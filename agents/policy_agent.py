import json
import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, ConfigDict, Field, model_validator

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

# Relevance keywords per need category — used by the context-filtering step
_NEED_KEYWORDS = {
    "food_assistance":    ["snap", "food", "nutrition", "grocery", "ebt", "fns"],
    "healthcare":         ["medicaid", "chip", "health", "medical", "insurance", "clinic"],
    "childcare_support":  ["childcare", "child care", "ccdf", "daycare", "wic", "infant"],
    "housing":            ["housing", "shelter", "eviction", "liheap", "utility", "rent"],
    "education_training": ["education", "training", "tanf", "workforce", "school"],
    "other":              ["assistance", "benefits", "program", "support"],
}


# ===========================================================================
# Pydantic Schemas — Reliability-First Design
# ===========================================================================

class ReasoningChain(BaseModel):
    """
    Structured 4-step Chain-of-Thought (CoT).

    Design principle: all fields default to "" so Pydantic never raises a
    ValidationError on partial LLM output. Completeness is measured separately
    by the evaluation framework — not enforced here at parse time.
    """
    step1_extract_criteria: str = Field(
        default="",
        description=(
            "Eligibility criteria quoted or paraphrased directly from the retrieved "
            "policy document. Must reference the document, not prior knowledge."
        ),
    )
    step2_extract_user_data: str = Field(
        default="",
        description=(
            "User's actual profile values relevant to this program: "
            "monthly income, family size, location, age, specific needs."
        ),
    )
    step3_compare: str = Field(
        default="",
        description=(
            "Explicit numerical comparison of user data against policy criteria. "
            "Must include at least one specific number (income amount, FPL %, age, etc.)."
        ),
    )
    step4_conclusion: str = Field(
        default="",
        description=(
            "Final eligibility determination: Eligible / Likely Eligible / Ineligible. "
            "Include a confidence score and the primary reason."
        ),
    )


class SourceCitation(BaseModel):
    document_title: str
    page_number: Optional[int] = None
    excerpt_summary: str
    url: Optional[str] = None


class BenefitAssessment(BaseModel):
    """
    Reliability guardrails:
    - extra="ignore": unknown JSON fields from the LLM are silently dropped,
      preventing ValidationError crashes on unexpected output.
    - reasoning_steps (legacy field): if the LLM returns the old flat string
      instead of reasoning_chain, the model_validator promotes it automatically.
    """
    model_config = ConfigDict(extra="ignore")

    benefit_name: str
    agency: Optional[str] = Field(default="Unknown Agency")
    estimated_value: Optional[str] = Field(default="Not specified")
    confidence_score: float = Field(default=0.5)
    reasoning_chain: ReasoningChain = Field(default_factory=ReasoningChain)
    reasoning_steps: Optional[str] = Field(default=None, exclude=True)  # legacy compat
    headline_summary: Optional[str] = Field(default="")
    eligibility_analysis: Optional[str] = Field(default="")
    source_citations: List[SourceCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _promote_legacy_reasoning(self) -> "BenefitAssessment":
        """
        Backward-compatibility bridge: if the LLM used the old 'reasoning_steps'
        flat-string field and reasoning_chain is empty, split the text into the
        4-step structure using Step N markers or heuristic splitting.
        """
        chain = self.reasoning_chain
        chain_is_empty = not any([
            chain.step1_extract_criteria,
            chain.step2_extract_user_data,
            chain.step3_compare,
            chain.step4_conclusion,
        ])
        legacy = (self.reasoning_steps or "").strip()
        if chain_is_empty and legacy:
            parts = re.split(r"(?i)step\s*[1-4]\s*[:\-\u2013]?", legacy)
            parts = [p.strip() for p in parts if p.strip()]
            self.reasoning_chain = ReasoningChain(
                step1_extract_criteria=parts[0] if len(parts) > 0 else legacy,
                step2_extract_user_data=parts[1] if len(parts) > 1 else "",
                step3_compare=parts[2] if len(parts) > 2 else "",
                step4_conclusion=parts[3] if len(parts) > 3 else "",
            )
        return self


class PolicyEvaluationResponse(BaseModel):
    matches: List[BenefitAssessment] = Field(default_factory=list)


# ===========================================================================
# Helper Utilities
# ===========================================================================

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


def _repair_json(raw: str) -> str:
    """
    Lightweight JSON repair for common LLM output issues:
      - Strip markdown code fences (```json ... ```)
      - Remove trailing commas before } or ]
      - Extract only the outermost complete JSON object, discarding any text after it
    """
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)

    # Remove trailing commas before closing delimiters
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Find and extract the outermost complete JSON object
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    end = -1
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start=start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    return text[start: end + 1] if end != -1 else text[start:]


