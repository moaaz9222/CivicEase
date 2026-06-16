import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional

# تحميل المفاتيح من ملف .env
load_dotenv()


# 1. تعريف هيكل البيانات (Schema) ليتطابق تماماً مع واجهة Streamlit
class IntakeProfile(BaseModel):
    location: Optional[str] = Field(
        description="City, County, or State. E.g., 'Travis County, TX'"
    )
    monthly_income: Optional[float] = Field(
        description="Estimated monthly income in USD"
    )
    family_size: Optional[int] = Field(
        description="Total number of people in the household"
    )
    children_ages: List[int] = Field(
        default=[], description="List of ages of the children"
    )
    specific_needs: List[str] = Field(
        default=[], description="Keywords like 'food_assistance', 'childcare_support'"
    )
    language_preference: str = Field(
        default="English", description="User's preferred language"
    )
    urgency_flag: bool = Field(
        default=False,
        description="True if the user is in immediate danger or has zero resources",
    )
    missing_fields: List[str] = Field(
        default=[],
        description="List of critical fields missing (e.g., 'monthly_income', 'family_size')",
    )
    clarification_needed: Optional[str] = Field(
        default=None,
        description="A friendly, empathetic question asking for missing info. Null if all good.",
    )


def run_agent_1(user_text: str) -> dict:
    """
    يأخذ نص المستخدم العشوائي ويستخرج منه البيانات بتنسيق JSON دقيق وموثوق.
    """
    # 2. تهيئة نموذج LLaMA 3 السريع والمجاني عبر Groq
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama3-8b-8192",  # يمكنك استخدام llama3-70b-8192 لأداء أذكى
        temperature=0,  # صفر لضمان الدقة وعدم التأليف
    )

    # إجبار النموذج على الالتزام بالهيكل
    structured_llm = llm.with_structured_output(IntakeProfile)

    # 3. هندسة الأوامر (System Prompt) مع قيود الذكاء الاصطناعي المسؤول
    system_prompt = """
    You are the Intake Specialist for CivicEase AI, a compassionate and precise data extraction agent. Your sole responsibility is to listen to a user's raw, conversational description of their situation and extract structured eligibility variables from it.

EXTRACTION TARGETS:
  - location: State and/or county/city (e.g., "Travis County, TX")
  - monthly_income: Gross household monthly income in USD (Number only)
  - family_size: Total number of people in the household (Integer only)
  - children_ages: List of integers representing the ages of all children under 18
  - specific_needs: Array of benefit categories mentioned or implied (options: "food_assistance", "childcare_support", "education_training", "healthcare", "housing", "other")
  - language_preference: Detected or stated language preference
  - urgency_flag: Boolean — true if the user indicates immediate crisis (e.g., "we have no food", "eviction tomorrow"), otherwise false.

OUTPUT FORMAT:
You must ALWAYS respond with a valid JSON object and NOTHING else. 
Do NOT wrap the JSON in markdown code blocks (e.g., no ```json).
No preamble, no explanation, no conversational text.

{
  "location": "...",
  "monthly_income": 0.0,
  "family_size": 0,
  "children_ages": [],
  "specific_needs": [],
  "language_preference": "...",
  "urgency_flag": false,
  "missing_fields": [],
  "clarification_needed": "..." 
}

STRICT RULES:
1. MISSING DATA: Never assume or hallucinate income, family size, or ages. If any value is missing from the user's prompt, you MUST set its value to `null` (not the string "null" or "not provided", but the JSON null type).
2. MISSING FIELDS HANDLING: If essential data (location, monthly_income, family_size) is missing, append the field names to the 'missing_fields' array AND generate exactly one friendly, empathetic sentence in 'clarification_needed' asking for this specific info. If all essential data is present, set 'clarification_needed' to null.
3. INFERRING NEEDS: Be generous in interpreting vague language. (e.g., "I can't afford groceries" implies "food_assistance").
4. INCOME MATH: If the user provides a yearly salary or weekly wage, calculate the monthly equivalent and store only that monthly numeric value.
5. PRIVACY GUARDRAIL (PII): Strip all Personally Identifiable Information (full names, SSNs, exact street addresses) from your output — store only what is needed for eligibility (like City/State).
6. TONE: Never add commentary or sympathy statements outside the 'clarification_needed' field.
    """

    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", "{user_input}")]
    )

    # 4. التنفيذ
    chain = prompt | structured_llm
    result = chain.invoke({"user_input": user_text})

    # إرجاع البيانات في صيغة Dictionary لكي يفهمها Streamlit
    return result.model_dump()


# للتجربة السريعة بمعزل عن الواجهة
if __name__ == "__main__":
    test_input = "I live in Austin Texas, I have 2 kids aged 4 and 7, my income is about $2100 a month, and I need help with food and childcare."
    print("Testing Agent 1...")
    output = run_agent_1(test_input)
    print(output)
