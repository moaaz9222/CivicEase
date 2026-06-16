# civicease_app.py
# CivicEase AI — Streamlit Frontend Scaffold
# ============================================

import streamlit as st
import json
import time
from datetime import datetime

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CivicEase AI",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    /* Global */
    .main { background-color: #F7F9FC; }
    
    /* Header */
    .civicease-header {
        background: linear-gradient(135deg, #1B4F72, #2E86C1);
        color: white;
        padding: 1.2rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    /* Chat bubbles */
    .chat-user {
        background: #D6EAF8;
        border-radius: 16px 16px 4px 16px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 85%;
        margin-left: auto;
        font-size: 0.95rem;
    }
    .chat-ai {
        background: #FFFFFF;
        border: 1px solid #D5D8DC;
        border-radius: 16px 16px 16px 4px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 85%;
        font-size: 0.95rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    
    /* Confidence badge */
    .badge-high   { background:#1E8449; color:white; 
                    padding:2px 10px; border-radius:20px; 
                    font-size:0.78rem; font-weight:600; }
    .badge-medium { background:#D4AC0D; color:white; 
                    padding:2px 10px; border-radius:20px; 
                    font-size:0.78rem; font-weight:600; }
    .badge-low    { background:#E67E22; color:white; 
                    padding:2px 10px; border-radius:20px; 
                    font-size:0.78rem; font-weight:600; }
    
    /* Benefit card */
    .benefit-card {
        background: white;
        border-left: 5px solid #2E86C1;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    }
    
    /* Disclaimer banner */
    .disclaimer-banner {
        background: #FEF9E7;
        border: 1px solid #F9E79F;
        border-left: 5px solid #F1C40F;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.85rem;
        color: #7D6608;
        margin: 1rem 0;
    }
    
    /* Urgency banner */
    .urgency-banner {
        background: #FDEDEC;
        border-left: 5px solid #E74C3C;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        color: #922B21;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    /* Checklist item */
    .checklist-item {
        border-bottom: 1px solid #EBF5FB;
        padding: 0.6rem 0;
        font-size: 0.92rem;
    }
    
    /* Divider label */
    .section-label {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #85929E;
        text-transform: uppercase;
        margin: 1.2rem 0 0.4rem 0;
    }
    
    /* Hide Streamlit branding */
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


# ── Agent Stubs (replace with real LangChain/CrewAI calls) ───────────────────
def run_agent_1(user_text: str) -> dict:
    """
    Replace this stub with your actual Agent 1 LangChain call.
    Returns the structured profile JSON.
    """
    # Example stub — remove and wire to LangChain
    return {
        "location": "Travis County, TX",
        "monthly_income": 2100,
        "family_size": 3,
        "children_ages": [4, 7],
        "specific_needs": ["food_assistance", "childcare_support"],
        "language_preference": "English",
        "urgency_flag": False,
        "missing_fields": [],
        "clarification_needed": None,
    }


def run_agent_2(profile: dict) -> list:
    """
    Replace with your actual Agent 2 RAG call (ChromaDB + LangChain).
    Returns benefits assessment array.
    """
    # Stub — remove and wire to RAG chain
    return [
        {
            "benefit_name": "SNAP (Food Assistance)",
            "agency": "USDA / Texas HHS",
            "qualification_likelihood": "HIGH",
            "confidence_score": 0.88,
            "plain_language_summary": (
                "Based on what you shared, your family may qualify for "
                "SNAP food benefits. A family of 3 earning around $2,100/month "
                "in Texas is likely within the income limits."
            ),
            "qualifying_reasons": [
                "Household income appears to be at or below 130% of the "
                "federal poverty line",
                "Family size of 3 meets standard household definition",
            ],
            "disqualifying_risks": [
                "Any unreported income or assets could affect eligibility"
            ],
            "source_citations": [
                {
                    "document_title": "SNAP Eligibility Manual — Texas HHS",
                    "page_number": 14,
                    "excerpt_summary": "Gross income limit for a 3-person "
                    "household is $2,311/month (FY2024)",
                    "url": "https://www.hhs.texas.gov/snap",
                }
            ],
            "monthly_benefit_estimate": "$535–$568 / month",
        },
        {
            "benefit_name": "Child Care Assistance Program (CCAP)",
            "agency": "Texas Workforce Commission",
            "qualification_likelihood": "MEDIUM",
            "confidence_score": 0.65,
            "plain_language_summary": (
                "Your family may qualify for childcare cost assistance. "
                "This program helps cover daycare or afterschool care "
                "for children under 13."
            ),
            "qualifying_reasons": [
                "Children ages 4 and 7 are within the eligible age range",
                "Income may fall within the subsidy threshold",
            ],
            "disqualifying_risks": [
                "Wait lists are active in many Texas counties",
                "Requires proof of work/school enrollment",
            ],
            "source_citations": [
                {
                    "document_title": "TWC Child Care Assistance Guide 2024",
                    "page_number": 3,
                    "excerpt_summary": "Families must have income at or below "
                    "85% of State Median Income",
                    "url": "https://www.twc.texas.gov/childcare",
                }
            ],
            "monthly_benefit_estimate": "Up to $800/month per child",
        },
    ]


def run_agent_3(profile: dict, benefits: list) -> dict:
    """
    Replace with your actual Agent 3 orchestration call.
    Returns the full action plan JSON.
    """
    # Stub — remove and wire to LangChain
    return {
        "action_plan_title": "Your Benefits Action Plan",
        "next_best_action": (
            "Start your SNAP application online today — it takes "
            "about 20 minutes and you can save your progress."
        ),
        "urgency_actions": [],
        "benefit_action_blocks": [
            {
                "benefit_name": "SNAP (Food Assistance)",
                "priority_rank": 1,
                "estimated_processing_time": "30 days",
                "checklist": [
                    {
                        "step_id": "SNAP_S1",
                        "category": "DOCUMENT",
                        "title": "Gather proof of income",
                        "description": "Last 30 days of pay stubs or employer letter.",
                        "is_completed": False,
                        "resource_url": None,
                        "local_office": None,
                    },
                    {
                        "step_id": "SNAP_S2",
                        "category": "DOCUMENT",
                        "title": "Gather ID for all household members",
                        "description": "Driver's license or state ID "
                        "for adults; birth certificates "
                        "for children.",
                        "is_completed": False,
                        "resource_url": None,
                        "local_office": None,
                    },
                    {
                        "step_id": "SNAP_S3",
                        "category": "LINK",
                        "title": "Start your SNAP application",
                        "description": "Apply online via Your Texas Benefits portal.",
                        "is_completed": False,
                        "resource_url": "https://yourtexasbenefits.hhs.texas.gov",
                        "local_office": None,
                    },
                    {
                        "step_id": "SNAP_S4",
                        "category": "APPOINTMENT",
                        "title": "Schedule your eligibility interview",
                        "description": "Required interview — can be done by phone.",
                        "is_completed": False,
                        "resource_url": "https://www.hhs.texas.gov/snap",
                        "local_office": {
                            "name": "Travis County HHS Office",
                            "address": "1000 E 41st St, Austin, TX 78751",
                            "phone": "2-1-1",
                            "hours": "Mon–Fri, 8am–5pm",
                        },
                    },
                ],
                "pro_tip": (
                    "Apply even if you're unsure — a caseworker will "
                    "confirm your eligibility. Applying costs nothing."
                ),
                "deadline_warning": None,
            },
            {
                "benefit_name": "Child Care Assistance (CCAP)",
                "priority_rank": 2,
                "estimated_processing_time": "45–90 days (waitlist possible)",
                "checklist": [
                    {
                        "step_id": "CCAP_S1",
                        "category": "ACTION",
                        "title": "Find your local Workforce Board",
                        "description": "CCAP is managed locally — "
                        "find your county board first.",
                        "is_completed": False,
                        "resource_url": (
                            "https://www.twc.texas.gov/jobseekers/"
                            "childcare-financial-assistance"
                        ),
                        "local_office": None,
                    },
                    {
                        "step_id": "CCAP_S2",
                        "category": "DOCUMENT",
                        "title": "Prepare work/school proof",
                        "description": "Recent pay stubs AND school enrollment letter.",
                        "is_completed": False,
                        "resource_url": None,
                        "local_office": None,
                    },
                ],
                "pro_tip": (
                    "Get on the waitlist now even if you're not ready "
                    "to apply — your spot is based on signup date."
                ),
                "deadline_warning": (
                    "Waitlists open and close — check your local board monthly."
                ),
            },
        ],
        "support_contacts": [
            {
                "name": "Texas Benefits Helpline",
                "number": "2-1-1",
                "available": "24/7",
            }
        ],
    }


# ── Helper: Agent status display ─────────────────────────────────────────────
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

            # Checklist items
            for item in block["checklist"]:
                sid = item["step_id"]
                if sid not in st.session_state.checklist_state:
                    st.session_state.checklist_state[sid] = False

                cat_icons = {
                    "DOCUMENT": "📄",
                    "ACTION": "✅",
                    "APPOINTMENT": "📅",
                    "LINK": "🔗",
                }
                icon = cat_icons.get(item["category"], "•")

                col_cb, col_text = st.columns([0.06, 0.94])
                with col_cb:
                    checked = st.checkbox(
                        "",
                        value=st.session_state.checklist_state[sid],
                        key=f"cb_{sid}",
                    )
                    st.session_state.checklist_state[sid] = checked
                with col_text:
                    style = (
                        "text-decoration:line-through;color:#AAB7B8;" if checked else ""
                    )
                    link_html = ""
                    if item.get("resource_url"):
                        link_html = (
                            f" <a href='{item['resource_url']}' "
                            f"target='_blank' "
                            f"style='font-size:0.82rem;'>→ Open Link</a>"
                        )
                    st.markdown(
                        f"<div class='checklist-item' style='{style}'>"
                        f"{icon} <strong>{item['title']}</strong>"
                        f"{link_html}<br/>"
                        f"<span style='color:#5D6D7E;font-size:0.87rem;'>"
                        f"{item['description']}</span></div>",
                        unsafe_allow_html=True,
                    )

                # Local office info
                if item.get("local_office"):
                    lo = item["local_office"]
                    with st.expander("📍 Local Office Info", expanded=False):
                        st.markdown(
                            f"**{lo['name']}**  \n"
                            f"📍 {lo['address']}  \n"
                            f"📞 {lo['phone']}  \n"
                            f"🕐 {lo['hours']}"
                        )

            # Pro tip
            if block.get("pro_tip"):
                st.success(f"💡 **Pro Tip:** {block['pro_tip']}")

    # Support contacts
    st.markdown("<div class='section-label'>Need Help?</div>", unsafe_allow_html=True)
    for contact in action_plan.get("support_contacts", []):
        st.markdown(
            f"📞 **{contact['name']}:** `{contact['number']}` — {contact['available']}"
        )


# ── Main Layout ───────────────────────────────────────────────────────────────
# Header
st.markdown(
    """
<div class='civicease-header'>
    <span style='font-size:2rem;'>🏛️</span>
    <div>
        <div style='font-size:1.4rem;font-weight:700;'>CivicEase AI</div>
        <div style='font-size:0.85rem;opacity:0.85;'>
            Benefits Navigator · Powered by Multi-Agent AI
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# Two-column split
col_chat, col_dash = st.columns([0.45, 0.55], gap="large")

# ── LEFT: Chat Interface ──────────────────────────────────────────────────────
with col_chat:
    st.markdown("#### 💬 Tell Us About Your Situation")
    st.caption(
        "Describe your family, income, and what kind of help you need — "
        "in your own words. Everything is confidential."
    )

    # Chat history display
    chat_container = st.container(height=420)
    with chat_container:
        if not st.session_state.messages:
            st.markdown(
                "<div class='chat-ai'>👋 Hello! I'm here to help you find "
                "benefits and support programs your family may qualify for."
                "<br/><br/>Just tell me a little about your situation — "
                "things like where you live, how many people are in your "
                "household, your approximate monthly income, and what "
                "kind of help you're looking for (food, childcare, "
                "job training, etc.)."
                "<br/><br/>There's no wrong way to say it.</div>",
                unsafe_allow_html=True,
            )
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f"<div class='chat-user'>{msg['content']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div class='chat-ai'>{msg['content']}</div>",
                    unsafe_allow_html=True,
                )

    # Processing status
    if st.session_state.processing:
        stage = st.session_state.stage
        st.markdown(
            f"<div style='color:#2E86C1;font-size:0.9rem;"
            f"padding:0.5rem 0;'>"
            f"{STAGE_LABELS.get(stage, '...')}</div>",
            unsafe_allow_html=True,
        )
        progress_map = {
            "extracting": 0.25,
            "analyzing": 0.60,
            "planning": 0.85,
            "done": 1.0,
        }
        st.progress(progress_map.get(stage, 0.0))

    # Input form
    with st.form(key=f"chat_form_{st.session_state.input_key}", clear_on_submit=True):
        user_input = st.text_area(
            "Your message",
            placeholder=(
                "e.g. I live in Austin Texas, I have 2 kids aged 4 and 7, "
                "my income is about $2100 a month, and I need help with food "
                "and childcare..."
            ),
            height=100,
            label_visibility="collapsed",
        )
        col_submit, col_reset = st.columns([0.7, 0.3])
        with col_submit:
            submitted = st.form_submit_button(
                "🚀 Find My Benefits",
                use_container_width=True,
                type="primary",
            )
        with col_reset:
            reset = st.form_submit_button(
                "🔄 Start Over",
                use_container_width=True,
            )

    # Reset logic
    if reset:
        for key in [
            "messages",
            "profile",
            "benefits",
            "action_plan",
            "checklist_state",
        ]:
            st.session_state[key] = (
                [] if key in ("messages", "checklist_state") else None
            )
        st.session_state.stage = "idle"
        st.session_state.processing = False
        st.session_state.input_key += 1
        st.rerun()

    # Submit logic — runs the 3-agent pipeline
    if submitted and user_input.strip():
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.processing = True

        # --- Agent 1 ---
        st.session_state.stage = "extracting"
        st.rerun()  # Show progress before blocking call

# NOTE: Agent calls continue after rerun via stage checks below
if (
    st.session_state.processing
    and st.session_state.stage == "extracting"
    and st.session_state.profile is None
    and st.session_state.messages
):
    last_user_msg = next(
        (
            m["content"]
            for m in reversed(st.session_state.messages)
            if m["role"] == "user"
        ),
        "",
    )
    profile = run_agent_1(last_user_msg)
    st.session_state.profile = profile

    if profile.get("clarification_needed"):
        # Agent 1 needs more info — ask user
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"🤔 {profile['clarification_needed']}",
            }
        )
        st.session_state.processing = False
        st.session_state.stage = "idle"
        st.rerun()
    else:
        st.session_state.stage = "analyzing"
        st.rerun()

if (
    st.session_state.processing
    and st.session_state.stage == "analyzing"
    and st.session_state.profile is not None
    and st.session_state.benefits is None
):
    benefits = run_agent_2(st.session_state.profile)
    st.session_state.benefits = benefits
    st.session_state.stage = "planning"
    st.rerun()

if (
    st.session_state.processing
    and st.session_state.stage == "planning"
    and st.session_state.benefits is not None
    and st.session_state.action_plan is None
):
    action_plan = run_agent_3(
        st.session_state.profile,
        st.session_state.benefits,
    )
    st.session_state.action_plan = action_plan

    benefit_names = ", ".join(b["benefit_name"] for b in st.session_state.benefits)
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": (
                f"✅ I've analyzed your situation and found **"
                f"{len(st.session_state.benefits)} potential benefit programs** "
                f"your family may qualify for: **{benefit_names}**.\n\n"
                f"Your personalized action plan is ready on the right. "
                f"Remember — this plan prepares your application; a government "
                f"caseworker makes the final decision. "
                f"You've got this! 💪"
            ),
        }
    )
    st.session_state.processing = False
    st.session_state.stage = "done"
    st.rerun()


# ── RIGHT: Dashboard ──────────────────────────────────────────────────────────
with col_dash:
    st.markdown("#### 📋 Your Action Plan Dashboard")

    if st.session_state.action_plan is None:
        st.markdown(
            """
        <div style='text-align:center;padding:3rem 1rem;
                    color:#AAB7B8;border:2px dashed #D5D8DC;
                    border-radius:12px;'>
            <div style='font-size:3rem;'>🗂️</div>
            <div style='font-size:1rem;margin-top:0.5rem;'>
                Your personalized action plan will appear here<br/>
                after you describe your situation.
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        render_dashboard(
            st.session_state.action_plan,
            st.session_state.benefits,
        )
