# app.py
# CivicEase AI — Enterprise Frontend (Rich UI)
# ====================================================

import streamlit as st
import requests
import json

# ── API Configuration ────────────────────────────────────────────────────────
API_URL = "http://127.0.0.1:8000"

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CivicEase AI",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    .civicease-header {
        background: linear-gradient(135deg, #1B4F72, #2E86C1);
        color: white; padding: 1.2rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;
        display: flex; align-items: center; gap: 1rem;
    }
    .civicease-header div { color: white !important; }
    
    .chat-user { background-color: rgba(46, 134, 193, 0.15); border-radius: 16px 16px 4px 16px; padding: 0.75rem 1rem; margin: 0.5rem 0; max-width: 85%; margin-left: auto; font-size: 0.95rem; }
    .chat-ai { background-color: rgba(128, 128, 128, 0.1); border-radius: 16px 16px 16px 4px; padding: 0.75rem 1rem; margin: 0.5rem 0; max-width: 85%; font-size: 0.95rem; }
    
    .badge-high   { background:#1E8449; color:white; padding:2px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
    .badge-medium { background:#D4AC0D; color:white; padding:2px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
    .badge-low    { background:#E67E22; color:white; padding:2px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
    
    .benefit-card { background-color: rgba(128, 128, 128, 0.05); border-left: 5px solid #2E86C1; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1rem; }
    .disclaimer-banner { background-color: rgba(241, 196, 15, 0.1); border-left: 5px solid #F1C40F; border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; margin: 1rem 0; }
    .urgency-banner { background-color: rgba(231, 76, 60, 0.1); border-left: 5px solid #E74C3C; border-radius: 8px; padding: 0.8rem 1rem; font-weight: 600; margin-bottom: 1rem; }
    
    .checklist-item { border-bottom: 1px solid rgba(128, 128, 128, 0.2); padding: 0.6rem 0; font-size: 0.92rem; }
    .section-label { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin: 1.2rem 0 0.4rem 0; opacity: 0.7; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True,
)


# ── Session State Init ────────────────────────────────────────────────────────
def init_session():
    defaults = {
        "messages": [],
        "profile": None,
        "benefits": None,
        "action_plan": None,
        "checklist_state": {},
        "processing": False,
        "input_key": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session()

# ── Live System Monitoring (Sidebar) ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🖥️ Enterprise Monitoring")
    st.markdown("---")
    try:
        health_res = requests.get(f"{API_URL}/api/health", timeout=2)
        if health_res.status_code == 200:
            st.success("🟢 FastAPI Engine: ONLINE")
            st.caption(f"Connected to {API_URL}")
        else:
            st.warning("🟡 FastAPI Engine: DEGRADED")
    except requests.exceptions.ConnectionError:
        st.error("🔴 FastAPI Engine: OFFLINE")
        st.caption("Please start Uvicorn server.")
        st.stop()


# ── Helper: Render action plan dashboard (المعلومات الغنية بالكامل هنا) ──────
def render_dashboard(action_plan: dict, benefits: list):
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

    if action_plan.get("urgency_actions"):
        st.markdown(
            """
        <div class='urgency-banner'>
            🚨 Immediate steps available — see below first.
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.info(f"💡 **Start here:** {action_plan.get('next_best_action', '')}")

    st.markdown(
        "<div class='section-label'>Benefits Assessment</div>", unsafe_allow_html=True
    )

    for b in benefits:
        lk = b.get("qualification_likelihood", "UNLIKELY")
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
            <strong>{b.get("benefit_name", "")}</strong> &nbsp;
            <span class='{badge_class}'>{lk}</span> &nbsp;
            <span style='font-size:0.82rem; opacity: 0.8;'>
                Confidence: {conf_pct}%{est_text}
            </span><br/>
            <span style='font-size:0.88rem; margin-top:4px; display:block;'>
                {b.get("plain_language_summary", "")}
            </span>
        </div>
        """,
            unsafe_allow_html=True,
        )

        if b.get("source_citations"):
            with st.expander("📄 Source Citations", expanded=False):
                for c in b["source_citations"]:
                    url = c.get("url", "#")
                    st.markdown(
                        f"- **{c.get('document_title', '')}** (p.{c.get('page_number', '')}) "
                        f"— {c.get('excerpt_summary', '')} "
                        f"[→ View Source]({url})"
                    )

    st.markdown("---")
    st.markdown(
        "<div class='section-label'>Your Step-by-Step Checklist</div>",
        unsafe_allow_html=True,
    )

    for block in action_plan.get("benefit_action_blocks", []):
        with st.expander(
            f"📋 {block.get('benefit_name', '')} (~{block.get('estimated_processing_time', '')})",
            expanded=(block.get("priority_rank") == 1),
        ):
            if block.get("deadline_warning"):
                st.warning(f"⏰ {block['deadline_warning']}")

            for item in block.get("checklist", []):
                sid = item.get("step_id", "s1")
                if sid not in st.session_state.checklist_state:
                    st.session_state.checklist_state[sid] = False

                cat_icons = {
                    "DOCUMENT": "📄",
                    "ACTION": "✅",
                    "APPOINTMENT": "📅",
                    "LINK": "🔗",
                }
                icon = cat_icons.get(item.get("category", ""), "•")

                col_cb, col_text = st.columns([0.06, 0.94])
                with col_cb:
                    checked = st.checkbox(
                        "", value=st.session_state.checklist_state[sid], key=f"cb_{sid}"
                    )
                    st.session_state.checklist_state[sid] = checked
                with col_text:
                    style = (
                        "text-decoration:line-through; opacity: 0.5;" if checked else ""
                    )
                    link_html = ""
                    if item.get("resource_url"):
                        link_html = f" <a href='{item['resource_url']}' target='_blank' style='font-size:0.82rem;'>→ Open Link</a>"

                    st.markdown(
                        f"<div class='checklist-item' style='{style}'>"
                        f"{icon} <strong>{item.get('title', '')}</strong>{link_html}<br/>"
                        f"<span style='font-size:0.87rem; opacity: 0.8;'>{item.get('description', '')}</span></div>",
                        unsafe_allow_html=True,
                    )

                if item.get("local_office"):
                    lo = item["local_office"]
                    with st.expander("📍 Local Office Info", expanded=False):
                        st.markdown(
                            f"**{lo.get('name', '')}** \n📍 {lo.get('address', '')} \n📞 {lo.get('phone', '')} \n🕐 {lo.get('hours', '')}"
                        )

            if block.get("pro_tip"):
                st.success(f"💡 **Pro Tip:** {block['pro_tip']}")

    st.markdown("<div class='section-label'>Need Help?</div>", unsafe_allow_html=True)
    for contact in action_plan.get("support_contacts", []):
        st.markdown(
            f"📞 **{contact.get('name', '')}:** `{contact.get('number', '')}` — {contact.get('available', '')}"
        )


# ── Main Layout ───────────────────────────────────────────────────────────────
st.markdown(
    """
<div class='civicease-header'>
    <span style='font-size:2rem;'>🏛️</span>
    <div>
        <div style='font-size:1.4rem;font-weight:700;'>CivicEase AI Enterprise</div>
        <div style='font-size:0.85rem;opacity:0.85;'>Decoupled Architecture · Powered by FastAPI Core</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

col_chat, col_dash = st.columns([0.45, 0.55], gap="large")

with col_chat:
    st.markdown("#### 💬 Tell Us About Your Situation")
    st.caption("Describe your family, income, and what kind of help you need.")

    chat_container = st.container(height=420)
    with chat_container:
        if not st.session_state.messages:
            st.markdown(
                "<div class='chat-ai'>👋 Hello! I'm here to help you find benefits and support programs. Describe your situation.</div>",
                unsafe_allow_html=True,
            )
        for msg in st.session_state.messages:
            css_class = "chat-user" if msg["role"] == "user" else "chat-ai"
            st.markdown(
                f"<div class='{css_class}'>{msg['content']}</div>",
                unsafe_allow_html=True,
            )

    with st.form(key=f"chat_form_{st.session_state.input_key}", clear_on_submit=True):
        user_input = st.text_area(
            "Your message",
            placeholder="e.g. I live in Austin Texas, I have 2 kids...",
            height=100,
            label_visibility="collapsed",
        )
        col_submit, col_reset = st.columns([0.7, 0.3])
        with col_submit:
            submitted = st.form_submit_button(
                "🚀 Find My Benefits (via API)",
                use_container_width=True,
                type="primary",
            )
        with col_reset:
            reset = st.form_submit_button("🔄 Reset", use_container_width=True)

    if reset:
        st.session_state.clear()
        init_session()
        st.rerun()

    if submitted and user_input.strip():
        st.session_state.messages.append({"role": "user", "content": user_input})

        # التواصل مع الـ FastAPI
        with st.spinner("🔄 Core Engine is evaluating via Multi-Agent Workflow..."):
            try:
                response = requests.post(
                    f"{API_URL}/api/evaluate", json={"user_input": user_input}
                )
                if response.status_code == 200:
                    data = response.json()

                    st.session_state.profile = data.get("profile")
                    st.session_state.benefits = data.get("benefits", [])
                    st.session_state.action_plan = data.get("action_plan")

                    status = data.get("status")
                    if status == "HUMAN_REVIEW":
                        reply = f"🚨 **FORCED HUMAN REVIEW**\n\n{data.get('message')}"
                    elif status == "NEED_CLARIFICATION":
                        reply = f"🤔 {data.get('message')}"
                    else:
                        reply = f"✅ **Status:** `{status}`\n\nAction plan generated successfully via API."

                    st.session_state.messages.append(
                        {"role": "assistant", "content": reply}
                    )
                else:
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": f"❌ API Error: {response.text}",
                        }
                    )
            except Exception as e:
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"❌ Network Error: {e}"}
                )
        st.rerun()

with col_dash:
    st.markdown("#### 📋 Executive Action Dashboard")
    if st.session_state.action_plan is None:
        st.markdown(
            """
        <div style='text-align:center;padding:3rem 1rem; opacity:0.6; border:2px dashed; border-radius:12px;'>
            <div style='font-size:3rem;'>🗂️</div>
            <div style='font-size:1rem;margin-top:0.5rem;'>
                Waiting for API payload...
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        render_dashboard(st.session_state.action_plan, st.session_state.benefits)
