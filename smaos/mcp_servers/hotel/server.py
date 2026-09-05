"""Hotel MCP Server - Credit Scoring & PMS Integration"""

from fastapi import FastAPI, HTTPException
import json
from typing import List, Dict, Any

app = FastAPI(title="SMAOS Hotel MCP Server", version="1.0.0")

# Available tools
TOOLS = {
    "score_credit": {
        "name": "score_credit",
        "description": "Score guest credit eligibility (Annex III: employment decisions)",
        "input_schema": {"type": "object", "properties": {"guest_id": {"type": "string"}, "income": {"type": "number"}}}
    },
    "fetch_pms_data": {
        "name": "fetch_pms_data",
        "description": "Fetch guest data from Property Management System",
        "input_schema": {"type": "object", "properties": {"guest_id": {"type": "string"}}}
    },
    "check_sanctions": {
        "name": "check_sanctions",
        "description": "Check guest against sanctions lists (requires human oversight)",
        "input_schema": {"type": "object", "properties": {"guest_id": {"type": "string"}}}
    }
}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "hotel-mcp"}

@app.post("/tools")
async def list_tools():
    """Discover available tools"""
    return {"tools": list(TOOLS.values())}

@app.post("/call")
async def call_tool(request: Dict[str, Any]):
    """Execute tool"""
    tool_name = request.get("name")
    
    if tool_name not in TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
    
    # Simulate tool execution
    return {
        "tool": tool_name,
        "result": f"Executed {tool_name} successfully",
        "timestamp": "2026-09-15T14:23:47Z"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
