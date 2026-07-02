"""agents/execution_agent/server.py — Run execution agent as standalone server on :8084"""
import uvicorn
from agents.execution_agent.agent import ExecutionAgent

if __name__ == "__main__":
    agent = ExecutionAgent()
    print("Starting Execution Agent on :8084")
    uvicorn.run(agent.app, host="0.0.0.0", port=8084, log_level="info")