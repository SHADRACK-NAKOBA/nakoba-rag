# Nakoba Advanced RAG
### AI Agent Framework for IT Operations Management

A production-ready multi-agent AI system that gives IT Operations engineers a single natural language interface to query across all enterprise data sources — ServiceNow, Jira, Confluence, Dynatrace, Zabbix, Puppet, SentinelOne, and more.

Built with LangGraph, LangChain, A2A Protocol, FastAPI, ChromaDB, and Claude Sonnet via Anthropic API.

---

## What This System Does

Ask questions like:
- *"How many SSO outages occurred in the last year?"* → Returns 4 incidents with IDs, dates, durations, root causes, cited from ServiceNow
- *"What CRM systems exist and what applications do they serve?"* → Returns Salesforce, Health Cloud, Dynamics 365 with dependencies
- *"How many apps depend on Legacy MCP for Authorization?"* → Returns 7 apps with migration timelines
- *"Where do I submit a vulnerability exception?"* → Returns 7-step process from Confluence
- *"What OSes are deployed in production?"* → RHEL/Ubuntu/Windows breakdown from Puppet
- *"Restart the auth-service on prod-web-01"* → Triggers HITL approval gate, sends Slack notification

---

## Architecture

```
USER BROWSER
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  Chat API  :8000  (api/main.py)                     │
│  GET /  → serves ui/index.html                      │
│  POST /chat → invokes LangGraph graph               │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│  MAIN ORCHESTRATOR  (agents/main_agent/graph.py)    │
│  LangGraph 6-node stateful graph:                   │
│  1. detect_intent   → classify query type           │
│  2. rag_retrieval   → search ChromaDB               │
│  3. a2a_delegate    → delegate to sub-agents (A2A)  │
│  4. parallel_tools  → live API calls via MCP        │
│  5. reflection      → validate data completeness    │
│  6. synthesis       → Claude writes final answer    │
└──────────────┬──────────────────────────────────────┘
               │  A2A Protocol (HTTP POST /tasks/send)
    ┌──────────┼──────────────────────┐
    ▼          ▼                      ▼            ▼
 :8081      :8082                 :8083         :8084
 Triage     Incident             Knowledge     Execution
 Agent      Agent                Agent         Agent
 (intent,   (ServiceNow,         (RAG,         (HITL-gated
  RAG)       Jira, Dynatrace)     Confluence)   actions)
    └──────────┴──────────────────────┴──────────┘
                    │
     ┌──────────────▼──────────────────────────────┐
     │  MCP GATEWAY  :8080  (mcp_gateway/)         │
     │  JWT auth + RBAC + HITL + Audit + 12 tools  │
     └─────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Claude Sonnet 4.5 via Anthropic API |
| Orchestration | LangGraph + LangChain |
| Agent Protocol | Google A2A (Agent-to-Agent) |
| API Framework | FastAPI + Uvicorn |
| Vector Store | ChromaDB (dev) / Vertex AI Vector Search (prod) |
| Auth | python-jose JWT + OAuth 2.0 |
| Infrastructure | GCP Cloud Run (prod) / local (dev) |

---

## Project Structure

```
nakoba-rag/
├── agents/
│   ├── a2a/
│   │   ├── coordinator.py      # A2A protocol coordinator
│   │   └── base_agent.py       # Base class for all sub-agents
│   ├── main_agent/
│   │   └── graph.py            # LangGraph 6-node orchestrator
│   ├── triage_agent/           # Intent classification + RAG
│   ├── incident_agent/         # ServiceNow + Jira + Dynatrace
│   ├── knowledge_agent/        # RAG + Confluence + CMDB
│   ├── execution_agent/        # HITL-gated IT actions
│   ├── llm.py                  # LLM factory (Anthropic/Vertex/Stub)
│   └── mcp_client.py           # MCP Gateway HTTP client
├── api/
│   └── main.py                 # Chat API + UI serving
├── auth/
│   ├── models.py               # UserContext, TokenResponse
│   ├── jwt_handler.py          # JWT create/decode
│   ├── middleware.py           # FastAPI auth dependency
│   └── rbac.py                 # Role hierarchy + tool authorization
├── config/
│   ├── settings.py             # Pydantic settings loader
│   └── .env.example            # Environment template
├── data_plane/
│   ├── ingestion/connectors.py # ServiceNow, Jira, Confluence connectors
│   └── normalization/          # Entity normalization (Host=CI=Asset)
├── mcp_gateway/
│   ├── gateway.py              # FastAPI MCP Gateway
│   ├── registry.py             # 12 tool definitions
│   ├── tools/live_sources.py   # Live API handlers
│   ├── hitl.py                 # Human-in-the-Loop gate
│   └── audit.py                # Audit logging
├── rag/
│   ├── vectorstore/store.py    # ChromaDB wrapper
│   └── retrieval/retriever.py  # Hybrid retriever + semantic cache
├── scripts/
│   └── seed_demo_data.py       # Loads 9 demo IT documents
├── tests/
│   └── test_full_stack.py      # 17 automated tests
├── ui/
│   └── index.html              # Chat UI (single file, no build step)
├── Dockerfile                  # python:3.10-slim container
└── requirements.txt            # Python dependencies
```

---

## Prerequisites

- Python 3.10.11 or higher
- Git
- VS Code (recommended)
- Windows: Git Bash terminal

---

## Local Setup — Every Step, Every Click

### Step 1 — Clone the repository

```bash
git clone https://github.com/SHADRACK-NAKOBA/nakoba-rag.git
cd nakoba-rag
```

### Step 2 — Create virtual environment

```bash
python -m venv .venv

