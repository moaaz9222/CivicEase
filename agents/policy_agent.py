import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional
from core.rag_engine import get_retriever

load_dotenv()


# 1. بناء الهيكل المطابق تماماً لطلبك وللواجهة
class SourceCitation(BaseModel):
    document_title: str
    page_number: int
    excerpt_summary: str
    url: str


class BenefitAssessment(BaseModel):
    benefit_name: str
    agency: str
    qualification_likelihood: str = Field(
        description="Must be HIGH, MEDIUM, LOW, or UNLIKELY"
    )
    confidence_score: float = Field(description="Score from 0.0 to 1.0")
    plain_language_summary: str
    qualifying_reasons: List[str]
    disqualifying_risks: List[str]
    source_citations: List[SourceCitation]
    monthly_benefit_estimate: Optional[str] = None


# إجبار النموذج على إرجاع مصفوفة (List) من التقييمات
class Agent2Output(BaseModel):
    benefits: List[BenefitAssessment]


def run_agent_2(profile_data: dict) -> list:
    """
    يستقبل ملف المستخدم من Agent 1، يبحث في ChromaDB، ويطبق برومبت السياسات الصارم الخاص بك.
    """
    # جلب نصوص السياسات من الـ Vector DB المحلي
    retriever = get_retriever()
    query = f"Eligibility criteria for {', '.join(profile_data.get('specific_needs', []))} in {profile_data.get('location', '')}"
    relevant_docs = retriever.invoke(query)
    context = "\n\n".join([doc.page_content for doc in relevant_docs])

    # تهيئة LLaMA 3 عبر Groq
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama3-8b-8192",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(Agent2Output)

    # البرومبت الاحترافي الخاص بك بعد تنقيحه ليناسب المخرجات
    system_prompt = """
    You are the Benefits Knowledge Specialist for CivicEase AI. You 
    receive a structured eligibility profile (JSON) from Agent 1 and 
    a set of retrieved policy document excerpts from the Vector DB.

    Your job is to translate dense government policy language into 
    warm, clear, human-readable eligibility assessments.

    LANGUAGE RULES — STRICTLY ENFORCED:
    1. FORBIDDEN words/phrases: "approved", "guaranteed", "will receive", "you qualify", "you are eligible".
    2. REQUIRED framing: Always use "may qualify", "likely eligible", "based on the information provided", "subject to verification".
    3. Plain language standard: Write at a 6th-grade reading level. No jargon. If a policy term must be used, define it immediately.
    4. Empathy standard: Summaries must be warm and non-judgmental. Never use language that implies the user is "poor", "needy", or "dependent".

    CONFIDENCE SCORE LOGIC:
    - 0.85–1.0: User clearly meets income AND family size thresholds with no identified disqualifiers
    - 0.60–0.84: User likely meets thresholds but 1–2 variables were missing or ambiguous
    - 0.35–0.59: Partial match — user meets some but not all known criteria
    - 0.00–0.34: Low match or significant disqualifiers present
    """

    human_template = """
    User Profile:
    {profile}

    Policy Documents:
    {context}
    """

    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", human_template)]
    )

    chain = prompt | structured_llm
    result = chain.invoke({"profile": str(profile_data), "context": context})

    # إرجاع المصفوفة مباشرة لتناسب الـ Loop الخاص بـ app.py
    return [benefit.model_dump() for benefit in result.benefits]
