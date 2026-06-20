# CivicEase AI - Benefits Navigator

CivicEase AI is a multi-agent benefits navigation platform that turns conversational descriptions of a household's situation into structured eligibility signals, policy-grounded benefit assessments, and a practical action plan.

The current production UI is a Flask dashboard with a premium dark-mode interface, asynchronous chat, dynamic benefit cards, source citations, and a 50-state RAG knowledge base.

> Important: CivicEase AI is a benefits preparation and navigation tool. It does not make official eligibility determinations. Final eligibility is decided by the relevant agency or government caseworker.

---

## Features

- Conversational intake for raw, natural-language user situations.
- Multi-agent pipeline:
  - Agent 1 extracts structured intake parameters.
  - Agent 2 evaluates possible benefit matches using RAG policy context.
  - Agent 3 builds a step-by-step action plan.
- Flask API backend with JSON endpoints.
- Premium responsive dashboard built with Tailwind CSS and FontAwesome.
- Defensive frontend rendering with sanitized URLs and safe DOM updates.
- Local Chroma vector database for policy retrieval.
- Expanded 50-state markdown knowledge base with state deep-dive sections.
- Deterministic KB populator script for missing U.S. state sections.
- Legacy Streamlit UI retained under `ui/app.py` for reference.

---

## Tech Stack

- Backend: Flask, Python
- Frontend: HTML, Tailwind CSS CDN, vanilla JavaScript, FontAwesome
- LLM: Groq via `langchain-groq`
- RAG: LangChain, ChromaDB, HuggingFace embeddings
- Validation: Pydantic v2
- Knowledge Base: Markdown files in `data/`

---

## Project Structure

```text
CivicEase-main/
├── app.py                         # Flask app and API routes
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variable template
├── agents/
│   ├── intake_agent.py            # Agent 1: intake extraction
│   ├── policy_agent.py            # Agent 2: RAG-based policy assessment
│   └── action_agent.py            # Agent 3: action plan generation
├── core/
│   └── rag_engine.py              # Chroma DB build/retrieval logic
├── data/
│   ├── civicease_knowledge_base.md
│   └── *.bak-*                    # Timestamped KB backups
├── scripts/
│   └── populate_states.py         # 50-state KB completion script
├── templates/
│   └── index.html                 # Flask dashboard template
├── static/
│   ├── css/app.css                # UI polish and custom CSS
│   └── js/app.js                  # Chat/dashboard frontend logic
├── ui/
│   └── app.py                     # Legacy Streamlit app
└── assets/
```

---

## How the Pipeline Works

1. The user enters a situation in the chat panel.
2. The browser sends the message history to `POST /api/process`.
3. Flask builds a compact conversation context.
4. `run_agent_1()` extracts a validated intake profile:
   - location
   - monthly income
   - household size
   - children ages
   - needs
   - urgency flag
   - missing fields
5. If essential data is missing, the API returns `needs_clarification` and the UI asks a follow-up question.
6. If intake is complete, `run_agent_2()` retrieves relevant policy context from Chroma and returns benefit assessments.
7. `run_agent_3()` converts those assessments into action blocks, checklists, pro tips, and support contacts.
8. The frontend updates the chat and dashboard without refreshing the page.

---

## Setup