# Activate:
# Windows Git Bash:
source .venv/Scripts/activate

# Mac/Linux:
source .venv/bin/activate

# You should see (.venv) in your prompt
```

### Step 3 — Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```

**Windows path-length error fix:**
```bash
export TMPDIR="C:/tmp"
mkdir -p C:/tmp
pip install -r requirements.txt --no-cache-dir
```

### Step 4 — Create configuration file

```bash
cp config/.env.example config/.env
```

Open `config/.env` and set:

```bash
APP_ENV=development
GCP_PROJECT_ID=local
VECTOR_STORE_BACKEND=chroma
CHROMA_PERSIST_DIR=./data/chroma_db
MCP_GATEWAY_URL=http://localhost:8080
JWT_SECRET_KEY=   # generate below
ANTHROPIC_API_KEY=  # from console.anthropic.com
```

Generate JWT secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 5 — Create data folders

```bash
mkdir -p data/chroma_db data/audit logs
```

### Step 6 — Seed the knowledge base

```bash
python scripts/seed_demo_data.py
```

Expected:
```
🌱 Seeding demo data into vector store...
✅ Seeded 10 documents → 10 total in store
```

**If you see emoji encoding error on Windows:**
```bash
export PYTHONIOENCODING=utf-8
echo 'export PYTHONIOENCODING=utf-8' >> ~/.bashrc
python scripts/seed_demo_data.py
```

### Step 7 — Run the tests

```bash
GCP_PROJECT_ID=local APP_ENV=development VECTOR_STORE_BACKEND=chroma \
CHROMA_PERSIST_DIR=/tmp/nakoba_test JWT_SECRET_KEY=test-secret \
MCP_GATEWAY_URL=http://localhost:8080 \
python -m pytest tests/test_full_stack.py -v --asyncio-mode=auto
```

Expected: `17 passed`

**If test_tool_execute_demo_servicenow fails:**
```bash
# Blank out SERVICENOW_URL in config/.env:
sed -i 's|SERVICENOW_URL=.*|SERVICENOW_URL=|' config/.env
```

### Step 8 — Start the servers

**Terminal 1 — MCP Gateway:**
```bash
source .venv/Scripts/activate
uvicorn mcp_gateway.gateway:app --host 0.0.0.0 --port 8080
```

Verify: http://localhost:8080/health → `{"status":"ok","tools_registered":12}`

