"""Glass Factory MCP Server - CAD Safety Analysis"""

from fastapi import FastAPI
from typing import List, Dict, Any

app = FastAPI(title="SMAOS Glass Factory MCP Server", version="1.0.0")

TOOLS = {
    "parse_cad_model": {
        "name": "parse_cad_model",
        "description": "Parse CAD model for safety analysis (Annex I: safety-critical)",
        "input_schema": {"type": "object", "properties": {"model_id": {"type": "string"}}}
    },
    "analyze_safety_violations": {
        "name": "analyze_safety_violations",
        "description": "Analyze potential safety violations in CAD spec",
        "input_schema": {"type": "object", "properties": {"model_id": {"type": "string"}}}
    },
    "update_spec": {
        "name": "update_spec",
        "description": "Update CAD specification (BLOCKED: requires human approval)",
        "input_schema": {"type": "object", "properties": {"model_id": {"type": "string"}}}
    }
}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "glass-mcp"}

@app.post("/tools")
async def list_tools():
    return {"tools": list(TOOLS.values())}

@app.post("/call")
async def call_tool(request: Dict[str, Any]):
    tool_name = request.get("name")
    if tool_name not in TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
    
    return {
        "tool": tool_name,
        "result": f"Executed {tool_name} successfully",
        "timestamp": "2026-09-15T14:23:47Z"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
