"""agents/triage_agent/server.py — Run triage agent as standalone server on :8081"""
import uvicorn
from agents.triage_agent.agent import TriageAgent

if __name__ == "__main__":
    agent = TriageAgent()
    print("Starting Triage Agent on :8081")
    uvicorn.run(agent.app, host="0.0.0.0", port=8081, log_level="info")