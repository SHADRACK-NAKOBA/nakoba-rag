"""agents/incident_agent/server.py — Run incident agent as standalone server on :8082"""
import uvicorn
from agents.incident_agent.agent import IncidentAgent

if __name__ == "__main__":
    agent = IncidentAgent()
    print("Starting Incident Agent on :8082")
    uvicorn.run(agent.app, host="0.0.0.0", port=8082, log_level="info")