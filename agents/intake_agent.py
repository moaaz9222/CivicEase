import json
import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field, ValidationError, field_validator

load_dotenv()

ESSENTIAL_FIELDS = ("location", "monthly_income", "family_size")


class IntakeProfile(BaseModel):
    location: Optional[str] = Field(
        default=None,
        description="City, County, or State. E.g., 'Travis County, TX'",
    )
    monthly_income: Optional[str] = Field(
        default="None",
        description="Gross household monthly income in USD as a plain numeric string, or 'None' when unknown.",
    )
    family_size: Optional[int] = Field(
        default=None,
        ge=1,
        le=30,
        description="Total number of people in the household",
    )
    children_ages: List[int] = Field(
        default_factory=list,
        description="List of ages of the children",
    )
    specific_needs: List[str] = Field(
        default_factory=list,
        description="Keywords like 'food_assistance', 'childcare_support'",
    )
    language_preference: str = Field(
        default="English",
        description="User's preferred language",
    )
    urgency_flag: bool = Field(
        default=False,
        description="True if the user is in immediate danger or has zero resources",
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="List of critical fields missing",
    )
    clarification_needed: Optional[str] = Field(
        default=None,
        description="A friendly, empathetic question asking for missing info. Null if all good.",
    )

    @field_validator("monthly_income", mode="before")
    @classmethod
    def normalize_income(cls, value: object) -> str:
        if value is None:
            return "None"
        
        raw_str = str(value).strip().lower()
        
        # Check for explicit zero-income indicators
        zero_indicators = {
            "0", "0.0", "zero", "no income", "none income", "unemployed", 
            "zero income", "zero dollar", "zero dollars", "no monthly income",
            "none monthly income", "unemployment"
        }
        if raw_str in zero_indicators or "no income" in raw_str or "zero income" in raw_str or "zero dollar" in raw_str:
            return "0"
            
        cleaned = raw_str.replace("$", "").replace(",", "")
        if not cleaned or cleaned in {"none", "null", "unknown", "n/a"}:
            return "None"
        try:
            numeric = float(cleaned)
        except ValueError:
            return "None"
        if numeric < 0:
            return "None"
        return str(int(numeric)) if numeric.is_integer() else str(numeric)

    @field_validator("children_ages", mode="before")
    @classmethod
    def normalize_children_ages(cls, value: object) -> list[int]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        ages: list[int] = []
        for item in value:
            try:
                age = int(item)
            except (TypeError, ValueError):
                continue
            if 0 <= age <= 17:
                ages.append(age)
        return ages

    @field_validator("specific_needs", mode="before")
    @classmethod
    def normalize_needs(cls, value: object) -> list[str]:
        allowed = {
            "food_assistance",
            "childcare_support",
            "education_training",
            "healthcare",
            "housing",
            "other",
        }
        if not isinstance(value, list):
            return []
        normalized = []
        for item in value:
            need = str(item).strip().lower().replace(" ", "_")
            if need in allowed and need not in normalized:
                normalized.append(need)
        return normalized


INTAKE_SYSTEM_PROMPT = """
You are the Intake Specialist for CivicEase AI. Extract eligibility variables from raw conversational text.

Return ONLY one valid JSON object. Do not use markdown fences, tool calls, explanations, or preamble.

Required JSON shape:
{{
  "location": "State/City string or null",
  "monthly_income": "Plain numeric monthly USD string like '2500', or the string 'None'",
  "family_size": integer or null,
  "children_ages": [],
  "specific_needs": [],
  "language_preference": "English",
  "urgency_flag": false,
  "missing_fields": [],
  "clarification_needed": "One friendly sentence asking for missing info, or null"
}}

Strict rules:
1. Never infer income or specific ages when absent. For family_size, see rule 9 below.
2. If location, monthly_income, or family_size is missing (and rule 9 does not apply), add that field name to missing_fields.
3. If income is unknown, unstable, a range, or conflicting, set monthly_income to the exact string "None" and ask for clarification.
4. If yearly, weekly, or hourly income is single and unambiguous, convert it to monthly income.
5. specific_needs may only contain: food_assistance, childcare_support, education_training, healthcare, housing, other.
6. Strip personally identifiable information. Keep only eligibility-relevant location such as city, county, or state.
7. If any essential field is missing, clarification_needed must be exactly one friendly sentence. Otherwise it must be null.
8. If the user explicitly states they have no income, earn zero dollars, have no monthly income, or are unemployed, set monthly_income to "0". Do not set it to "None".
9. If the user refers to themselves in first-person singular (I, me, my) with NO mention of a partner, spouse, children, roommates, or other household members, set family_size to 1. Do NOT add family_size to missing_fields in this case.
"""


