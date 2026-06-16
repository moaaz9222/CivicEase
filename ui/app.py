# civicease_app.py
# CivicEase AI — Streamlit Frontend Scaffold
# ============================================

import sys
import os
import streamlit as st
import json
import time
from datetime import datetime

# إضافة المسار الرئيسي للمشروع ليتعرف بايثون على مجلد الوكلاء بره الـ ui
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── الربط الحقيقي للوكلاء ───────────────────────────────────────────────────
from agents.intake_agent import run_agent_1
from agents.policy_agent import run_agent_2
from agents.action_agent import run_agent_3

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CivicEase AI",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS (تم إصلاح الألوان والتباين بالكامل هنا) ───────────────────────────
st.markdown(
    """
<style>
    /* الإجبار على خلفية فاتحة مريحة للعين */
    .stApp { background-color: #F8FAFC !important; }
    
    /* حل مشكلة اختفاء النصوص: إجبار جميع العناوين والنصوص العادية على اللون الداكن */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp p, .stApp label, .stApp div {
        color: #0F172A !important;
    }
    
    /* استثناء الهيدر الرئيسي ليبقى باللون الأبيض */
    .civicease-header, .civicease-header div, .civicease-header span {
        color: white !important;
        background: linear-gradient(135deg, #1B4F72, #2E86C1);
        padding: 1.2rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    /* فقاعات الشات للمستخدم */
    .chat-user {
        background: #D6EAF8 !important;
        color: #1B4F72 !important;
        border-radius: 16px 16px 4px 16px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 85%;
        margin-left: auto;
        font-size: 0.95rem;
    }
    
    /* فقاعات الشات للذكاء الاصطناعي */
    .chat-ai {
        background: #FFFFFF !important;
        color: #1E293B !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 16px 16px 16px 4px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 85%;
        font-size: 0.95rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    
    /* شارات نسب القبول */
    .badge-high   { background:#1E8449 !important; color:white !important; padding:2px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
    .badge-medium { background:#D4AC0D !important; color:white !important; padding:2px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
    .badge-low    { background:#E67E22 !important; color:white !important; padding:2px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
    
    /* كروت المساعدات */
    .benefit-card {
        background: white !important;
        border-left: 5px solid #2E86C1 !important;
        color: #1E293B !important;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    }
    
    /* بنر إخلاء المسؤولية */
    .disclaimer-banner {
        background: #FEF9E7 !important;
        border: 1px solid #F9E79F !important;
        border-left: 5px solid #F1C40F !important;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.85rem;
        color: #7D6608 !important;
        margin: 1rem 0;
    }
    
    /* بنر الطوارئ */
    .urgency-banner {
        background: #FDEDEC !important;
        border-left: 5px solid #E74C3C !important;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        color: #922B21 !important;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    .checklist-item {
        border-bottom: 1px solid #EBF5FB !important;
        padding: 0.6rem 0;
        font-size: 0.92rem;
        color: #1E293B !important;
    }
    
    .section-label {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #64748B !important;
        text-transform: uppercase;
        margin: 1.2rem 0 0.4rem 0;
    }
    
    /* تعديل صندوق الكتابة ليكون واضحاً ومتناسقاً */
    .stTextArea textarea {
        color: #1E293B !important;
        background-color: #FFFFFF !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True,
)


# ── Session State Init ────────────────────────────────────────────────────────
def init_session():
    defaults = {
        "messages": [],  # Chat history
        "profile": None,  # Agent 1 output
        "benefits": None,  # Agent 2 output
        "action_plan": None,  # Agent 3 output
        "checklist_state": {},  # {step_id: bool}
        "processing": False,
        "stage": "idle",  # idle | extracting | analyzing | planning | done
        "input_key": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session()

# ── Helper: Agent status labels ──────────────────────────────────────────────
STAGE_LABELS = {
    "extracting": "🔍 Agent 1: Reading your situation...",
    "analyzing": "📚 Agent 2: Checking eligibility rules...",
    "planning": "🗂️  Agent 3: Building your action plan...",
    "done": "✅ Your plan is ready!",
}


# ── Helper: Render action plan dashboard ─────────────────────────────────────
def render_dashboard(action_plan: dict, benefits: list):
    # Disclaimer banner
    st.markdown(
        """
    <div class='disclaimer-banner'>
        ⚠️ <strong>Important:</strong> This plan helps you <em>prepare</em> 
        your application. It is NOT an official decision. 
        Final eligibility is determined exclusively by a human 
        government case manager.
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Urgency actions
    if action_plan.get("urgency_actions"):
        st.markdown(
            """
        <div class='urgency-banner'>
            🚨 Immediate steps available — see below first.
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Next best action
    st.info(f"💡 **Start here:** {action_plan['next_best_action']}")

    # Benefits summary strip
    st.markdown(
        "<div class='section-label'>Benefits Assessment</div>", unsafe_allow_html=True
    )

    for b in benefits:
        lk = b["qualification_likelihood"]
        badge_class = {
            "HIGH": "badge-high",
            "MEDIUM": "badge-medium",
            "LOW": "badge-low",
            "UNLIKELY": "badge-low",
        }.get(lk, "badge-low")

        conf_pct = int(b.get("confidence_score", 0) * 100)
        est = b.get("monthly_benefit_estimate", "")
        est_text = f" · Est. **{est}**" if est else ""

        st.markdown(
            f"""
        <div class='benefit-card'>
            <strong>{b["benefit_name"]}</strong> &nbsp;
            <span class='{badge_class}'>{lk}</span> &nbsp;
            <span style='font-size:0.82rem;color:#626567;'>
                Confidence: {conf_pct}%{est_text}
            </span><br/>
            <span style='font-size:0.88rem;color:#444;margin-top:4px;
                         display:block;'>
                {b["plain_language_summary"]}
            </span>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Citations expander
        if b.get("source_citations"):
            with st.expander("📄 Source Citations", expanded=False):
                for c in b["source_citations"]:
                    url = c.get("url", "#")
                    st.markdown(
                        f"- **{c['document_title']}** (p.{c['page_number']}) "
                        f"— {c['excerpt_summary']} "
                        f"[→ View Source]({url})"
                    )

    st.markdown("---")

    # Action plan checklist blocks
    st.markdown(
        "<div class='section-label'>Your Step-by-Step Checklist</div>",
        unsafe_allow_html=True,
    )

    for block in action_plan["benefit_action_blocks"]:
        with st.expander(
            f"📋 {block['benefit_name']} (~{block['estimated_processing_time']})",
            expanded=(block["priority_rank"] == 1),
        ):
            # Deadline warning
            if block.get("deadline_warning"):
                st.warning(f"⏰ {block['deadline_warning']}")

            #
