import json
import os
from typing import List, Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from core.rag_engine import get_retriever

load_dotenv()

STATE_ALIASES = {
    "tx": "texas", "ca": "california", "ny": "new_york", "fl": "florida",
    "il": "illinois", "pa": "pennsylvania", "oh": "ohio", "ga": "georgia",
    "nc": "north_carolina", "mi": "michigan", "nj": "new_jersey",
    "va": "virginia", "wa": "washington", "az": "arizona", "ma": "massachusetts",
    "tn": "tennessee", "in": "indiana", "mo": "missouri", "md": "maryland",
    "wi": "wisconsin", "co": "colorado", "mn": "minnesota", "sc": "south_carolina",
    "al": "alabama", "la": "louisiana", "ky": "kentucky", "or": "oregon",
    "ok": "oklahoma", "ct": "connecticut", "ut": "utah", "ia": "iowa",
    "nv": "nevada", "ar": "arkansas", "ms": "mississippi", "ks": "kansas",
    "nm": "new_mexico", "ne": "nebraska", "wv": "west_virginia", "id": "idaho",
    "hi": "hawaii", "nh": "new_hampshire", "me": "maine", "mt": "montana",
    "ri": "rhode_island", "de": "delaware", "sd": "south_dakota",
    "nd": "north_dakota", "ak": "alaska", "vt": "vermont", "wy": "wyoming",
}


class SourceCitation(BaseModel):
    document_title: str
    page_number: Optional[int] = None
    excerpt_summary: str
    url: Optional[str] = None


class BenefitAssessment(BaseModel):
    benefit_name: str
    agency: str
    estimated_value: str
    confidence_score: float
    headline_summary: str
    eligibility_analysis: str
    source_citations: List[SourceCitation] = Field(default_factory=list)


class PolicyEvaluationResponse(BaseModel):
    matches: List[BenefitAssessment] = Field(default_factory=list)


def parse_income_to_float(raw: object) -> float:
    if raw is None:
        return 0.0
    cleaned = str(raw).strip().replace("$", "").replace(",", "")
    if not cleaned or cleaned.lower() in {"none", "null", "unknown", "n/a"}:
        return 0.0
    try:
        value = float(cleaned)
    except ValueError:
        return 0.0
    return value if value >= 0 else 0.0


def _detect_state(location_str: Optional[str]) -> Optional[str]:
    if not location_str:
        return None
    normalized = location_str.lower().replace(",", " ").replace(".", " ")
    tokens = normalized.split()
    for token in tokens:
        if token in STATE_ALIASES:
            return STATE_ALIASES[token]
    underscored = "_".join(tokens)
    for state in STATE_ALIASES.values():
        if state in underscored:
            return state
    return None


def _llm() -> ChatGroq:
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is not configured")
    return ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name=os.getenv("GROQ_MODEL_NAME", "llama-3.1-8b-instant"),
        temperature=0,
        timeout=45,
        max_retries=2,
    )


def run_agent_2(enriched_profile: dict) -> dict:
    try:
        raw_income = enriched_profile.get("monthly_income")
        if raw_income == "None" or raw_income is None:
            income_str = "unknown"
        else:
            income_float = parse_income_to_float(raw_income)
            income_str = str(income_float)

        normalized_profile = {
            **enriched_profile,
            "monthly_income": income_str,
        }

        raw_location = enriched_profile.get("location") or ""
        specific_needs = enriched_profile.get("specific_needs") or ["benefits"]
        detected_state = _detect_state(raw_location)

        metadata_filter = {"state": detected_state} if detected_state else None

        query = f"State: {raw_location or detected_state}, Program/Need: {', '.join(map(str, specific_needs))} eligibility guidelines criteria 2026"

        try:
            retriever = get_retriever(metadata_filter=metadata_filter)
            relevant_docs = retriever.invoke(query)
        except Exception:
            return {"matches": []}

        context = "\n\n".join(doc.page_content for doc in relevant_docs).strip()
        if not context:
            return {"matches": []}

        system_prompt = """
You are the Benefits Knowledge Specialist for CivicEase AI.
Analyze the user profile against the provided policy documents.

You MUST return a JSON object with a single key "matches" containing a list of objects.
Each object in the list MUST have these keys exactly:
- "benefit_name": (string) name of program (e.g., "SNAP", "Medicaid")
- "agency": (string) managing agency
- "estimated_value": (string) value description (e.g., "$291/month")
- "confidence_score": (float between 0.0 and 1.0)
- "headline_summary": (string) quick overview
- "eligibility_analysis": (string) why they qualify, using cautious language (e.g., "may qualify")
- "source_citations": (array of objects) each with "document_title", "page_number" (null or int), "excerpt_summary", and "url" (null or string)

Return ONLY raw valid JSON. Do not wrap in markdown blocks like ```json.
"""
        human_template = "User Profile JSON:\n{profile}\n\nPolicy Documents:\n{context}"
        prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", human_template)])

        chain = prompt | _llm()
        response = chain.invoke({
            "profile": json.dumps(normalized_profile, ensure_ascii=False),
            "context": context[:12000]
        })

        raw_content = response.content.strip()
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]

        data = json.loads(raw_content.strip())
        validated = PolicyEvaluationResponse.model_validate(data)
        return validated.model_dump()
    except Exception:
        return {"matches": []}