> **One required key:** All you need is a free [Groq API key](https://console.groq.com). Everything else is local.

### Option A — Automated Setup (recommended)

**Windows PowerShell:**

```powershell
.\setup.ps1
```

**macOS / Linux:**

```bash
bash setup.sh
```

Both scripts will automatically:
1. Create a Python virtual environment
2. Install all dependencies from `requirements.txt`
3. Copy `.env.example` → `.env`
4. Build the local ChromaDB vector database

Then open `.env` and set your `GROQ_API_KEY`.

---

### Option B — Manual Setup

**1. Create and activate a virtual environment**

Windows PowerShell:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Configure environment variables**

```bash
cp .env.example .env
```

Then open `.env` and fill in:

```env
GROQ_API_KEY=your_groq_api_key_here
```

All other values have sensible defaults and do not need to be changed.

Get a free Groq API key at: https://console.groq.com

---

## Build the RAG Vector Database

The RAG engine reads markdown/text files from `data/` and writes a local Chroma index to `chroma_db/`.

Run this after changing the knowledge base:

```bash
python core/rag_engine.py
```

You should rebuild Chroma after:

- editing `data/civicease_knowledge_base.md`
- running `scripts/populate_states.py`
- adding any new `.md` or `.txt` file to `data/`

---

## Run the Flask App

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Health check:

```text
http://127.0.0.1:5000/health
```

---

## API Reference

### `GET /`

Serves the CivicEase dashboard.

### `GET /health`

Returns:

```json
{"status": "ok"}
```

### `POST /api/process`

Processes the current chat history.

Request body:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "I live in Austin, Texas. I have two kids and make about $2100/month."
    }
  ]
}
```

Possible response statuses:

- `complete`: full profile, benefits, and action plan are available.
- `needs_clarification`: Agent 1 needs more information before policy matching.
- `error`: the backend returned a safe fallback.

Example response shape:

```json
{
  "status": "complete",
  "assistant_message": "I reviewed your situation and found 2 potential program(s)...",
  "profile": {},
  "benefits": [],
  "action_plan": {
    "action_plan_title": "Your Benefits Action Plan",
    "urgency_actions": [],
    "benefit_action_blocks": [],
    "next_best_action": "Gather proof of identity, residence, household size, and income.",
    "support_contacts": []
  }
}
```

---

## Knowledge Base

The primary RAG knowledge base is:

```text
data/civicease_knowledge_base.md
```

It contains:

- Federal baseline program sections.
- 50-state human services agency directory.
- State deep dives for all 50 U.S. states.
- FPL reference anchors.
- National benefits finder resources.

Markdown conventions:

- `##` sections are semantic chunk boundaries.
- `###` sections are sub-chunks.
- State deep dives include hidden metadata comments for retrieval.
- State sections follow this pattern:

```markdown
<!-- chunk: state_deep_dive:TX -->
<!-- metadata: {"state": "TX", "type": "deep_dive"} -->
## State Deep Dive - Texas (TX)

### Texas - SNAP Baseline Mapping (2026)
### Texas - TANF Baseline Mapping (2026)
### Texas - Medicaid Baseline Mapping (2026)
```

---

## Populate Missing State Deep Dives

The script `scripts/populate_states.py` checks whether the KB has a dedicated `## State Deep Dive` section for each of the 50 states.

Dry run:

```bash
python scripts/populate_states.py --dry-run
```

Populate missing sections:

```bash
python scripts/populate_states.py
```

Optional link validation:

```bash
python scripts/populate_states.py --validate-links
```

The script creates a timestamped backup before writing:

```text
data/civicease_knowledge_base.md.bak-YYYYMMDDHHMMSS
```

After running it, rebuild Chroma:

```bash
python core/rag_engine.py
```

---

## Frontend Notes

The dashboard is implemented in:

```text
templates/index.html
static/css/app.css
static/js/app.js
```

UI features:

- Dark navy/slate premium theme.
- Two-column responsive layout.
- Chat panel with AI/user avatars.
- Dynamic top metrics.
- Animated empty state.
- Benefit cards with confidence meters.
- Checklist phase icons.
- Source citation accordions with sanitized external links.
- Friendly error and clarification alerts.

Security-related frontend practices:

- User and model text is inserted with `textContent`, not unsafe HTML.
- URLs are validated with `new URL()` and restricted to `http:`/`https:`.
- External links use `target="_blank"` and `rel="noopener noreferrer"`.

---

## Agent Details

### Agent 1: Intake Agent

File:

```text
agents/intake_agent.py
```

