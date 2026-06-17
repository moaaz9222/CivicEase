# api.py
# CivicEase AI — Enterprise FastAPI Backend Engine
# ==================================================

import os
import sys
from datetime import datetime  # <--- ده السطر اللي كان ناقص ووقع السيرفر!
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv

# إضافة المسار الحالي ليتعرف بايثون على مجلد الـ agents
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from agents.intake_agent import run_agent_1
from agents.policy_agent import run_agent_2
from agents.action_agent import run_agent_3

load_dotenv()

app = FastAPI(
    title="CivicEase AI — Core Engine",
    description="Decoupled Full-Stack Multi-Agent AI API",
    version="1.0.0",
)


# ── 1. Request / Response Schemas ──────────────────────────────────────────
class EvaluationRequest(BaseModel):
    user_input: str


class EvaluationResponse(BaseModel):
    status: str
    stage: str
    timestamp: str
    profile: Optional[dict] = None
    benefits: Optional[list] = None
    action_plan: Optional[dict] = None
    message: str


# دالة تنظيف الأرقام لحماية السيرفر من الكراش
def safe_float(val):
    if not val:
        return 0.0
    try:
        clean_str = str(val).replace("$", "").replace(",", "").strip()
        return float(clean_str)
    except (ValueError, TypeError):
        return 0.0


# ── 2. API Endpoints ────────────────────────────────────────────────────────
@app.post("/api/evaluate", response_model=EvaluationResponse)
async def evaluate_case(payload: EvaluationRequest):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Layer 1: Civic Data Intake Agent ---
    try:
        profile = run_agent_1(payload.user_input)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Intake Agent Layer Failure: {str(e)}"
        )

    if profile.get("clarification_needed"):
        return EvaluationResponse(
            status="NEED_CLARIFICATION",
            stage="extracting",
            timestamp=current_time,
            profile=profile,
            message=profile["clarification_needed"],
        )

    # --- Layer 2: Proactive Programmatic Guardrails ---
    income = safe_float(profile.get("monthly_income"))
    variance = safe_float(profile.get("income_variance"))

    if income > 0 and (variance / income) > 0.30:
        return EvaluationResponse(
            status="HUMAN_REVIEW",
            stage="done",
            timestamp=current_time,
            profile=profile,
            message="🚨 Forced Human Review: Income variance exceeds the 30% programmatic fraud threshold.",
        )

    # --- Layer 3: Civic Operations Agent ---
    try:
        benefits = run_agent_2(profile)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Policy Agent Layer Failure: {str(e)}"
        )

    # --- Layer 4: Dynamic Action Maker Agent ---
    try:
        action_plan = run_agent_3(profile, benefits)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Action Agent Layer Failure: {str(e)}"
        )

    final_status = "PENDING_CASEWORKER"
    # أضفت حماية هنا عشان لو الـ benefits رجعت فاضية السيرفر مايقعش
    if benefits and any(b.get("qualification_likelihood") == "HIGH" for b in benefits):
        final_status = "APPROVED_DISBURSEMENT"

    return EvaluationResponse(
        status=final_status,
        stage="done",
        timestamp=current_time,
        profile=profile,
        benefits=benefits,
        action_plan=action_plan,
        message="✅ Case payload generated and validated via sovereign multi-agent workflow.",
    )


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "groq_configured": bool(os.getenv("GROQ_API_KEY"))}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
