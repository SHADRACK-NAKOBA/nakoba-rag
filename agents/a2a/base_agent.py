"""
agents/a2a/base_agent.py

Base class for all Nakoba A2A sub-agents.
Each sub-agent is a small FastAPI app that:
  - Serves GET /.well-known/agent.json
  - Accepts POST /tasks/send
  - Has its own specialized handle() method

Why separate sub-agents?
  The main orchestrator decomposes complex queries into targeted sub-tasks.
  Each sub-agent has a limited, focused tool set — this reduces hallucination
  because the LLM only sees the tools relevant to its specialty.
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TaskRequest(BaseModel):
    id: str
    message: str
    context: dict[str, Any] = {}
    session_id: str = ""


class TaskResponse(BaseModel):
    task_id: str
    agent_name: str
    status: str
    output: str
    data: dict = {}
    error: str = ""
    timestamp: str = ""


class BaseSubAgent(ABC):
    """Base class for all sub-agents."""

    def __init__(self, name: str, description: str, skills: list[str], port: int):
        self.name = name
        self.description = description
        self.skills = skills
        self.port = port
        self.app = self._build_app()

    def _build_app(self) -> FastAPI:
        app = FastAPI(title=self.name, version="1.0")

        agent_self = self

        @app.get("/.well-known/agent.json")
        def agent_card():
            return {
                "name": agent_self.name,
                "url": f"http://localhost:{agent_self.port}",
                "description": agent_self.description,
                "version": "1.0",
                "skills": agent_self.skills,
                "input_modes": ["text"],
                "output_modes": ["text"],
            }

        @app.post("/tasks/send", response_model=TaskResponse)
        async def handle_task(body: TaskRequest):
            logger.info("[%s] Received task: %s", agent_self.name, body.message[:80])
            try:
                output, data = await agent_self.handle(body.message, body.context)
                return TaskResponse(
                    task_id=body.id, agent_name=agent_self.name,
                    status="completed", output=output, data=data,
                    timestamp=datetime.utcnow().isoformat(),
                )
            except Exception as e:
                logger.error("[%s] Task failed: %s", agent_self.name, e)
                return TaskResponse(
                    task_id=body.id, agent_name=agent_self.name,
                    status="failed", output="", error=str(e),
                    timestamp=datetime.utcnow().isoformat(),
                )

        @app.get("/health")
        def health():
            return {"status": "ok", "agent": agent_self.name, "port": agent_self.port}

        return app

    @abstractmethod
    async def handle(self, message: str, context: dict[str, Any]) -> tuple[str, dict]:
        """
        Process a task and return (output_text, structured_data).
        Implement this in each sub-agent.
        """
        ...