def _filter_relevant_chunks(
    docs: list, specific_needs: list, detected_state: Optional[str]
) -> list:
    """
    Context-Filtering Step: retain chunks that carry at least one relevance
    signal for the user's state or specific needs.

    Fallback: if fewer than 2 chunks survive, return all retrieved chunks so
    the LLM is never given an empty context window.

    Design note: This filter is purely additive — it never invents context.
    It only reduces noise from semantically unrelated chunks.
    """
    general_signals = [
        "fpl", "federal poverty", "eligibility", "income limit",
        "qualify", "eligible", "household", "benefit", "program",
    ]

    need_keywords: list[str] = []
    for need in (specific_needs or ["other"]):
        need_keywords.extend(_NEED_KEYWORDS.get(need, _NEED_KEYWORDS["other"]))

    state_token = detected_state.replace("_", " ") if detected_state else ""

    filtered = []
    for doc in docs:
        text = doc.page_content.lower()
        has_state   = bool(state_token and state_token in text)
        has_need    = any(kw in text for kw in need_keywords)
        has_general = any(sig in text for sig in general_signals)
        if has_state or has_need or has_general:
            filtered.append(doc)

    # Wide fallback: never starve the LLM of context
    return filtered if len(filtered) >= 2 else docs


def _apply_conclusion_filter(matches: list) -> list:
    """
    Self-Consistency Guard (Hallucination Prevention Layer).

    Drops any match where the LLM's own step4_conclusion or step3_compare
    text indicates the user does NOT qualify.

    Rationale: Small models (8B parameters) frequently reason correctly that
    a user exceeds an income limit but still include the program in the
    matches list. This post-processor enforces consistency between the model's
    reasoning and its output — using the model's own words, not hard-coded
    income thresholds. This makes it fully generalizable to unseen states.
    """
    INELIGIBLE_SIGNALS = [
        "not eligible", "ineligible", "does not qualify", "disqualif",
        "income exceeds", "income is over", "income is too high",
        "over the limit", "exceeds the limit", "above the limit",
        "above the threshold", "not qualify", "cannot qualify",
        "no eligibility", "too high to qualify",
    ]
    filtered = []
    for m in matches:
        chain    = m.get("reasoning_chain") or {}
        conclusion = str(chain.get("step4_conclusion") or "").lower()
        compare    = str(chain.get("step3_compare")    or "").lower()
        combined   = conclusion + " " + compare

        if any(sig in combined for sig in INELIGIBLE_SIGNALS):
            benefit = m.get("benefit_name", "Unknown")
            print(f"  [PolicyAgent] Self-consistency guard: removed '{benefit}' "
                  f"(LLM's own reasoning concluded ineligible)")
            continue
        filtered.append(m)
    return filtered


def _llm() -> ChatGroq:
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is not configured")
    return ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name=os.getenv("GROQ_MODEL_NAME", "llama-3.1-8b-instant"),
        temperature=0,      # Deterministic output — same input always yields same answer
        timeout=60,
        max_retries=2,
    )


# ===========================================================================
# System Prompt — Inductive Reasoning Protocol
# ===========================================================================

POLICY_SYSTEM_PROMPT = """
You are a Benefits Eligibility Analyst for CivicEase AI.

CORE RULE — INDUCTIVE REASONING ONLY:
You derive ALL eligibility criteria exclusively from the Policy Documents provided below.
You do NOT use internal training knowledge to determine eligibility rules.
If a program is not mentioned in the provided documents, do NOT include it.

YOUR TASK:
Review the Policy Documents and identify every government benefit program for which the
user profile plausibly meets the stated criteria.

For EACH program you assess, fill in all 4 steps of the reasoning_chain:

  step1_extract_criteria:
    Quote or closely paraphrase the eligibility rules DIRECTLY from the document.
    Include the income limit, FPL percentage, age cutoff, or other criteria as stated.
    Example: "Per document: SNAP gross income limit for family of 3 = 130% FPL = $2,311/month."

  step2_extract_user_data:
    State the user's actual values from the profile JSON.
    Example: "User profile: income=$1,500/month, family_size=3, location=Texas, needs=food_assistance."

  step3_compare:
    Perform an explicit numerical comparison. You MUST include at least one number.
    Example: "User income $1,500 is below $2,311 SNAP limit. Income test: PASS.
              Family size 3 meets household requirement. Size test: PASS."

  step4_conclusion:
    State your eligibility determination and confidence.
    Example: "Likely Eligible for SNAP. Confidence: 0.85.
              Reason: income and family size both satisfy the stated criteria."

IMPORTANT: Return ONLY raw JSON. No markdown fences. No text outside the JSON object.

Required JSON structure:
{{"matches": [
  {{
    "benefit_name": "SNAP",
    "agency": "USDA / State Agency Name",
    "estimated_value": "$291/month",
    "confidence_score": 0.85,
    "reasoning_chain": {{
      "step1_extract_criteria": "Per document: SNAP gross income limit ...",
      "step2_extract_user_data": "User: income=$1500, family_size=3 ...",
      "step3_compare": "1500 < 2311. PASS. Family size 3 meets minimum. PASS.",
      "step4_conclusion": "Likely Eligible. Confidence 0.85. Income below limit."
    }},
    "headline_summary": "User likely qualifies for SNAP food assistance.",
    "eligibility_analysis": "Based on the retrieved policy documents, the user may qualify because their income and family size fall within the stated limits.",
    "source_citations": [
      {{
        "document_title": "CivicEase Knowledge Base",
        "page_number": null,
        "excerpt_summary": "SNAP income limit at 130% FPL",
        "url": null
      }}
    ]
  }}
]}}

RULES:
1. Only include programs explicitly referenced in the provided Policy Documents.
2. Use cautious language: "may qualify", "likely eligible", "potentially eligible".
3. If the user's income clearly exceeds a program's stated limit, state that in step4_conclusion and set confidence_score below 0.25.
4. The reasoning_chain is mandatory. All 4 steps must contain substantive content.
5. step3_compare must contain at least one specific number (income amount, percentage, or age).
6. Do NOT hallucinate program names, dollar amounts, agency names, or URLs not in the documents.
7. Source citations must reference only information present in the provided documents.
"""


