# Nakoba Advanced RAG — Complete Reference Document
## From Zero to Production | Every Step | Every Click | Every Error & Fix

---

## WHAT THIS DOCUMENT COVERS

1. Full local setup from scratch
2. Connecting real Claude (Anthropic API + Vertex AI)
3. Connecting every real source system with live data
4. Moving to your secured company environment (no air-gap)
5. GitLab CI/CD pipeline
6. GCP Cloud Run production deployment
7. Every error hit during build — with exact fix beside it
8. All commands in one reference

---

## PART 1 — LOCAL SETUP FROM SCRATCH

### Prerequisites — install these first

**Python 3.10+**
- Windows: https://python.org/downloads → check "Add to PATH" → Install Now
- Mac: `brew install python@3.11`
- Verify: `python --version` → must show 3.10.x or higher

**Git**
- Windows: https://git-scm.com/download/win → install with defaults
- Mac: `brew install git`
- Verify: `git --version`

**VS Code**
- https://code.visualstudio.com → download → install
- Open VS Code → Ctrl+Shift+X → install "Python" by Microsoft

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/SHADRACK-NAKOBA/nakoba-rag.git
cd nakoba-rag
```

---

### Step 2 — Create virtual environment

```bash
python -m venv .venv

# Activate — Windows Git Bash:
source .venv/Scripts/activate

# Activate — Mac/Linux:
source .venv/bin/activate
```

You should see `(.venv)` at the start of your terminal prompt.

⚠️ **Every time you open a new terminal, run the activate command again.**

---

### Step 3 — Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```

Takes 3-5 minutes.

---

### Step 4 — Create config/.env

```bash
cp config/.env.example config/.env
```

Generate a JWT secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Open `config/.env` and set:
```
APP_ENV=development
LOG_LEVEL=INFO
GCP_PROJECT_ID=local
GCP_REGION=us-central1
VERTEX_CLAUDE_MODEL=claude-sonnet-4-5
VERTEX_CLAUDE_LOCATION=us-east5
VECTOR_STORE_BACKEND=chroma
CHROMA_PERSIST_DIR=./data/chroma_db
MCP_GATEWAY_URL=http://localhost:8080
JWT_SECRET_KEY=PASTE_YOUR_GENERATED_SECRET_HERE
USE_FAKE_REDIS=true
ANTHROPIC_API_KEY=
SERVICENOW_URL=
ZABBIX_URL=
DYNATRACE_URL=
JIRA_URL=
CONFLUENCE_URL=
```

Leave all source system URLs blank for now — demo data is used automatically.

---

### Step 5 — Create data folders

```bash
mkdir -p data/chroma_db data/audit logs
```

---

### Step 6 — Set Windows encoding (prevents emoji errors)

```bash
export PYTHONIOENCODING=utf-8
echo 'export PYTHONIOENCODING=utf-8' >> ~/.bashrc
source ~/.bashrc
```

---

### Step 7 — Seed the knowledge base

```bash
python scripts/seed_demo_data.py
```

Expected output:
```
🌱 Seeding demo data into vector store...
✅ Seeded 10 documents → 10 total in store
```

---

### Step 8 — Run the tests (all 17 must pass)

```bash
GCP_PROJECT_ID=local APP_ENV=development VECTOR_STORE_BACKEND=chroma \
CHROMA_PERSIST_DIR=/tmp/nakoba_test JWT_SECRET_KEY=test-secret \
MCP_GATEWAY_URL=http://localhost:8080 \
python -m pytest tests/test_full_stack.py -v --asyncio-mode=auto
```

Windows Command Prompt:
```cmd
set GCP_PROJECT_ID=local
set APP_ENV=development
set VECTOR_STORE_BACKEND=chroma
set CHROMA_PERSIST_DIR=C:\Temp\nakoba_test
set JWT_SECRET_KEY=test-secret
set MCP_GATEWAY_URL=http://localhost:8080
python -m pytest tests/test_full_stack.py -v --asyncio-mode=auto
```

---

### Step 9 — Start the servers

**Terminal 1 — MCP Gateway:**
```bash
source .venv/Scripts/activate
uvicorn mcp_gateway.gateway:app --host 0.0.0.0 --port 8080
```

Verify: http://localhost:8080/health
Expected: `{"status":"ok","tools_registered":12}`

