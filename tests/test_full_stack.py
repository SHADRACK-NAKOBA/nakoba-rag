"""
tests/test_full_stack.py
Full stack tests — run without GCP credentials using demo data and stub LLM.
"""
import asyncio
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ["GCP_PROJECT_ID"] = "local"
os.environ["APP_ENV"] = "development"
os.environ["VECTOR_STORE_BACKEND"] = "chroma"
os.environ["CHROMA_PERSIST_DIR"] = "/tmp/nakoba_test_chroma"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["MCP_GATEWAY_URL"] = "http://localhost:8080"


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_jwt_create_and_decode():
    from auth.jwt_handler import create_access_token, decode_token
    token = create_access_token("user1", "user1@test.com", ["l1_support"])
    payload = decode_token(token)
    assert payload["sub"] == "user1"
    assert "l1_support" in payload["roles"]


def test_rbac_hierarchy():
    from auth.models import UserContext
    from auth.rbac import check_role, get_effective_roles
    user = UserContext(user_id="u1", email="u@test.com", roles=["it_admin"])
    effective = get_effective_roles(user)
    assert "l3_support" in effective
    assert "l2_support" in effective
    assert "l1_support" in effective
    assert check_role(user, "l3_support")


def test_rbac_tool_authorization():
    from auth.models import UserContext
    from auth.rbac import is_tool_authorized
    l1 = UserContext(user_id="l1", email="", roles=["l1_support"])
    admin = UserContext(user_id="admin", email="", roles=["it_admin"])

    ok, _ = is_tool_authorized("servicenow_get_incidents", l1)
    assert ok

    ok, reason = is_tool_authorized("puppet_run_task", l1)
    assert not ok
    assert "l3_support" in reason

    ok, _ = is_tool_authorized("puppet_run_task", admin)
    assert ok


# ── Normalization tests ───────────────────────────────────────────────────────

def test_normalize_record_basic():
    from data_plane.normalization.normalizer import normalize_record
    docs = normalize_record(
        raw={"content": "Incident about SSO failure affecting prod", "url": "http://sn/inc1"},
        source_system="servicenow",
        content_field="content",
        url_field="url",
    )
    assert len(docs) >= 1
    assert docs[0].source_system == "servicenow"
    assert docs[0].doc_type == "incident"
    assert "l1_support" in docs[0].rbac_tags


def test_chunking_long_text():
    from data_plane.normalization.normalizer import chunk_text
    long_text = "word " * 400  # 2000 chars
    chunks = chunk_text(long_text, size=500, overlap=50)
    assert len(chunks) > 1
    # Check overlap
    assert chunks[0][-40:].strip()


def test_canonical_entity_id_stable():
    from data_plane.normalization.normalizer import canonical_entity_id
    id1 = canonical_entity_id("prod-web-01")
    id2 = canonical_entity_id("PROD-WEB-01")  # case insensitive
    assert id1 == id2


# ── Vector store tests ────────────────────────────────────────────────────────

def test_chroma_add_and_search():
    import shutil
    shutil.rmtree("/tmp/nakoba_test_chroma", ignore_errors=True)

    from rag.vectorstore.store import ChromaVectorStore, Document
    store = ChromaVectorStore("/tmp/nakoba_test_chroma")

    docs = [
        Document(id="d1", content="SSO login failure affecting Corporate Apps production environment",
                 source_system="servicenow", doc_type="incident"),
        Document(id="d2", content="Vulnerability exception request process via PolicyHub",
                 source_system="confluence", doc_type="kb_article"),
        Document(id="d3", content="CPU and memory metrics for Zabbix monitoring",
                 source_system="zabbix", doc_type="monitoring_metric"),
    ]
    store.add_documents(docs)
    assert store.count() == 3

    results = store.search("SSO authentication outage", top_k=2)
    assert len(results) >= 1


# ── Retriever tests ───────────────────────────────────────────────────────────

