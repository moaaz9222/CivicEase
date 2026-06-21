import json
import os
from typing import List, Literal, Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

load_dotenv()


class LocalOffice(BaseModel):
    name: str
    address: str
    phone: str
    hours: str


class ChecklistItem(BaseModel):
    step_id: str = Field(description="Globally unique ID. e.g., 'SNAP_S1'")
    category: Literal["DOCUMENT", "ACTION", "APPOINTMENT", "LINK"]
    title: str
    description: str = Field(description="Keep under 25 words")
    resource_url: Optional[str] = None
    local_office: Optional[LocalOffice] = None


class BenefitActionBlock(BaseModel):
    benefit_name: str
    priority_rank: int = Field(ge=1)
    estimated_processing_time: str
    checklist: List[ChecklistItem] = Field(default_factory=list)
    pro_tip: str = "Keep copies of every document you submit."
    deadline_warning: Optional[str] = None


class SupportContact(BaseModel):
    name: str
    number: str
    available: str


class ActionPlanOutput(BaseModel):
    action_plan_title: str = "Your Benefits Action Plan"
    urgency_actions: List[str] = Field(default_factory=list)
    benefit_action_blocks: List[BenefitActionBlock] = Field(default_factory=list)
    next_best_action: str
    support_contacts: List[SupportContact] = Field(default_factory=list)


def _fallback_action_plan(urgent: bool = False) -> dict:
    return ActionPlanOutput(
        urgency_actions=["Call 2-1-1 for immediate local assistance."] if urgent else [],
        benefit_action_blocks=[],
        next_best_action="Gather proof of identity, residence, household size, and income before applying.",
        support_contacts=[SupportContact(name="2-1-1", number="2-1-1", available="24/7")],
    ).model_dump()


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


import re
from urllib.parse import urlparse


def _apply_guardrails(action_plan: dict, policy_matches: dict) -> dict:
    # Guardrail 1: Strict Program Alignment
    allowed_benefits = {
        match.get("benefit_name", "").strip().lower() 
        for match in policy_matches.get("matches", [])
    }
    
    filtered_blocks = []
    for block in action_plan.get("benefit_action_blocks", []):
        name = block.get("benefit_name", "").strip().lower()
        if name in allowed_benefits:
            filtered_blocks.append(block)
    action_plan["benefit_action_blocks"] = filtered_blocks
    
    # Collect all valid URLs from Policy Agent's citations
    valid_citation_urls = set()
    for match in policy_matches.get("matches", []):
        for citation in match.get("source_citations", []):
            url = citation.get("url")
            if url:
                valid_citation_urls.add(url.strip().lower())
                
    # Trusted TLDs whitelist
    trusted_tlds = (".gov", ".org", ".edu")
    
    # Guardrail 2: Certainty Mitigation
    mitigations = {
        r"\byou are approved\b": "you may be eligible",
        r"\byou are guaranteed\b": "you may qualify",
        r"\bwill receive\b": "may receive",
        r"\bwill get\b": "may qualify for",
        r"\bguaranteed to receive\b": "potentially eligible to receive",
        r"\bdefinitely qualify\b": "likely qualify",
    }
    
    def sanitize_text(text: str) -> str:
        if not text:
            return text
        sanitized = text
        for pattern, replacement in mitigations.items():
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        return sanitized

    if "next_best_action" in action_plan:
        action_plan["next_best_action"] = sanitize_text(action_plan["next_best_action"])
        
    if "urgency_actions" in action_plan:
        action_plan["urgency_actions"] = [
            sanitize_text(action) for action in action_plan["urgency_actions"]
        ]

    for block in action_plan.get("benefit_action_blocks", []):
        block["pro_tip"] = sanitize_text(block.get("pro_tip", ""))
        if block.get("deadline_warning"):
            block["deadline_warning"] = sanitize_text(block["deadline_warning"])
            
        for item in block.get("checklist", []):
            item["title"] = sanitize_text(item.get("title", ""))
            item["description"] = sanitize_text(item.get("description", ""))
            
            # Guardrail 3: URL Whitelisting & Validation
            url = item.get("resource_url")
            if url:
                url_str = url.strip()
                url_lower = url_str.lower()
                
                is_valid = False
                if url_lower in valid_citation_urls:
                    is_valid = True
                else:
                    try:
                        parsed = urlparse(url_str)
                        hostname = parsed.hostname
                        if hostname and hostname.lower().endswith(trusted_tlds):
                            is_valid = True
                    except Exception:
                        pass
                
                if not is_valid:
                    item["resource_url"] = None

    return action_plan


def run_agent_3(profile_data: dict, policy_matches: dict) -> dict:
    benefits_list = policy_matches.get("matches", []) if isinstance(policy_matches, dict) else []
    if not benefits_list:
        return _fallback_action_plan(bool(profile_data.get("urgency_flag")))

    try:
        llm = _llm()
        system_prompt = """
You are the Benefits Action Planner for CivicEase AI.
Convert structured eligibility signals and policy matches into a practical step-by-step action plan dashboard.

You MUST return a JSON object with this exact shape:
{{
  "action_plan_title": "string (e.g., 'Your Customized Benefits Action Plan')",
  "urgency_actions": ["string of immediate urgent actions if urgency_flag is True, otherwise empty list"],
  "benefit_action_blocks": [
    {{
      "benefit_name": "string (MUST exactly match the benefit_name from the input matches)",
      "priority_rank": 1,
      "estimated_processing_time": "string (e.g., '30 days', '2 weeks')",
      "checklist": [
        {{
          "step_id": "string (globally unique step ID, e.g., 'SNAP_S1', 'MED_S2')",
          "category": "DOCUMENT" | "ACTION" | "APPOINTMENT" | "LINK",
          "title": "string (short step title)",
          "description": "string (detailed description of what to do, keep under 25 words)",
          "resource_url": "string or null (valid URL to portal or info, or null)",
          "local_office": {{
            "name": "string",
            "address": "string",
            "phone": "string",
            "hours": "string"
          }}
        }}
      ],
      "pro_tip": "string (practical advice for applying)",
      "deadline_warning": "string or null (if any deadlines apply, or null)"
    }}
  ],
  "next_best_action": "string (a summary statement of the absolute first thing the user should do)",
  "support_contacts": [
    {{
      "name": "string",
      "number": "string",
      "available": "string"
    }}
  ]
}}

Strict instructions:
1. Do not wrap the JSON output in markdown code blocks like ```json. Return ONLY valid raw JSON.
2. For each benefit in the matches, output one matching benefit_action_block. Use the exact benefit_name.
3. Keep descriptions extremely concise (under 25 words per step).
4. Provide realistic steps, resource URLs (if any official portals are mentioned in the policy references), and local office details if relevant, otherwise null.
"""
        
        human_template = "User Profile:\n{profile}\n\nPolicy Matches:\n{matches}"
        prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", human_template)])

        chain = prompt | llm
        response = chain.invoke({
            "profile": json.dumps(profile_data, ensure_ascii=False),
            "matches": json.dumps(policy_matches, ensure_ascii=False)
        })

        raw_content = response.content.strip()
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]

        data = json.loads(raw_content.strip())
        validated = ActionPlanOutput.model_validate(data)
        return _apply_guardrails(validated.model_dump(), policy_matches)

    except Exception:
        return _fallback_action_plan(bool(profile_data.get("urgency_flag")))