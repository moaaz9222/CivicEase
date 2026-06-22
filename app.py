import logging
import os
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from agents.action_agent import run_agent_3
from agents.intake_agent import run_agent_1
from agents.policy_agent import run_agent_2
from core.background_ingestion import start_background_ingestion_scheduler

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
_INGESTION_SCHEDULER = None

MAX_MESSAGE_CHARS = 6000
MAX_CONTEXT_CHARS = 14000
ALLOWED_ROLES = {"user", "assistant"}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())
    app.config["JSON_SORT_KEYS"] = False
    _maybe_start_background_ingestion()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/process")
    def process_message():
        payload = request.get_json(silent=True) or {}
        messages = _normalize_messages(payload.get("messages"))

        if not messages:
            return jsonify(_error_response("Please tell us a little about your situation to begin.")), 400

        full_context = _build_context(messages)
        try:
            profile = run_agent_1(full_context)
            if not isinstance(profile, dict):
                raise ValueError("Agent 1 returned a non-object profile")

            if profile.get("clarification_needed"):
                return jsonify(
                    {
                        "status": "needs_clarification",
                        "assistant_message": str(profile["clarification_needed"]),
                        "profile": _json_safe(profile),
                        "benefits": [],
                        "action_plan": _empty_action_plan(
                            "Answer the clarification question so we can check benefits accurately."
                        ),
                    }
                )

            policy_matches = run_agent_2(profile)
            if not isinstance(policy_matches, dict):
                policy_matches = {"matches": []}
            benefits = policy_matches.get("matches", [])

            action_plan = run_agent_3(profile, policy_matches)
            if not isinstance(action_plan, dict):
                action_plan = _empty_action_plan("Gather core documents and contact 2-1-1 for local support.")

            benefit_names = [
                str(item.get("benefit_name", "benefit program"))
                for item in benefits
                if isinstance(item, dict)
            ]
            assistant_message = _summary_message(benefit_names)

            return jsonify(
                {
                    "status": "complete",
                    "assistant_message": assistant_message,
                    "profile": _json_safe(profile),
                    "benefits": _json_safe(_sanitize_benefits(benefits)),
                    "action_plan": _json_safe(_sanitize_action_plan(action_plan)),
                }
            )
        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            return jsonify(_error_response("We could not complete the analysis safely. Please try again.")), 500

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def _maybe_start_background_ingestion() -> None:
    global _INGESTION_SCHEDULER
    if _INGESTION_SCHEDULER is not None:
        return
    if os.getenv("FLASK_DEBUG", "false").lower() == "true" and os.getenv("WERKZEUG_RUN_MAIN") != "true":
        return
    _INGESTION_SCHEDULER = start_background_ingestion_scheduler()


def _normalize_messages(raw_messages: Any) -> list[dict[str, str]]:
    if not isinstance(raw_messages, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in raw_messages[-12:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user")).lower()
        if role not in ALLOWED_ROLES:
            role = "user"
        content = str(item.get("content", "")).strip()[:MAX_MESSAGE_CHARS]
        if content:
            normalized.append({"role": role, "content": content})
    return normalized


def _build_context(messages: list[dict[str, str]]) -> str:
    context = "\n\n".join(
        f"{'User' if item['role'] == 'user' else 'Assistant'}: {item['content']}"
        for item in messages
    )
    return context[-MAX_CONTEXT_CHARS:]


def _summary_message(benefit_names: list[str]) -> str:
    if not benefit_names:
        return "I prepared a safe starter plan. I could not verify specific programs from the current policy context."
    joined = ", ".join(benefit_names[:5])
    return f"I reviewed your situation and found {len(benefit_names)} potential program(s): {joined}. Review the action dashboard for next steps."


def _empty_action_plan(next_action: str) -> dict[str, Any]:
    return {
        "action_plan_title": "Your Benefits Action Plan",
        "urgency_actions": [],
        "benefit_action_blocks": [],
        "next_best_action": next_action,
        "support_contacts": [
            {"name": "2-1-1", "number": "2-1-1", "available": "24/7"}
        ],
    }


def _error_response(message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "assistant_message": message,
        "profile": {},
        "benefits": [],
        "action_plan": _empty_action_plan("Try again in a moment, or contact 2-1-1 for local benefits support."),
    }


def _sanitize_url(value: Any) -> str | None:
    if not value:
        return None
    url = str(value).strip()
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return url
    return None


def _sanitize_benefits(benefits: list[Any]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in benefits:
        if not isinstance(item, dict):
            continue
        citations = []
        for citation in item.get("source_citations") or []:
            if not isinstance(citation, dict):
                continue
            citations.append(
                {
                    "document_title": str(citation.get("document_title", "Policy document")),
                    "page_number": citation.get("page_number"),
                    "excerpt_summary": str(citation.get("excerpt_summary", "Retrieved policy excerpt")),
                    "url": _sanitize_url(citation.get("url")),
                }
            )
        cleaned.append({**item, "source_citations": citations})
    return cleaned


def _sanitize_action_plan(action_plan: dict[str, Any]) -> dict[str, Any]:
    blocks = []
    for block in action_plan.get("benefit_action_blocks") or []:
        if not isinstance(block, dict):
            continue
        checklist = []
        for step in block.get("checklist") or []:
            if not isinstance(step, dict):
                continue
            checklist.append({**step, "resource_url": _sanitize_url(step.get("resource_url"))})
        blocks.append({**block, "checklist": checklist})
    return {**action_plan, "benefit_action_blocks": blocks}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
