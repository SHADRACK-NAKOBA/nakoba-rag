"""agents/knowledge_agent/server.py — Run knowledge agent as standalone server on :8083"""
import uvicorn
from agents.knowledge_agent.agent import KnowledgeAgent

if __name__ == "__main__":
    agent = KnowledgeAgent()
    print("Starting Knowledge Agent on :8083")
    uvicorn.run(agent.app, host="0.0.0.0", port=8083, log_level="info")