# ===========================================================================
# Main Agent Entry Point
# ===========================================================================

def run_agent_2(enriched_profile: dict) -> dict:
    """
    Policy Agent (Agent 2): Retrieves relevant policy documents from ChromaDB
    and uses the LLM to assess benefit eligibility via structured Chain-of-Thought.

    Reliability guarantees:
    - temperature=0 ensures deterministic, reproducible output
    - _repair_json() handles malformed LLM responses without crashing
    - _apply_conclusion_filter() removes self-contradictory matches
    - All exceptions are caught and logged; never propagated to the UI
    """
    try:
        raw_income = enriched_profile.get("monthly_income")
        income_str = (
            "unknown"
            if (raw_income == "None" or raw_income is None)
            else str(parse_income_to_float(raw_income))
        )

        normalized_profile = {**enriched_profile, "monthly_income": income_str}

        raw_location   = enriched_profile.get("location") or ""
        specific_needs = enriched_profile.get("specific_needs") or ["other"]
        detected_state = _detect_state(raw_location)

        needs_str = ", ".join(map(str, specific_needs))
        query = (
            f"State: {raw_location or detected_state}, "
            f"Need: {needs_str} eligibility income limits criteria 2026"
        )

        metadata_filter = {"state": detected_state} if detected_state else None

        try:
            retriever = get_retriever(metadata_filter=metadata_filter)
            raw_docs  = retriever.invoke(query)
        except Exception as e:
            print(f"  [PolicyAgent] RAG retrieval error: {e}")
            return {"matches": []}

        # Context-Filtering Step: improve signal quality before LLM call
        relevant_docs = _filter_relevant_chunks(raw_docs, specific_needs, detected_state)
        context = "\n\n".join(doc.page_content for doc in relevant_docs).strip()
        if not context:
            print("  [PolicyAgent] No relevant context after filtering.")
            return {"matches": []}

        human_template = "User Profile JSON:\n{profile}\n\nPolicy Documents:\n{context}"
        prompt = ChatPromptTemplate.from_messages([
            ("system", POLICY_SYSTEM_PROMPT),
            ("human",  human_template),
        ])
        chain    = prompt | _llm()
        response = chain.invoke({
            "profile": json.dumps(normalized_profile, ensure_ascii=False),
            "context": context[:12000],  # Balanced window: enough policy detail, avoids truncation
        })

        raw_content = response.content.strip()

        # JSON Repair Step: handle common LLM formatting issues
        repaired = _repair_json(raw_content)

        try:
            data = json.loads(repaired)
        except json.JSONDecodeError as je:
            print(f"  [PolicyAgent] JSON parse error after repair: {je}")
            print(f"  [PolicyAgent] First 400 chars of raw response:\n{raw_content[:400]}")
            return {"matches": []}

        # Pydantic Validation: structured schema enforcement
        validated = PolicyEvaluationResponse.model_validate(data)

        # Self-Consistency Guard: drop programs the LLM itself concluded are ineligible
        clean_matches = _apply_conclusion_filter(validated.model_dump().get("matches", []))
        return {"matches": clean_matches}

    except Exception as e:
        print(f"  [PolicyAgent] Unexpected error: {type(e).__name__}: {e}")
        return {"matches": []}