**Terminal 2 — open a NEW Git Bash window:**
```bash
cd nakoba-rag
source .venv/Scripts/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Verify: http://localhost:8000/health
Expected: `{"status":"ok","vector_store_docs":10}`

---

### Step 10 — Open the UI

Go to: **http://localhost:8000**

Log in:
| Username | Password | Role | Access |
|----------|----------|------|--------|
| admin | admin123 | it_admin | Everything |
| l3user | l3pass | l3_support | Reads + HITL execution |
| l2user | l2pass | l2_support | All read tools |
| l1user | l1pass | l1_support | ServiceNow, Jira, Confluence |
| secuser | secpass | security | SentinelOne, Tenable, Wiz |

---

## PART 2 — CONNECT REAL CLAUDE

### Option A — Anthropic Direct API (Recommended for local dev)

**Every click:**
1. Go to **https://console.anthropic.com**
2. Sign up or sign in
3. Left sidebar → **API Keys**
4. Click **Create Key**
5. Name: `nakoba-dev`
6. Click **Create Key**
7. Copy the key — starts with `sk-ant-...`
8. **NEVER share this key or commit it to git**

Add to `config/.env`:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Add to `config/settings.py` — open the file, find `use_fake_redis: bool = True` and add the line below it:
```python
    anthropic_api_key: str = ""
