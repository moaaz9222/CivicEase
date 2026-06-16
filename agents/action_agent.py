import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional

load_dotenv()


class LocalOffice(BaseModel):
    name: str
    address: str
    phone: str
    hours: str


class ChecklistItem(BaseModel):
    step_id: str = Field(description="Globally unique ID. e.g., 'SNAP_S1'")
    category: str = Field(
        description="Must be exactly: DOCUMENT, ACTION, APPOINTMENT, or LINK"
    )
    title: str
    description: str = Field(description="Keep under 25 words")
    resource_url: Optional[str] = None
    local_office: Optional[LocalOffice] = None


class BenefitActionBlock(BaseModel):
    benefit_name: str
    priority_rank: int
    estimated_processing_time: str
    checklist: List[ChecklistItem]
    pro_tip: str
    deadline_warning: Optional[str] = None


class SupportContact(BaseModel):
    name: str
    number: str
    available: str


class ActionPlanOutput(BaseModel):
    action_plan_title: str = Field(default="Your Benefits Action Plan")
    urgency_actions: List[str] = Field(default=[])
    benefit_action_blocks: List[BenefitActionBlock]
    next_best_action: str
    support_contacts: List[SupportContact]


def run_agent_3(profile_data: dict, benefits_data: list) -> dict:
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama-3.1-8b-instant",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(ActionPlanOutput)

    system_prompt = """
    You are the Action Plan Architect for CivicEase AI.
    RULES:
    1. Rank benefits by priority_rank: Order by qualification_likelihood DESC.
    2. Every checklist item MUST have a direct .gov URL where one exists.
    3. Keep step descriptions under 25 words.
    4. CRITICAL: Every 'step_id' MUST be globally unique (e.g., 'SNAP_S1').
    5. urgency_actions: Only if urgency_flag is True, prepend immediate steps.
    """

    human_template = "Profile Data:\n{profile}\n\nBenefits:\n{benefits}"

    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", human_template)]
    )

    chain = prompt | structured_llm

    try:
        result = chain.invoke(
            {"profile": str(profile_data), "benefits": str(benefits_data)}
        )
        if not result:
            raise ValueError("Empty Output")
        return result.model_dump()

    except Exception as e:
        print(f"⚠️ Error in Agent 3: {e}")
        # خطة طوارئ لو النموذج علق عشان الواجهة ماتقفلش
        return {
            "action_plan_title": "Your Benefits Action Plan",
            "urgency_actions": ["Please contact 2-1-1 for immediate assistance."],
            "benefit_action_blocks": [],
            "next_best_action": "System load is high, but you can still apply through local offices.",
            "support_contacts": [
                {"name": "Emergency Hotline", "number": "2-1-1", "available": "24/7"}
            ],
        }
