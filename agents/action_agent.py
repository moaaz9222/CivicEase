import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional

load_dotenv()


# 1. تعريف الـ Pydantic Schema ليتطابق بالملي مع الـ app.py
class LocalOffice(BaseModel):
    name: str
    address: str
    phone: str
    hours: str


class ChecklistItem(BaseModel):
    step_id: str = Field(
        description="Globally unique ID. Format: [PROGRAM]_S[NUM] e.g., 'SNAP_S1'"
    )
    category: str = Field(
        description="Must be exactly: DOCUMENT, ACTION, APPOINTMENT, or LINK"
    )
    title: str
    description: str = Field(description="Keep under 25 words")
    is_completed: bool = False
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
    action_plan_title: str = "Your Benefits Action Plan"
    urgency_actions: List[str] = Field(default=[])
    benefit_action_blocks: List[BenefitActionBlock]
    next_best_action: str
    support_contacts: List[SupportContact]


def run_agent_3(profile_data: dict, benefits_data: list) -> dict:
    """
    يأخذ تقييم الأهلية من Agent 2 ويحوله إلى خطة عمل تنفيذية ومنظمة للواجهة.
    """
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama3-8b-8192",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(ActionPlanOutput)

    # البرومبت الاحترافي الخاص بك مع حماية الـ Unique Key
    system_prompt = """
    You are the Action Plan Architect for CivicEase AI. You receive 
    the benefits assessment array from Agent 2 and transform it into 
    a concrete, step-by-step action roadmap that a user can immediately 
    begin following.

    RULES:
    1. Rank benefits by priority_rank: Order by qualification_likelihood DESC (HIGH first, UNLIKELY last).
    2. Every checklist item MUST have a direct .gov URL where one exists. Never link to third-party aggregators.
    3. Keep step descriptions under 25 words — users are often on mobile or in stressful situations.
    4. CRITICAL: Every 'step_id' MUST be globally unique. Use the format: [PROGRAM_ACRONYM]_S[NUMBER] (e.g., 'SNAP_S1', 'SNAP_S2', 'WIC_S1').
    5. urgency_actions: Only if urgency_flag in the profile is True, prepend 2-3 immediate steps (e.g., emergency food pantry locator).
    6. Never fabricate phone numbers, addresses, or URLs. Use placeholder format [VERIFY: source] if uncertain.
    """

    human_template = """
    User Profile Data:
    {profile}

    Benefits Assessment (from Agent 2):
    {benefits}
    """

    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", human_template)]
    )

    chain = prompt | structured_llm
    result = chain.invoke(
        {"profile": str(profile_data), "benefits": str(benefits_data)}
    )

    return result.model_dump()
