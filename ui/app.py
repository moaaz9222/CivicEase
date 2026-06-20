import os
import sys
from html import escape
from urllib.parse import urlparse

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.action_agent import run_agent_3
from agents.intake_agent import run_agent_1
from agents.policy_agent import run_agent_2

st.set_page_config(
    page_title="CivicEase AI",
    page_icon="CE",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .civicease-header {
        background: linear-gradient(135deg, #1B4F72, #2E86C1);
        color: white;
        padding: 1.2rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .civicease-header div { color: white !important; }
    .chat-user {
        background-color: rgba(46, 134, 193, 0.15);
        border-radius: 8px 8px 2px 8px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 85%;
        margin-left: auto;
        font-size: 0.95rem;
    }
    .chat-ai {
        background-color: rgba(128, 128, 128, 0.1);
        border-radius: 8px 8px 8px 2px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 85%;
        font-size: 0.95rem;
    }
    .badge-high, .badge-medium, .badge-low {
        color:white; padding:2px 10px; border-radius:20px; font-size:0.78rem; font-weight:600;
    }
    .badge-high { background:#1E8449; }
    .badge-medium { background:#A57905; }
    .badge-low { background:#B55314; }
    .benefit-card {
        background-color: rgba(128, 128, 128, 0.05);
        border-left: 5px solid #2E86C1;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    .disclaimer-banner {
        background-color: rgba(241, 196, 15, 0.1);
        border-left: 5px solid #F1C40F;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.85rem;
        margin: 1rem 0;
    }
    .urgency-banner {
        background-color: rgba(231, 76, 60, 0.1);
        border-left: 5px solid #E74C3C;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .checklist-item {
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        padding: 0.6rem 0;
        font-size: 0.92rem;
    }
    .section-label {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 1.2rem 0 0.4rem 0;
        opacity: 0.7;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True,
)

STAGE_LABELS = {
    "extracting": "Agent 1: Reading your situation...",
    "analyzing": "Agent 2: Checking eligibility rules...",
    "planning": "Agent 3: Building your action plan...",
    "done": "Your plan is ready!",
}


def safe_text(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def safe_url(value: object) -> str | None:
    if not value:
        return None
    parsed = urlparse(str(value))
    if parsed.scheme in {"http", "https"}:
        return str(value)
    return None


def init_session() -> None:
    defaults = {
        "messages": [],
        "profile": None,
        "benefits": None,
        "action_plan": None,
        "checklist_state": {},
        "processing": False,
        "stage": "idle",
        "input_key": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session() -> None:
    st.session_state.messages = []
    st.session_state.profile = None
    st.session_state.benefits = None
    st.session_state.action_plan = None
    st.session_state.checklist_state = {}
    st.session_state.processing = False
    st.session_state.stage = "idle"
    st.session_state.input_key += 1


def fallback_action_plan(message: str) -> dict:
    return {
        "action_plan_title": "Your Benefits Action Plan",
        "urgency_actions": [],
        "benefit_action_blocks": [],
        "next_best_action": message,
        "support_contacts": [
            {"name": "2-1-1", "number": "2-1-1", "available": "24/7"}
        ],
    }


def run_pipeline(full_context: str) -> None:
    try:
        st.session_state.stage = "extracting"
        profile = run_agent_1(full_context)
        if not isinstance(profile, dict):
            raise ValueError("Agent 1 returned an invalid profile")

        if profile.get("clarification_needed"):
            st.session_state.messages.append(
                {"role": "assistant", "content": profile["clarification_needed"]}
            )
            st.session_state.profile = profile
            st.session_state.processing = False
            st.session_state.stage = "idle"
            return

        st.session_state.profile = profile
        st.session_state.stage = "analyzing"
        policy_matches = run_agent_2(profile)
        if not isinstance(policy_matches, dict):
            policy_matches = {"matches": []}
        st.session_state.benefits = policy_matches.get("matches", [])

        st.session_state.stage = "planning"
        action_plan = run_agent_3(profile, policy_matches)
        if not isinstance(action_plan, dict):
            action_plan = fallback_action_plan("Gather your documents and review the checklist below.")
        st.session_state.action_plan = action_plan

        benefit_names = ", ".join(
            safe_text(benefit.get("benefit_name", "benefit program"))
            for benefit in st.session_state.benefits
            if isinstance(benefit, dict)
        ) or "local support programs"
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": (
                    f"I reviewed your situation and found {len(st.session_state.benefits)} potential program(s): "
                    f"{benefit_names}. Your action plan is ready on the right."
                ),
            }
        )
        st.session_state.stage = "done"
    except Exception:
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "I could not complete the analysis safely. Please try again in a moment, or contact 2-1-1 for immediate local support.",
            }
        )
        st.session_state.action_plan = fallback_action_plan(
            "Try again in a moment, or contact 2-1-1 for local benefits support."
        )
        st.session_state.stage = "idle"
    finally:
        st.session_state.processing = False


def render_dashboard(action_plan: dict, benefits: list | None) -> None:
    st.markdown(
        """
    <div class='disclaimer-banner'>
        <strong>Important:</strong> This plan helps you prepare your application. It is not an official decision.
        Final eligibility is determined by the relevant agency or case manager.
    </div>
    """,
        unsafe_allow_html=True,
    )

    if action_plan.get("urgency_actions"):
        st.markdown(
            "<div class='urgency-banner'>Immediate steps are available. Review them first.</div>",
            unsafe_allow_html=True,
        )
        for action in action_plan.get("urgency_actions", []):
            st.warning(safe_text(action))

    st.info(f"Start here: {action_plan.get('next_best_action', 'Gather your documents and review the checklist below.')}")

    st.markdown("<div class='section-label'>Benefits Assessment</div>", unsafe_allow_html=True)
    for benefit in benefits or []:
        if not isinstance(benefit, dict):
            continue
        likelihood = str(benefit.get("qualification_likelihood", "LOW")).upper()
        badge_class = {"HIGH": "badge-high", "MEDIUM": "badge-medium"}.get(likelihood, "badge-low")
        try:
            confidence = int(float(benefit.get("confidence_score", 0)) * 100)
        except (TypeError, ValueError):
            confidence = 0
        estimate = safe_text(benefit.get("monthly_benefit_estimate") or "")
        estimate_text = f" - Est. <strong>{estimate}</strong>" if estimate else ""

        st.markdown(
            f"""
        <div class='benefit-card'>
            <strong>{safe_text(benefit.get('benefit_name', 'Benefit program'))}</strong>&nbsp;
            <span class='{badge_class}'>{safe_text(likelihood)}</span>&nbsp;
            <span style='font-size:0.82rem; opacity: 0.8;'>Confidence: {confidence}%{estimate_text}</span><br/>
            <span style='font-size:0.88rem; margin-top:4px; display:block;'>{safe_text(benefit.get('plain_language_summary', 'Review the checklist for next steps.'))}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

        citations = benefit.get("source_citations") or []
        if citations:
            with st.expander("Source Citations", expanded=False):
                for citation in citations:
                    if not isinstance(citation, dict):
                        continue
                    title = safe_text(citation.get("document_title", "Policy document"))
                    page = safe_text(citation.get("page_number", "n/a"))
                    summary = safe_text(citation.get("excerpt_summary", "Retrieved policy excerpt"))
                    url = safe_url(citation.get("url"))
                    if url:
                        st.markdown(f"- **{title}** (p.{page}) - {summary} [View Source]({url})")
                    else:
                        st.markdown(f"- **{title}** (p.{page}) - {summary}")

    st.markdown("---")
    st.markdown("<div class='section-label'>Your Step-by-Step Checklist</div>", unsafe_allow_html=True)

    blocks = action_plan.get("benefit_action_blocks") or []
    if not blocks:
        st.info("No detailed checklist is available yet. Start by gathering proof of identity, residence, household size, and income.")

    for block in blocks:
        if not isinstance(block, dict):
            continue
        title = safe_text(block.get("benefit_name", "Benefit"))
        processing_time = safe_text(block.get("estimated_processing_time", "timeline varies"))
        priority = block.get("priority_rank") == 1
        with st.expander(f"{title} (~{processing_time})", expanded=priority):
            if block.get("deadline_warning"):
                st.warning(safe_text(block["deadline_warning"]))

            for item in block.get("checklist", []):
                if not isinstance(item, dict):
                    continue
                step_id = safe_text(item.get("step_id", item.get("title", "step")))
                st.session_state.checklist_state.setdefault(step_id, False)
                checked = st.checkbox(
                    safe_text(item.get("title", "Checklist step")),
                    value=st.session_state.checklist_state[step_id],
                    key=f"cb_{step_id}",
                )
                st.session_state.checklist_state[step_id] = checked
                resource = safe_url(item.get("resource_url"))
                description = safe_text(item.get("description", ""))
                if resource:
                    st.markdown(f"<div class='checklist-item'>{description}<br/><a href='{resource}' target='_blank'>Open Link</a></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='checklist-item'>{description}</div>", unsafe_allow_html=True)

                office = item.get("local_office")
                if isinstance(office, dict):
                    with st.expander("Local Office Info", expanded=False):
                        st.markdown(
                            f"**{safe_text(office.get('name', 'Local office'))}**  \n"
                            f"{safe_text(office.get('address', ''))}  \n"
                            f"{safe_text(office.get('phone', ''))}  \n"
                            f"{safe_text(office.get('hours', ''))}"
                        )

            if block.get("pro_tip"):
                st.success(f"Pro Tip: {safe_text(block['pro_tip'])}")

    st.markdown("<div class='section-label'>Need Help?</div>", unsafe_allow_html=True)
    for contact in action_plan.get("support_contacts", []):
        if isinstance(contact, dict):
            st.markdown(
                f"**{safe_text(contact.get('name', 'Support'))}:** `{safe_text(contact.get('number', ''))}` - {safe_text(contact.get('available', ''))}"
            )


init_session()

st.markdown(
    """
<div class='civicease-header'>
    <span style='font-size:2rem;'>CE</span>
    <div>
        <div style='font-size:1.4rem;font-weight:700;'>CivicEase AI</div>
        <div style='font-size:0.85rem;opacity:0.85;'>Benefits Navigator - Powered by Multi-Agent AI</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

col_chat, col_dash = st.columns([0.45, 0.55], gap="large")

with col_chat:
    st.markdown("#### Tell Us About Your Situation")
    st.caption("Describe your family, income, location, and what kind of help you need.")

    chat_container = st.container(height=420)
    with chat_container:
        if not st.session_state.messages:
            st.markdown(
                "<div class='chat-ai'>Hello. Tell me a little about your situation, such as where you live, household size, monthly income, and what kind of help you need.</div>",
                unsafe_allow_html=True,
            )
        for msg in st.session_state.messages:
            css_class = "chat-user" if msg.get("role") == "user" else "chat-ai"
            st.markdown(
                f"<div class='{css_class}'>{safe_text(msg.get('content', ''))}</div>",
                unsafe_allow_html=True,
            )

    if st.session_state.processing:
        label = STAGE_LABELS.get(st.session_state.stage, "Working...")
        st.markdown(
            f"<div style='color:#2E86C1;font-size:0.9rem; padding:0.5rem 0;'>{safe_text(label)}</div>",
            unsafe_allow_html=True,
        )
        st.progress({"extracting": 0.25, "analyzing": 0.60, "planning": 0.85, "done": 1.0}.get(st.session_state.stage, 0.0))

    with st.form(key=f"chat_form_{st.session_state.input_key}", clear_on_submit=True):
        user_input = st.text_area(
            "Your message",
            placeholder="Example: I live in Austin, Texas. I have 2 kids ages 4 and 7, and my income is about $2100 a month.",
            height=100,
            label_visibility="collapsed",
            max_chars=6000,
        )
        col_submit, col_reset = st.columns([0.7, 0.3])
        with col_submit:
            submitted = st.form_submit_button("Find My Benefits", use_container_width=True, type="primary")
        with col_reset:
            reset = st.form_submit_button("Start Over", use_container_width=True)

    if reset:
        reset_session()
        st.rerun()

    if submitted and user_input.strip():
        st.session_state.messages.append({"role": "user", "content": user_input.strip()})
        st.session_state.processing = True
        st.session_state.stage = "extracting"
        st.session_state.profile = None
        st.rerun()

if st.session_state.processing and st.session_state.stage == "extracting" and st.session_state.messages:
    full_context = "\n\n".join(
        f"{'User' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content', '')}"
        for msg in st.session_state.messages
    )
    with col_chat:
        with st.status("Analyzing your situation...", expanded=True) as status_box:
            st.write("Agent 1: Extracting intake parameters...")
            run_pipeline(full_context)
            status_box.update(label="Analysis complete", state="complete", expanded=False)
    st.rerun()

with col_dash:
    st.markdown("#### Your Action Plan Dashboard")
    if st.session_state.action_plan is None:
        st.markdown(
            """
        <div style='text-align:center;padding:3rem 1rem; opacity:0.6; border:2px dashed; border-radius:8px;'>
            <div style='font-size:1.2rem;font-weight:700;'>Your personalized action plan will appear here</div>
            <div style='font-size:0.95rem;margin-top:0.5rem;'>Describe your situation to begin.</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        render_dashboard(st.session_state.action_plan, st.session_state.benefits)