**Terminal 2 (new window) — Chat API:**
```bash
cd nakoba-rag
source .venv/Scripts/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Verify: http://localhost:8000/health → `{"status":"ok","vector_store_docs":10}`

### Step 9 — Open the UI

Go to: **http://localhost:8000**

Login credentials:
| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | it_admin (full access) |
| l3user | l3pass | l3_support |
| l2user | l2pass | l2_support |
| l1user | l1pass | l1_support |
| secuser | secpass | security |

---

## Connect Real Claude (Anthropic API)

1. Go to **https://console.anthropic.com**
2. Sign up → **API Keys** → **Create Key**
3. Copy the key (starts with `sk-ant-...`)
4. Add to `config/.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```
5. Restart both servers

Responses will now be real Claude answers instead of `[STUB LLM]`.

---

## Connect Real Source Systems

For each system, add credentials to `config/.env`, restart servers, then trigger ingestion:

```bash
# Get token:
TOKEN=$(curl -s -X POST http://localhost:8080/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | \
  python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Trigger ingestion:
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_systems":["servicenow","jira","confluence"]}'
```

### ServiceNow
```
SERVICENOW_URL=https://your-instance.service-now.com
SERVICENOW_USER=svc-nakoba
SERVICENOW_PASS=your-password
```

### Jira
```
JIRA_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_TOKEN=your-jira-api-token
```

### Confluence
```
CONFLUENCE_URL=https://your-org.atlassian.net/wiki
CONFLUENCE_TOKEN=your-confluence-token
```

### Dynatrace (live API, not indexed)
```
DYNATRACE_URL=https://your-env.live.dynatrace.com
DYNATRACE_TOKEN=your-dynatrace-token
```

### Zabbix (live API, not indexed)
```
ZABBIX_URL=https://zabbix.your-company.com
ZABBIX_TOKEN=your-zabbix-api-token
```

---

## HITL (Human-in-the-Loop) — Slack Notifications

1. Go to **https://api.slack.com/apps**
2. **Create New App** → From scratch → name: `Nakoba HITL`
3. **Incoming Webhooks** → On → **Add Webhook** → choose channel
4. Copy the webhook URL
5. Add to `config/.env`:
   ```
   HITL_SLACK_WEBHOOK=https://hooks.slack.com/services/...
   ```

When someone requests "restart service on prod-web-01", Slack gets a notification with Approve/Deny instructions.

Approve via API:
```bash
curl -X POST http://localhost:8080/hitl/approve/HITL-ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## Role-Based Access Control

| Role | Tools accessible |
|------|-----------------|
| it_admin | Everything including execution tools |
| l3_support | All reads + HITL-gated execution |
| l2_support | Dynatrace, Puppet reads, all ServiceNow |
| l1_support | ServiceNow incidents, Jira, Confluence |
| security | SentinelOne, Tenable, Wiz |

---

## Production Deployment (GCP Cloud Run)

### Prerequisites
- GCP project with billing enabled
- Vertex AI API enabled
- Claude Sonnet enabled in Model Garden (region: us-east5)

### Deploy
```bash
# Authenticate:
gcloud auth login
gcloud config set project YOUR-PROJECT-ID
gcloud auth application-default login

# Build and deploy:
gcloud run deploy nakoba-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=YOUR-PROJECT-ID

gcloud run deploy nakoba-mcp-gateway \
  --source . \
  --region us-central1 \
  --no-allow-unauthenticated
```

---

## Issues Faced & Fixes

### 1. Python 3.10 on Windows — `cd` with spaces in folder name
**Error:** `bash: cd: too many arguments`
**Fix:** Quote the path: `cd "Nakoba Advanced Rag"`

### 2. pip install fails — Windows path length error
**Error:** `OSError: [Errno 2] No such file or directory: 'C:\\Users\\...very long path...'`
**Fix:**
```bash
export TMPDIR="C:/tmp"
mkdir -p C:/tmp
pip install -r requirements.txt --no-cache-dir
```

### 3. `google-cloud-aiplatform[vectorsearch]` causes infinite resolver loop
**Error:** pip spins forever printing `WARNING: google-cloud-aiplatform X.X does not provide the extra 'all'`
**Fix:** Remove `[vectorsearch]` extra from requirements. Use plain `google-cloud-aiplatform>=1.65.0`

### 4. Files created in wrong folder (config/ instead of project root)
**Cause:** Terminal stayed inside `config/` after creating `config/settings.py`
**Fix:**
```bash
mv config/agent.py agents/triage_agent/agent.py
mv config/gateway.py mcp_gateway/gateway.py
# ... etc for each misplaced file
```
**Prevention:** Always run `pwd` before creating a file. Always `cd ~/Documents/nakoba-rag` to return to root.

### 5. `UnicodeEncodeError` on emoji characters (Windows)
**Error:** `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f331'`
**Fix:**
```bash
export PYTHONIOENCODING=utf-8
echo 'export PYTHONIOENCODING=utf-8' >> ~/.bashrc
source ~/.bashrc
```

### 6. `ModuleNotFoundError: No module named 'langchain_core.pydantic_v1'`
**Cause:** langgraph==0.2.14 incompatible with newer langchain-core
**Fix:**
```bash
pip install "langchain-core>=0.3.0" "langgraph>=0.2.28" --no-cache-dir
```

### 7. JWT "Invalid or expired token" error
**Cause:** Zombie uvicorn processes from earlier `--reload` sessions holding old JWT secret in `lru_cache`
**Fix:**
```bash
# Find processes:
netstat -ano | grep ":8000"
netstat -ano | grep ":8080"
# Kill them:
taskkill //PID XXXX //F
# Then restart servers fresh (without --reload)
```

### 8. Port already in use
**Error:** `[Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)`
**Fix:**
```bash
taskkill //F //IM python.exe
taskkill //F //IM uvicorn.exe
# Wait 10 seconds, then restart
```

### 9. Pasting large files — content gets truncated
**Cause:** VS Code/editor GUI paste drops content silently, especially with CRLF line endings
**Fix:** Use bash heredoc instead of GUI paste:
```bash
cat >> filename.py << 'EOF'
... content ...
EOF
```
Or verify with `tail -5 filename` and `wc -l filename` after every paste.

### 10. `google-cloud-aiplatform[all]` pip resolver conflict
**Cause:** Multiple packages requesting conflicting versions of aiplatform
**Fix:** Let pip resolve freely without pinning:
```bash
# Replace pinned requirements with unpinned:
pip install langchain langchain-community langchain-google-vertexai langgraph fastapi uvicorn chromadb python-jose passlib google-auth tenacity python-dotenv pytest pytest-asyncio --no-cache-dir
```

### 11. Claude on Vertex AI — 404 Publisher model not found
**Error:** `Publisher model projects/.../publishers/google/models/claude-sonnet-4-5 was not found`
**Cause:** Wrong publisher path (`google` instead of `anthropic`)
**Fix:** Use `AnthropicVertex` client directly instead of `ChatVertexAI`

### 12. Claude on Vertex AI — 429 Quota exceeded
**Error:** `Quota exceeded for aiplatform.googleapis.com/online_prediction_input_tokens_per_minute_per_base_model`
**Cause:** Free trial GCP account has near-zero quota for partner models
**Fix options:**
- Request quota increase at: https://console.cloud.google.com/iam-admin/quotas
- OR use Anthropic direct API instead (simpler):
  ```
  ANTHROPIC_API_KEY=sk-ant-your-key
  ```

### 13. `pydantic v1/v2` conflict with langchain-google-vertexai
**Error:** `RuntimeError: error checking inheritance of SafetySettingsType`
**Fix:**
```bash
pip install langchain-google-vertexai==2.0.0 --no-cache-dir
```

### 14. `OSError: [WinError 5] Access is denied` during pip install
**Cause:** Running uvicorn servers lock `.pyd` files preventing pip from updating them
**Fix:** Kill all Python processes first:
```bash
taskkill //F //IM python.exe
taskkill //F //IM uvicorn.exe
# Then retry pip install
```

### 15. API key accidentally committed / shared
**Fix:**
1. Immediately go to https://console.anthropic.com/settings/keys
2. Revoke the exposed key
3. Create a new key
4. Remove from git history:
```bash
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch config/.env' HEAD
```

---

## Quick Reference — All Commands

```bash
# Activate venv (run every time you open a new terminal)
source .venv/Scripts/activate   # Windows
source .venv/bin/activate        # Mac/Linux

# Seed demo data
python scripts/seed_demo_data.py

# Run tests
GCP_PROJECT_ID=local APP_ENV=development VECTOR_STORE_BACKEND=chroma \
CHROMA_PERSIST_DIR=/tmp/nakoba_test JWT_SECRET_KEY=test-secret \
MCP_GATEWAY_URL=http://localhost:8080 \
python -m pytest tests/test_full_stack.py -v --asyncio-mode=auto

# Start MCP Gateway (Terminal 1)
uvicorn mcp_gateway.gateway:app --host 0.0.0.0 --port 8080

# Start Chat API (Terminal 2)
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Get auth token
curl -s -X POST http://localhost:8080/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Send a chat query
curl -s -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"How many SSO outages last year?"}'

# Kill zombie processes (Windows)
taskkill //F //IM python.exe
netstat -ano | grep ":8000"
taskkill //PID XXXX //F

# Push code to GitHub
git add .
git commit -m "your change description"
git push origin main
```

---

## Moving to Company Environment

Since company environments are typically air-gapped:

### Option A — Internal Git server
```bash
git remote add internal https://gitlab.company.com/nakoba-rag.git
git push internal main
```

### Option B — Docker image transfer
```bash
# Build image locally:
docker build -t nakoba-rag:1.0 .
docker save nakoba-rag:1.0 | gzip > nakoba-rag-1.0.tar.gz

# Transfer via approved process, then load:
docker load < nakoba-rag-1.0.tar.gz
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=your-key \
  -e JWT_SECRET_KEY=your-secret \
  nakoba-rag:1.0
```

### What changes in company environment
Only `config/.env` needs updating — same code everywhere:
```bash
ANTHROPIC_API_KEY=your-company-key
SERVICENOW_URL=https://your-internal-sn.company.com
ZABBIX_URL=https://zabbix.internal.company.com
DYNATRACE_URL=https://your-env.internal.dynatrace.com
JWT_SECRET_KEY=strong-random-secret
```

---

## License

Internal use only. Do not distribute outside the organization.404: Not Found