Responsibilities:

- Extract structured profile data from raw conversation.
- Validate output with Pydantic.
- Normalize income and child ages.
- Ask clarification questions when essential fields are missing.
- Return safe fallback output if the LLM fails.

### Agent 2: Policy Agent

File:

```text
agents/policy_agent.py
```

Responsibilities:

- Normalize income for policy reasoning.
- Detect state from user location.
- Retrieve relevant KB chunks through Chroma.
- Produce structured benefit assessments.
- Avoid unsupported claims when RAG context is empty.

### Agent 3: Action Agent

File:

```text
agents/action_agent.py
```

Responsibilities:

- Convert benefit assessments into an action plan.
- Build checklist blocks.
- Add urgency actions when appropriate.
- Return deterministic fallback plans when the LLM fails.

---

## Safety and Compliance Boundaries

CivicEase AI should always frame results as preparation guidance, not official decisions.

Do say:

- "You may qualify."
- "Based on the information provided."
- "Subject to verification."
- "The agency will make the final decision."

Do not say:

- "You are approved."
- "You are guaranteed benefits."
- "You will receive this amount."
- "You are officially eligible."

The application should not collect unnecessary personally identifiable information. Users should avoid entering SSNs, full account numbers, exact street addresses, or private medical records.

---

## Development Commands

Compile Python files:

```bash
python -m py_compile app.py agents/intake_agent.py agents/policy_agent.py agents/action_agent.py core/rag_engine.py scripts/populate_states.py
```

Check frontend JavaScript syntax if Node is available:

```bash
node --check static/js/app.js
```

Run Flask locally:

```bash
python app.py
```

Run the legacy Streamlit UI:

```bash
streamlit run ui/app.py
```

---

## Deployment Notes

For production, do not use Flask's built-in development server. Use a WSGI server such as Gunicorn, Waitress, or uWSGI behind a reverse proxy.

Example with Waitress on Windows:

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 app:app
```

Example with Gunicorn on Linux:

```bash
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

Recommended production settings:

- Set `FLASK_DEBUG=false`.
- Store secrets outside source control.
- Use HTTPS.
- Rebuild Chroma during deployment if KB files changed.
- Monitor LLM/API failures and fallback rates.
- Keep policy data current with official agency sources.

---

## Troubleshooting

### `GROQ_API_KEY is not configured`

Create or update `.env` with a valid Groq API key.

### No benefits appear after submitting a profile

Possible causes:

- Chroma DB was not built after KB changes.
- The user's location or need is too vague.
- Agent 2 could not retrieve relevant policy context.

Fix:

```bash
python core/rag_engine.py
```

Then restart Flask.

### Import errors for LangChain packages

Reinstall dependencies:

```bash
pip install -r requirements.txt
```

### Streamlit watcher logs missing `torchvision`

This can happen when Streamlit scans optional Transformers vision modules. The Flask app is the primary UI and does not require Streamlit file watching.

---

## Data Freshness

The KB includes 2026-oriented screening anchors and state routing data. Public benefit rules can change frequently. Before using this in production, verify:

- Current HHS poverty guidelines.
- Current USDA SNAP state rules and waivers.
- Current TANF state manuals.
- Current Medicaid expansion and eligibility rules.
- Current state portal URLs.

Official references used by the project include:

- USDA SNAP State Directory: https://www.fns.usda.gov/snap/state-directory
- ACF TANF information: https://www.acf.hhs.gov/ofa/programs/tanf
- Medicaid.gov State Overviews: https://www.medicaid.gov/state-overviews/index.html
- HHS Poverty Guidelines: https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines
- Healthcare.gov Medicaid and CHIP: https://www.healthcare.gov/medicaid-chip/

---

## License

See `LICENSE`.

---

## Status

Current app surface: Flask dashboard at `http://127.0.0.1:5000`.

Current KB status: 50 U.S. state deep dives populated.