```

Install the package:
```bash
pip install langchain-anthropic --no-cache-dir
```

Restart both servers. Responses will now be real Claude.

---

### Option B — Claude via Vertex AI (Company environment)

**Step 1 — Install gcloud CLI**
- Windows: https://cloud.google.com/sdk/docs/install
- Run installer → check "Add gcloud to PATH" → Finish
- A terminal opens automatically → follow prompts

**Step 2 — Initialize gcloud**
```bash
gcloud init
```
1. Press Y to log in → browser opens → sign in → Allow
2. Select your project
3. Select default region: us-central1

**Step 3 — Authenticate**
```bash
gcloud auth application-default login
```
Browser opens → sign in → Allow.
Expected: `Credentials saved to file: [...application_default_credentials.json]`

If it opens Edge and fails:
1. Set Chrome as default browser (Windows Settings → Default Apps → Web Browser → Chrome)
2. Run `gcloud auth application-default login` again

**Step 4 — Enable Vertex AI API**
```bash
gcloud services enable aiplatform.googleapis.com
```

**Step 5 — Enable Claude in Model Garden**
1. Go to https://console.cloud.google.com/vertex-ai/model-garden
2. Search: `Claude Sonnet`
3. Click the Claude Sonnet 4.5 card
4. Fill in the business form:
   - Business name: your company
   - Use case: IT Operations Management
   - Industry: Information Technology
   - Intended users: Internal IT engineers
5. Click Submit/Enable
6. ⚠️ MUST use region **us-east5** — Claude is only available there on Vertex

**Step 6 — Upgrade GCP billing**
Free trial accounts have near-zero quota for Claude.
1. https://console.cloud.google.com/billing
2. Click your billing account
3. Click **Upgrade to paid account**
4. Add credit card
5. Click Activate

**Step 7 — Request quota increase**
1. https://console.cloud.google.com/iam-admin/quotas?project=YOUR-PROJECT
2. Filter: `online_prediction_input_tokens_per_minute_per_base_model`
3. Check the Claude Sonnet row
4. Click **Edit Quotas**
5. New limit: `100000`
6. Description: "IT Operations AI agent for internal use"
7. Submit → approved within minutes to 2 hours

**Step 8 — Update config/.env**
```
GCP_PROJECT_ID=your-real-project-id
VERTEX_CLAUDE_MODEL=claude-sonnet-4-5
VERTEX_CLAUDE_LOCATION=us-east5
```

Install Vertex packages:
```bash
pip install google-auth==2.32.0 --no-cache-dir
pip install langchain-google-vertexai==2.0.0 --no-cache-dir
pip install anthropic --no-cache-dir
```

Restart both servers.

---

## PART 3 — CONNECT REAL SOURCE SYSTEMS

For each system:
1. Add credentials to `config/.env`
2. Restart both servers
3. Trigger ingestion to index data into ChromaDB

**Get auth token first:**
```bash
TOKEN=$(curl -s -X POST http://localhost:8080/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | \
  python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

**Trigger ingestion:**
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_systems":["servicenow","jira","confluence"]}'
```

---

### ServiceNow

**In ServiceNow (every click):**
1. Log in as admin
2. Left nav → **System Security** → **Users**
3. Click **New**
4. User ID: `svc-nakoba`
5. First name: `Nakoba` Last name: `Service`
6. Click **Submit**
7. Open the new user → **Roles** tab → Add role: `itil` (read-only)
8. Set a password → **Update**

**In config/.env:**
```
SERVICENOW_URL=https://your-instance.service-now.com
SERVICENOW_USER=svc-nakoba
SERVICENOW_PASS=the-password-you-set
```

What gets indexed: incidents, CMDB configuration items

---

### Jira

**Get Jira API token (every click):**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Label: `nakoba-rag`
4. Click **Create**
5. Copy the token — shown once only

**In config/.env:**
```
JIRA_URL=https://your-org.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_TOKEN=your-copied-token
```

What gets indexed: issues, tickets, project tracking

---

### Confluence

**Get Confluence token:**
Same token as Jira if using Atlassian Cloud (same account).

**In config/.env:**
```
CONFLUENCE_URL=https://your-org.atlassian.net/wiki
CONFLUENCE_TOKEN=your-atlassian-token
```

What gets indexed: KB articles, runbooks, documentation pages

---

### Dynatrace (live API — not indexed, queried in real-time)

**Get Dynatrace API token (every click):**
1. Dynatrace console → left nav → **Access Tokens**
2. Click **Generate new token**
3. Token name: `nakoba-rag`
4. Scopes: ✅ `Read entities` ✅ `Read problems` ✅ `Read metrics`
5. Click **Generate token**
6. Copy it

**In config/.env:**
```
DYNATRACE_URL=https://your-env.live.dynatrace.com
DYNATRACE_TOKEN=your-copied-token
```

What it provides: Active problems, service metrics, response times, error rates, active sessions

---

### Zabbix (live API — not indexed, queried in real-time)

**Get Zabbix API token:**
1. Zabbix web console → **User settings** → **API tokens**
2. Click **Create API token**
3. Name: `nakoba-rag`
4. User: a read-only service account
5. Click **Add**

**In config/.env:**
```
ZABBIX_URL=https://zabbix.your-company.com
ZABBIX_TOKEN=your-zabbix-token
```

What it provides: Host metrics (CPU, memory, disk, network)

---

### SentinelOne (live API — security role required)

**Get SentinelOne API token:**
1. SentinelOne console → top-right avatar → **My User**
2. Click **Generate API Token**
3. Copy it

**In config/.env:**
```
SENTINEL_ONE_URL=https://your-console.sentinelone.net
SENTINEL_ONE_TOKEN=your-token
```

What it provides: Active threats, suspicious processes, endpoint status

---

### Puppet Enterprise (live API + HITL-gated execution)

**Get Puppet token:**
```bash
curl -k -X POST \
  https://puppet.your-company.com:4433/rbac-api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"login":"svc-nakoba","password":"password","lifetime":"1y"}'
```

**In config/.env:**
```
PUPPET_URL=https://puppet.your-company.com:8143
PUPPET_TOKEN=your-puppet-token
```

What it provides: Node state, system facts, task execution (HITL gated)

---

## PART 4 — MOVING TO YOUR SECURED COMPANY ENVIRONMENT

Since your company environment is secured (restricted outbound internet, internal GitLab, internal GCP), here is the correct approach — no air-gap needed.

### The Strategy: Internal GitLab + Internal GCP

Your code stays in Git. Your company environment clones from internal GitLab. Everything runs inside GCP which your company already has.

---

### Step 4.1 — Push to Internal GitLab

From your local machine (which can reach both external GitHub and internal GitLab):

```bash
cd nakoba-rag

# Add internal GitLab as a second remote
git remote add internal https://gitlab.your-company.com/your-team/nakoba-rag.git

# Push to internal GitLab
git push internal main
```

When prompted: use your company GitLab credentials (or LDAP login).

---

### Step 4.2 — In Your Secured Environment: Clone from Internal GitLab

On any machine inside your secured network:

```bash
git clone https://gitlab.your-company.com/your-team/nakoba-rag.git
cd nakoba-rag
```

Follow the same setup steps (Steps 2-8 from Part 1). The only difference is:
- Use your company's internal URLs for all source systems
- Use your company's GCP project instead of `nakoba-rag-poc`
- Secrets come from GCP Secret Manager instead of `.env` file

---

### Step 4.3 — Use GCP Secret Manager for secrets (company requirement)

Instead of `config/.env`, store secrets in GCP Secret Manager:

**Create secrets (every click in GCP Console):**
1. GCP Console → **Secret Manager** → **Create Secret**
2. Name: `nakoba-jwt-secret` → Value: your JWT secret → **Create**
3. Repeat for each secret:
   - `nakoba-anthropic-api-key`
   - `nakoba-servicenow-pass`
   - `nakoba-jira-token`
   - `nakoba-confluence-token`
   - `nakoba-dynatrace-token`

**Grant access:**
```bash
gcloud secrets add-iam-policy-binding nakoba-jwt-secret \
  --member="serviceAccount:nakoba-api@YOUR-PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Read in Python (add to config/settings.py):**
```python
def get_secret(secret_name: str) -> str:
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
```

---

### Step 4.4 — Replace demo data with real company data

1. Connect ServiceNow (Step 3.1 above)
2. Connect Confluence (Step 3.3 above)
3. Connect Jira (Step 3.2 above)
4. Delete demo data and re-seed from real systems:

```bash
rm -rf data/chroma_db
mkdir -p data/chroma_db

# Trigger full ingestion from real systems:
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_systems":["servicenow","jira","confluence"]}'
```

---

## PART 5 — GITLAB CI/CD PIPELINE

Create `.gitlab-ci.yml` in your project root:

```bash
cat > .gitlab-ci.yml << 'EOF'
stages:
  - test
  - deploy

variables:
  PYTHON_VERSION: "3.10"

test:
  stage: test
  image: python:3.10-slim
  variables:
    GCP_PROJECT_ID: local
    APP_ENV: development
    VECTOR_STORE_BACKEND: chroma
    CHROMA_PERSIST_DIR: /tmp/nakoba_test
    JWT_SECRET_KEY: test-secret-ci
    MCP_GATEWAY_URL: http://localhost:8080
  before_script:
    - pip install --upgrade pip
    - pip install -r requirements.txt --no-cache-dir
  script:
    - python -m pytest tests/test_full_stack.py -v --asyncio-mode=auto
  only:
    - main
    - merge_requests

deploy:
  stage: deploy
  image: google/cloud-sdk:latest
  before_script:
    - echo $GCP_SERVICE_ACCOUNT_KEY | base64 -d > /tmp/key.json
    - gcloud auth activate-service-account --key-file=/tmp/key.json
    - gcloud config set project $GCP_PROJECT_ID
  script:
    - gcloud run deploy nakoba-api
        --source .
        --region us-central1
        --platform managed
        --no-allow-unauthenticated
        --set-secrets JWT_SECRET_KEY=nakoba-jwt-secret:latest
        --set-secrets ANTHROPIC_API_KEY=nakoba-anthropic-api-key:latest
        --set-env-vars GCP_PROJECT_ID=$GCP_PROJECT_ID
    - gcloud run deploy nakoba-mcp-gateway
        --source .
        --region us-central1
        --platform managed
        --no-allow-unauthenticated
        --set-secrets JWT_SECRET_KEY=nakoba-jwt-secret:latest
  only:
    - main
  environment:
    name: production
EOF
```

**Set GitLab CI variables (every click):**
1. GitLab → your project → **Settings** → **CI/CD**
2. Expand **Variables**
3. Click **Add variable** for each:
   - `GCP_PROJECT_ID` = your GCP project ID
   - `GCP_SERVICE_ACCOUNT_KEY` = base64-encoded service account JSON

**Create GCP service account:**
```bash
gcloud iam service-accounts create nakoba-ci \
  --display-name="Nakoba CI/CD"

gcloud projects add-iam-policy-binding YOUR-PROJECT \
  --member="serviceAccount:nakoba-ci@YOUR-PROJECT.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR-PROJECT \
  --member="serviceAccount:nakoba-ci@YOUR-PROJECT.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud iam service-accounts keys create key.json \
  --iam-account=nakoba-ci@YOUR-PROJECT.iam.gserviceaccount.com

# Base64 encode for GitLab:
base64 key.json
# Copy output → paste as GCP_SERVICE_ACCOUNT_KEY in GitLab CI variables
```

Commit and push:
```bash
git add .gitlab-ci.yml
git commit -m "ci: add GitLab CI/CD pipeline"
git push origin main
```

Pipeline runs automatically on every push to main.

---

## PART 6 — GCP CLOUD RUN PRODUCTION DEPLOYMENT

### Step 6.1 — Create service accounts

```bash
# API service account
gcloud iam service-accounts create nakoba-api \
  --display-name="Nakoba Chat API"

# MCP Gateway service account
gcloud iam service-accounts create nakoba-gateway \
  --display-name="Nakoba MCP Gateway"

# Grant permissions
gcloud projects add-iam-policy-binding YOUR-PROJECT \
  --member="serviceAccount:nakoba-api@YOUR-PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding YOUR-PROJECT \
  --member="serviceAccount:nakoba-gateway@YOUR-PROJECT.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
```

### Step 6.2 — Deploy MCP Gateway

```bash
gcloud run deploy nakoba-mcp-gateway \
  --source . \
  --region us-central1 \
  --platform managed \
  --no-allow-unauthenticated \
  --service-account nakoba-gateway@YOUR-PROJECT.iam.gserviceaccount.com \
  --set-secrets JWT_SECRET_KEY=nakoba-jwt-secret:latest \
  --set-env-vars GCP_PROJECT_ID=YOUR-PROJECT \
  --memory 1Gi \
  --min-instances 1 \
  --max-instances 10 \
  --port 8080
```

Copy the service URL shown after deployment (e.g. `https://nakoba-mcp-gateway-xxx-uc.a.run.app`)

### Step 6.3 — Deploy Chat API

```bash
gcloud run deploy nakoba-api \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --service-account nakoba-api@YOUR-PROJECT.iam.gserviceaccount.com \
  --set-secrets JWT_SECRET_KEY=nakoba-jwt-secret:latest \
  --set-secrets ANTHROPIC_API_KEY=nakoba-anthropic-api-key:latest \
  --set-env-vars GCP_PROJECT_ID=YOUR-PROJECT \
  --set-env-vars MCP_GATEWAY_URL=https://nakoba-mcp-gateway-xxx-uc.a.run.app \
  --set-env-vars VECTOR_STORE_BACKEND=vertex \
  --memory 2Gi \
  --min-instances 1 \
  --max-instances 20 \
  --port 8000
```

### Step 6.4 — Set up Vertex AI Vector Search (production RAG)

1. GCP Console → **Vertex AI** → **Vector Search** → **+ Create Index**
2. Display name: `nakoba-rag-index`
3. Dimensions: `768`
4. Distance measure: `DOT_PRODUCT_DISTANCE`
5. Click **Create** (takes 15-30 minutes)
6. Once created → **Index Endpoints** → **Create Endpoint**
7. Name: `nakoba-rag-endpoint`
8. Click **Create**
9. Click **Deploy Index** → select your index → **Deploy**

Update config:
```
VECTOR_STORE_BACKEND=vertex
VERTEX_INDEX_ID=your-index-id
VERTEX_ENDPOINT_ID=your-endpoint-id
VERTEX_DEPLOYED_INDEX_ID=your-deployed-index-id
```

### Step 6.5 — Set up BigQuery audit table

```bash
bq mk --dataset YOUR-PROJECT:nakoba_audit

bq mk --table YOUR-PROJECT:nakoba_audit.gateway_events \
  request_id:STRING,user_id:STRING,tool_name:STRING,status:STRING,\
  parameters_json:STRING,result_summary:STRING,error:STRING,timestamp:TIMESTAMP
```

---

## PART 7 — CONNECT SLACK FOR HITL NOTIFICATIONS

**Every click:**
1. Go to **https://api.slack.com/apps**
2. Click **Create New App** → **From scratch**
3. App Name: `Nakoba HITL` → select your workspace → **Create App**
4. Left sidebar → **Incoming Webhooks** → toggle **On**
5. Click **Add New Webhook to Workspace**
6. Choose channel: `#it-ops-approvals`
7. Click **Allow**
8. Copy the Webhook URL

**In config/.env:**
```
HITL_SLACK_WEBHOOK=https://hooks.slack.com/services/T.../B.../...
```

**Approve or deny actions:**
```bash
# Approve:
curl -X POST http://localhost:8080/hitl/approve/HITL-ID \
  -H "Authorization: Bearer $TOKEN"

# Deny:
curl -X POST http://localhost:8080/hitl/deny/HITL-ID \
  -H "Authorization: Bearer $TOKEN"

# Check status:
curl http://localhost:8080/hitl/status/HITL-ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## PART 8 — EVERY ERROR HIT AND HOW IT WAS FIXED

### Error 1 — `cd: too many arguments`
**When:** Trying to cd into folder with spaces
**Command that failed:** `cd Nakoba Advanced Rag`
**Fix:** Quote the path:
```bash
cd "Nakoba Advanced Rag"
```

---

### Error 2 — `OSError: [Errno 2] No such file or directory` during pip install
**When:** Installing packages on Windows with deep AppData path
**Error message:** `Cannot open: C:\\Users\\admin\\AppData\\Local\\Temp\\pip-build-tracker-xxx\\...`
**Fix:**
```bash
export TMPDIR="C:/tmp"
mkdir -p C:/tmp
pip install -r requirements.txt --no-cache-dir
```

---

### Error 3 — pip loops forever on `google-cloud-aiplatform[vectorsearch]`
**When:** Installing requirements.txt that contained `[vectorsearch]` or `[all]` extra
**Symptom:** Terminal prints hundreds of `WARNING: google-cloud-aiplatform X.X does not provide the extra 'all'`
**Fix:** Remove the extra from requirements.txt:
```bash
sed -i 's/google-cloud-aiplatform\[vectorsearch\]/google-cloud-aiplatform/' requirements.txt
```
Or skip GCP packages entirely for local dev and install unpinned:
```bash
pip install langchain langchain-community langchain-google-vertexai langgraph fastapi uvicorn chromadb python-jose passlib google-auth tenacity python-dotenv pytest pytest-asyncio --no-cache-dir
```

---

### Error 4 — Files created in wrong folder
**When:** Creating files after `cd config/` — all subsequent files went into config/ instead of their correct locations
**Symptom:** `find . -name "*.py"` showed `./config/gateway.py`, `./config/agent.py` etc.
**Fix:**
```bash
mv config/agent.py agents/triage_agent/agent.py
mv config/server.py agents/triage_agent/server.py
mv config/coordinator.py agents/a2a/coordinator.py
mv config/base_agent.py agents/a2a/base_agent.py
mv config/audit.py mcp_gateway/audit.py
mv config/hitl.py mcp_gateway/hitl.py
mv config/gateway.py mcp_gateway/gateway.py
mv config/registry.py mcp_gateway/registry.py
mv config/live_sources.py mcp_gateway/tools/live_sources.py
mv config/models.py auth/models.py
mv config/jwt_handler.py auth/jwt_handler.py
mv config/middleware.py auth/middleware.py
mv config/rbac.py auth/rbac.py
mv config/store.py rag/vectorstore/store.py
mv config/retriever.py rag/retrieval/retriever.py
mv config/normalizer.py data_plane/normalization/normalizer.py
mv config/connectors.py data_plane/ingestion/connectors.py
```
**Prevention:** Always run `pwd` before creating a file. Always return to root: `cd ~/Documents/nakoba-rag`

---

### Error 5 — `UnicodeEncodeError: 'charmap' codec can't encode character`
**When:** Running `python scripts/seed_demo_data.py` on Windows
**Error message:** `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f331'`
**Fix:**
```bash
export PYTHONIOENCODING=utf-8
echo 'export PYTHONIOENCODING=utf-8' >> ~/.bashrc
source ~/.bashrc
python scripts/seed_demo_data.py
```

---

### Error 6 — `IndentationError` in test file
**When:** Paste got truncated halfway through `test_hitl_required_for_execution`
**Error message:** `IndentationError: expected an indented block after function definition on line 208`
**Fix:** Open file, scroll to end, find the truncated function, append the missing body:
```bash
# Check where file ends:
tail -15 tests/test_full_stack.py
# Then append the missing content using heredoc
cat >> tests/test_full_stack.py << 'EOF'
    # ... missing content ...
EOF
```

---

### Error 7 — `ModuleNotFoundError: No module named 'langchain_core.pydantic_v1'`
**When:** Starting uvicorn after installing langgraph==0.2.14 with newer langchain-core
**Fix:**
```bash
pip install "langchain-core>=0.3.0" "langgraph>=0.2.28" --no-cache-dir
# Verify:
python -c "from langgraph.graph import END, START, StateGraph; print('OK')"
```

---

### Error 8 — JWT "Invalid or expired token" — token from :8080 rejected by :8000
**When:** Sending chat request to port 8000 after getting token from port 8080
**Root cause:** Zombie uvicorn processes from `--reload` sessions holding OLD `JWT_SECRET_KEY` in `lru_cache` memory. Config file had been updated but old processes never restarted.
**Diagnosis:**
```bash
netstat -ano | grep ":8000"
netstat -ano | grep ":8080"
# Multiple PIDs = zombie processes
```
**Fix:**
```bash
# Kill ALL Python processes:
taskkill //F //IM python.exe
# Wait 10 seconds
# Restart servers WITHOUT --reload:
uvicorn mcp_gateway.gateway:app --host 0.0.0.0 --port 8080
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

### Error 9 — `[Errno 10048] error while attempting to bind on address`
**When:** Starting uvicorn and port is already in use
**Fix:**
```bash
netstat -ano | grep ":8000"
# Get the PID from last column, then:
taskkill //PID XXXX //F
# Wait 5-10 seconds for socket to release
```

---

### Error 10 — `session_id` Pydantic validation error
**When:** Sending chat request from UI — `"Input should be a valid string, input: null"`
**Root cause:** UI was sending `session_id: null` but Pydantic model expected `str`
**Fix in api/main.py:**
```python
from typing import Optional
from pydantic import BaseModel, field_validator

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = ""

    @field_validator("session_id", mode="before")
    @classmethod
    def fix_session(cls, v):
        return v or ""
```

---

### Error 11 — File paste truncated by VS Code editor
**When:** Pasting large files (ui/index.html, graph.py) — content silently dropped after certain point
**Root cause:** Windows CRLF line endings caused silent truncation in editor GUI paste
**Diagnosis:** `tail -5 filename` showed wrong content, `grep -n "expected_function" filename` returned nothing
**Fix:** Use bash heredoc instead of GUI paste:
```bash
cat >> ui/index.html << 'EOF'
... missing content ...
EOF
```
**Verify after every paste:**
```bash
wc -l filename
tail -5 filename
grep -n "key_function" filename
```

---

### Error 12 — `OSError: [WinError 5] Access is denied` during pip install
**When:** pip trying to update `.pyd` files while uvicorn servers are running
**Fix:**
```bash
taskkill //F //IM python.exe
taskkill //F //IM uvicorn.exe
# Wait 5 seconds
pip install package-name --no-cache-dir
```

---

### Error 13 — `pydantic v1/v2 compatibility` — `RuntimeError: error checking inheritance of SafetySettingsType`
**When:** Importing `langchain_google_vertexai==1.0.10` with pydantic v2 installed
**Fix:**
```bash
pip install langchain-google-vertexai==2.0.0 --no-cache-dir
```

---

### Error 14 — Dependency version conflicts between langchain packages
**When:** Trying to pin exact versions — pip resolver fails with `ResolutionImpossible`
**Fix:** Let pip resolve freely without pinning:
```bash
pip install langchain langchain-community langchain-google-vertexai langgraph fastapi uvicorn chromadb python-jose passlib google-auth tenacity python-dotenv pytest pytest-asyncio respx --no-cache-dir
```

---

### Error 15 — Claude on Vertex — `404 Publisher model not found`
**Error:** `Publisher model projects/.../publishers/google/models/claude-sonnet-4-5 was not found`
**Root cause:** `langchain-google-vertexai` was routing to `publishers/google` instead of `publishers/anthropic`
**Fix:** Use `AnthropicVertex` client directly in `agents/llm.py`:
```python
from anthropic import AnthropicVertex
client = AnthropicVertex(project_id=project, region="us-east5")
response = client.messages.create(model="claude-sonnet-4-5", ...)
```

---

### Error 16 — Claude on Vertex — `429 Quota exceeded`
**Error:** `Quota exceeded for aiplatform.googleapis.com/online_prediction_input_tokens_per_minute_per_base_model`
**Root cause 1:** Free trial GCP account has near-zero quota for partner models
**Root cause 2:** Paid account but quota not yet increased from default
**Fix Option A:** Request quota increase:
1. https://console.cloud.google.com/iam-admin/quotas
2. Filter: `online_prediction_input_tokens_per_minute_per_base_model`
3. Check Claude Sonnet row → Edit Quotas → set 100000 → Submit

**Fix Option B (faster):** Use Anthropic direct API:
```
ANTHROPIC_API_KEY=sk-ant-your-key
```

---

### Error 17 — gcloud auth fails — wrong browser opens
**Error:** `There was a problem with web authentication. Try running again with --no-browser`
**Root cause:** gcloud opened Edge, but user was signed into Google in Chrome
**Fix:**
1. Windows Settings → Default Apps → Web Browser → set Chrome
2. Run `gcloud auth application-default login` again

OR:
```bash
gcloud auth application-default login --no-browser
# Copy the URL shown → manually open in Chrome → sign in → copy redirect URL → paste back
```

---

### Error 18 — `git rev-parse --show-toplevel` shows wrong directory
**When:** `git status` showed thousands of unrelated files from home directory
**Root cause:** `git init` was run in `~/Documents` (home area) instead of inside the project folder
**Fix:**
```bash
cd ~/Documents/nakoba-rag
git init
git branch -m main
git remote add origin https://github.com/SHADRACK-NAKOBA/nakoba-rag.git
git rev-parse --show-toplevel
# Must show: C:/Users/admin/Documents/nakoba-rag
```

---

### Error 19 — Anthropic API key accidentally shared publicly
**When:** Pasted `sk-ant-...` key directly into chat
**Fix (immediate):**
1. Go to https://console.anthropic.com/settings/keys
2. Find the key → click **Revoke**
3. Create a new key
4. Update `config/.env` with new key
5. Never paste API keys in chat, emails, or documents

---

### Error 20 — `protobuf` version conflict
**Error:** `google-cloud-aiplatform requires protobuf<7.0.0 but you have protobuf 7.35.1`
**Fix:**
```bash
pip install "protobuf>=3.20.2,<7.0.0" --no-cache-dir --force-reinstall
# Verify:
python -c "import google.protobuf; print(google.protobuf.__version__)"
# Should show 6.x.x
```

---

### Error 21 — ChromaDB telemetry warnings
**When:** Running seed_demo_data.py
**Message:** `Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given`
**Fix:** None needed — completely harmless. ChromaDB's internal telemetry has a version mismatch but it doesn't affect functionality at all.

---

### Error 22 — `git push` rejected — `fetch first`
**Error:** `! [rejected] main -> main (fetch first)`
**When:** Remote repo had commits that local didn't have
**Fix (since this is your repo and you want local to be source of truth):**
```bash
git push -u origin main --force
```

---

## PART 9 — QUICK REFERENCE COMMANDS

```bash
# ── DAILY STARTUP ──────────────────────────────────────────────
# Activate venv (every new terminal)
source .venv/Scripts/activate    # Windows
source .venv/bin/activate         # Mac/Linux

# Check for zombie processes before starting
netstat -ano | grep ":8000"
netstat -ano | grep ":8080"
# Kill if found: taskkill //PID XXXX //F

# Start MCP Gateway (Terminal 1)
cd nakoba-rag && uvicorn mcp_gateway.gateway:app --host 0.0.0.0 --port 8080

# Start Chat API (Terminal 2 - new window)
cd nakoba-rag && uvicorn api.main:app --host 0.0.0.0 --port 8000

# Open UI
# Browser: http://localhost:8000

# ── TESTING ────────────────────────────────────────────────────
GCP_PROJECT_ID=local APP_ENV=development VECTOR_STORE_BACKEND=chroma \
CHROMA_PERSIST_DIR=/tmp/nakoba_test JWT_SECRET_KEY=test-secret \
MCP_GATEWAY_URL=http://localhost:8080 \
python -m pytest tests/test_full_stack.py -v --asyncio-mode=auto

# ── DATA MANAGEMENT ────────────────────────────────────────────
# Re-seed demo data (after wiping):
rm -rf data/chroma_db && mkdir -p data/chroma_db
python scripts/seed_demo_data.py

# Trigger real data ingestion:
TOKEN=$(curl -s -X POST http://localhost:8080/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | \
  python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_systems":["servicenow","jira","confluence"]}'

# ── DIRECT API TESTING ─────────────────────────────────────────
# Get token:
TOKEN=$(curl -s -X POST http://localhost:8080/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | \
  python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Send query:
curl -s -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"How many SSO outages last year?"}' | python -m json.tool

# List tools:
curl http://localhost:8080/tools/list \
  -H "Authorization: Bearer $TOKEN"

# Execute a tool directly:
curl -X POST http://localhost:8080/tools/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tool_name":"servicenow_get_incidents","parameters":{"limit":5}}'

# ── HITL MANAGEMENT ────────────────────────────────────────────
# Approve:
curl -X POST http://localhost:8080/hitl/approve/HITL-ID \
  -H "Authorization: Bearer $TOKEN"

# Deny:
curl -X POST http://localhost:8080/hitl/deny/HITL-ID \
  -H "Authorization: Bearer $TOKEN"

# ── PROCESS MANAGEMENT ─────────────────────────────────────────
# Kill all Python processes:
taskkill //F //IM python.exe         # Windows
pkill -f uvicorn                      # Mac/Linux

# Check ports:
netstat -ano | grep ":8000"           # Windows
lsof -i :8000                         # Mac/Linux

# ── GIT ────────────────────────────────────────────────────────
# Save and push changes:
git add agents/ api/ auth/ config/ data_plane/ mcp_gateway/ rag/ scripts/ tests/ ui/ requirements.txt Dockerfile .gitignore README.md
git commit -m "your description"
git push origin main

# Push to both GitHub and company GitLab:
git push origin main
git push internal main
```

---

## PART 10 — SYSTEM HEALTH CHECKS

Run these to verify everything is working at any time:

```bash
# 1. All packages importable:
python - << 'EOF'
tests = [
    ("LangGraph", "from langgraph.graph import END, START, StateGraph"),
    ("LangChain", "from langchain_core.messages import HumanMessage"),
    ("FastAPI", "import fastapi"),
    ("ChromaDB", "import chromadb"),
    ("Anthropic", "import anthropic"),
    ("google.auth", "import google.auth"),
]
for name, imp in tests:
    try:
        exec(imp)
        print(f"✅ {name}")
    except Exception as e:
        print(f"❌ {name}: {e}")
EOF

# 2. Settings loading correctly:
python -c "from config.settings import get_settings; s=get_settings(); print('Project:', s.gcp_project_id, '| Model:', s.vertex_claude_model)"

# 3. ChromaDB has data:
python -c "from rag.vectorstore.store import get_vector_store; print('Docs in store:', get_vector_store().count())"

# 4. MCP Gateway healthy:
curl -s http://localhost:8080/health | python -m json.tool

# 5. Chat API healthy:
curl -s http://localhost:8000/health | python -m json.tool

# 6. Real Claude responding:
TOKEN=$(curl -s -X POST http://localhost:8080/auth/token -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -X POST http://localhost:8000/chat -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"message":"say hello in 5 words"}' | python -c "import sys,json; r=json.load(sys.stdin); print('Claude says:', r['response'][:100])"
```

---

*Document version 1.0 — Built July 2026*
*Repository: https://github.com/SHADRACK-NAKOBA/nakoba-rag*
