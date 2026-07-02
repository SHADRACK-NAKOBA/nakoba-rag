"""
api/main.py
Nakoba Advanced RAG — Main Chat API.
Serves the UI at / and handles chat, ingestion, health.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel

from agents.main_agent.graph import get_graph, AgentState
from auth.middleware import get_current_user
from auth.models import UserContext

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nakoba Advanced RAG — Chat API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions: dict[str, list[dict]] = {}

UI_PATH = Path(__file__).parent.parent / "ui" / "index.html"


# ── Serve UI directly from the API ───────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the chat UI at http://localhost:8000"""
    if UI_PATH.exists():
        return HTMLResponse(content=UI_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h2>UI not found — check ui/index.html exists</h2>")


# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent: str
    tool_calls_made: int = 0
    requires_hitl: bool = False
    hitl_ids: list[str] = []
    sources_used: list[str] = []
    timestamp: str


class IngestRequest(BaseModel):
    source_systems: list[str] = ["servicenow", "jira", "confluence"]


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: UserContext = Depends(get_current_user),
):
    session_id = body.session_id or str(uuid.uuid4())
    graph = get_graph()

    # Build history from previous turns
    history_msgs = []
    if session_id in _sessions:
        for h in _sessions[session_id][-10:]:
            history_msgs.append(HumanMessage(content=h["user"]))
            if h.get("assistant"):
                history_msgs.append(AIMessage(content=h["assistant"]))

    initial_state = AgentState(
        messages=history_msgs + [HumanMessage(content=body.message)],
        user_id=user.user_id,
        user_roles=user.roles,
        bearer_token=user.token,
        session_id=session_id,
        intent="",
        sub_intent="",
        entities=[],
        rag_context="",
        a2a_results={},
        tool_results=[],
        requires_hitl=False,
        hitl_ids=[],
        reflection_notes="",
        iteration=0,
        final_response="",
    )

    config = {"configurable": {"thread_id": session_id}}

    try:
        result = await graph.ainvoke(initial_state, config=config)
    except Exception as e:
        logger.error("Graph execution error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({
        "user": body.message,
        "assistant": result.get("final_response", ""),
        "timestamp": datetime.utcnow().isoformat(),
    })

    sources = list({r["tool"] for r in result.get("tool_results", []) if r.get("tool")})
    if result.get("rag_context") and "No relevant context" not in result.get("rag_context", ""):
        sources.append("knowledge_base_rag")

    return ChatResponse(
        response=result.get("final_response", "I was unable to generate a response."),
        session_id=session_id,
        intent=result.get("intent", ""),
        tool_calls_made=len(result.get("tool_results", [])),
        requires_hitl=result.get("requires_hitl", False),
        hitl_ids=result.get("hitl_ids", []),
        sources_used=sources,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/chat/history/{session_id}")
async def get_history(
    session_id: str,
    user: UserContext = Depends(get_current_user),
):
    history = _sessions.get(session_id, [])
    return {"session_id": session_id, "turns": len(history), "history": history}


# ── Ingestion ─────────────────────────────────────────────────────────────────

@app.post("/ingest")
async def trigger_ingestion(
    body: IngestRequest,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
):
    if "it_admin" not in user.roles and "l3_support" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin or L3 role required")

    async def _run():
        from data_plane.ingestion.connectors import run_full_ingestion
        count = await run_full_ingestion()
        logger.info("Ingestion complete: %d chunks", count)

    background_tasks.add_task(_run)
    return {"status": "ingestion_started", "triggered_by": user.user_id,
            "timestamp": datetime.utcnow().isoformat()}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    from rag.vectorstore.store import get_vector_store
    try:
        store = get_vector_store()
        doc_count = store.count() if hasattr(store, "count") else "unknown"
    except Exception:
        doc_count = "unavailable"
    return {
        "status": "ok",
        "service": "nakoba-chat-api",
        "vector_store_docs": doc_count,
        "active_sessions": len(_sessions),
        "timestamp": datetime.utcnow().isoformat(),
    }