def test_retriever_returns_results():
    import shutil
    test_dir = "/tmp/nakoba_retriever_test"
    shutil.rmtree(test_dir, ignore_errors=True)
    os.makedirs(test_dir, exist_ok=True)

    from rag.vectorstore.store import ChromaVectorStore, Document
    from auth.models import UserContext

    store = ChromaVectorStore(test_dir)
    store.add_documents([
        Document(id="r1", content="How to submit a vulnerability exception in PolicyHub step by step",
                 source_system="confluence", doc_type="kb_article",
                 rbac_tags=["l1_support"]),
    ])
    results = store.search("vulnerability exception process", top_k=3)
    assert len(results) >= 1


# ── MCP Gateway tests ─────────────────────────────────────────────────────────

def test_tool_registry_completeness():
    from mcp_gateway.registry import TOOL_REGISTRY
    assert "zabbix_get_metrics" in TOOL_REGISTRY
    assert "servicenow_get_incidents" in TOOL_REGISTRY
    assert "confluence_search" in TOOL_REGISTRY
    assert "puppet_run_task" in TOOL_REGISTRY
    # Execution tools must require HITL
    assert TOOL_REGISTRY["puppet_run_task"].requires_hitl
    assert TOOL_REGISTRY["sentinel_isolate_host"].requires_hitl


@pytest.mark.asyncio
async def test_mcp_gateway_health():
    from httpx import AsyncClient, ASGITransport
    from mcp_gateway.gateway import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_auth_token_endpoint():
    from httpx import AsyncClient, ASGITransport
    from mcp_gateway.gateway import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/auth/token", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_tool_list_requires_auth():
    from httpx import AsyncClient, ASGITransport
    from mcp_gateway.gateway import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/tools/list")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tool_list_with_auth():
    from httpx import AsyncClient, ASGITransport
    from mcp_gateway.gateway import app
    from auth.jwt_handler import create_access_token
    token = create_access_token("admin", "admin@test.com", ["it_admin"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/tools/list", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0


@pytest.mark.asyncio
async def test_tool_execute_demo_servicenow():
    from httpx import AsyncClient, ASGITransport
    from mcp_gateway.gateway import app
    from auth.jwt_handler import create_access_token
    token = create_access_token("admin", "admin@test.com", ["it_admin"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/tools/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"tool_name": "servicenow_get_incidents", "parameters": {"limit": 2}},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["result"] is not None


@pytest.mark.asyncio
async def test_servicenow_incidents_demo_fallback_when_url_blank():
    from mcp_gateway.tools import live_sources
    live_sources.s.servicenow_url = ""
    result = await live_sources.servicenow_get_incidents(limit=2)
    assert result["demo"] is True
    assert "note" not in result
    assert len(result["result"]) >= 1
    assert result["result"][0]["number"].startswith("INC")


@pytest.mark.asyncio
async def test_servicenow_cmdb_demo_fallback_when_url_blank():
    from mcp_gateway.tools import live_sources
    live_sources.s.servicenow_url = ""
    result = await live_sources.servicenow_get_cmdb_ci("prod-web-01")
    assert result["demo"] is True
    assert "note" not in result
    assert result["result"][0]["name"] == "prod-web-01"


@pytest.mark.asyncio
async def test_hitl_required_for_execution():
    from httpx import AsyncClient, ASGITransport
    from mcp_gateway.gateway import app
    from auth.jwt_handler import create_access_token
    token = create_access_token("l3", "l3@test.com", ["l3_support"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/tools/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"tool_name": "puppet_run_task",
                  "parameters": {"node": "prod-web-01", "task": "service::restart", "params": {"service": "nginx"}}},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "hitl_required"
    assert data["hitl_id"] is not None


# ── Chat API tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_api_health():
    from httpx import AsyncClient, ASGITransport
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_chat_requires_auth():
    from httpx import AsyncClient, ASGITransport
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/chat", json={"message": "hello"})
    assert resp.status_code in (401, 403)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])