def _intake_fallback(message: str) -> dict:
    return IntakeProfile(
        monthly_income="None",
        missing_fields=list(ESSENTIAL_FIELDS),
        clarification_needed=message,
    ).model_dump()


def _extract_json_object(raw: str) -> dict:
    content = raw.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object")
    return json.loads(content[start : end + 1])


def _complete_missing_fields(profile: IntakeProfile) -> IntakeProfile:
    missing = set(profile.missing_fields)
    if not profile.location:
        missing.add("location")
    if not profile.monthly_income or profile.monthly_income == "None":
        missing.add("monthly_income")
    if profile.family_size is None:
        missing.add("family_size")

    profile.missing_fields = [field for field in ESSENTIAL_FIELDS if field in missing]
    if profile.missing_fields and not profile.clarification_needed:
        requested = ", ".join(profile.missing_fields)
        profile.clarification_needed = f"Could you share your {requested} so I can check programs more accurately?"
    if not profile.missing_fields:
        profile.clarification_needed = None
    return profile


def _infer_solo_individual(profile: IntakeProfile, user_text: str) -> IntakeProfile:
    """
    Python-level fallback for Rule 9: when the LLM fails to infer family_size=1
    for a clearly solo individual, this function does it programmatically.

    Triggered only when family_size is still None after LLM parsing AND the
    user text contains solo-living signals with no household-member signals.
    This is generalizable — it reads from user text, not hardcoded profiles.
    """
    if profile.family_size is not None:
        return profile  # Already determined — no action needed

    text_lower = user_text.lower()

    # Words that imply other people in the household
    household_signals = [
        "children", "kids", "child", "spouse", "partner", "wife", "husband",
        "family", "roommate", "daughter", "son", "baby", "infant", "toddler",
        "we ", "our ", "us ",
    ]
    # Phrases that imply a single individual living alone
    solo_signals = [
        "living in my car", "living alone", "by myself", "on my own",
        "i am alone", "i'm alone", "just me", "only me", "i live alone",
        "living in car", "sleeping in my car", "no one else",
    ]

    has_others = any(w in text_lower for w in household_signals)
    has_solo   = any(phrase in text_lower for phrase in solo_signals)

    if has_solo and not has_others:
        profile.family_size = 1
        profile.missing_fields = [f for f in profile.missing_fields if f != "family_size"]
        if not profile.missing_fields:
            profile.clarification_needed = None
        print("  [IntakeAgent] Solo-individual inference: family_size set to 1")

    return profile


def run_agent_1(user_text: str) -> dict:
    if not os.getenv("GROQ_API_KEY"):
        return _intake_fallback("The intake service is not configured yet. Please try again later.")

    try:
        llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name=os.getenv("GROQ_MODEL_NAME", "llama-3.1-8b-instant"),
            temperature=0,
            timeout=30,
            max_retries=2,
        )
        prompt = ChatPromptTemplate.from_messages(
            [("system", INTAKE_SYSTEM_PROMPT), ("human", "{user_input}")]
        )
        response = (prompt | llm).invoke({"user_input": str(user_text)[:8000]})
        payload = _extract_json_object(response.content)
        profile = _complete_missing_fields(IntakeProfile.model_validate(payload))
        # Python-level fallback: infer family_size=1 for clearly solo individuals
        profile = _infer_solo_individual(profile, str(user_text))
        return profile.model_dump()
    except (json.JSONDecodeError, ValidationError, ValueError):
        return _intake_fallback(
            "I had trouble reading that safely. Could you share your location, household size, monthly income, and what help you need?"
        )
    except Exception:
        return _intake_fallback(
            "The intake service is temporarily unavailable. Could you try again in a moment?"
        )
