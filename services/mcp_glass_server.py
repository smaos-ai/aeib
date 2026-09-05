"""
Stream C: Glass Safety Review MCP Server
Port: 8002
Provides tools for glass safety review and compliance verification
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict

from mcp_core import GlassSafetyEngine


class GlassMCPHandler(BaseHTTPRequestHandler):
    """JSON-RPC handler for glass MCP server"""

    glass_tools = {
        "check_safety_policy": {
            "description": "Check safety policy",
            "handler": "check_safety_policy",
        },
        "analyze_safety_risk": {
            "description": "Analyze safety risk",
            "handler": "analyze_safety_risk",
        },
        "approve_safety_review": {
            "description": "Approve safety review",
            "handler": "approve_safety_review",
        },
        "log_safety_decision": {
            "description": "Log safety decision",
            "handler": "log_safety_decision",
        },
    }

    def do_POST(self):
        """Handle JSON-RPC POST requests"""
        if self.path == "/rpc":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                request = json.loads(body.decode())
                response = self.handle_rpc(request)
            except Exception as e:
                response = {"error": str(e), "status": "error"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_error(404)

    def handle_rpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Route JSON-RPC calls to appropriate handler"""
        method = request.get("method")
        params = request.get("params", {})

        if method == "check_safety_policy":
            return GlassSafetyEngine.check_safety_policy(
                params.get("product_id", "unknown"),
                params.get("category", "general"),
            )
        elif method == "analyze_safety_risk":
            return GlassSafetyEngine.analyze_safety_risk(
                params.get("product_id", "unknown"),
                params.get("specs", {}),
            )
        elif method == "approve_safety_review":
            return GlassSafetyEngine.approve_safety_review(
                params.get("product_id", "unknown"),
                params.get("certifications", []),
            )
        elif method == "log_safety_decision":
            return GlassSafetyEngine.log_safety_decision(
                params.get("product_id", "unknown"),
                params.get("decision", "pending"),
            )
        elif method == "list_tools":
            return self.handle_list_tools()
        else:
            return {"error": f"Unknown method: {method}"}

    def handle_list_tools(self) -> Dict[str, Any]:
        """List all available tools"""
        return {
            "tools": list(self.glass_tools.keys()),
            "server": "glass",
            "port": 8002,
        }

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def run_glass_server(port: int = 8002):
    """Start glass MCP server"""
    server = HTTPServer(("127.0.0.1", port), GlassMCPHandler)
    print(f"Glass MCP server running on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Glass MCP server stopped")
        server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
    run_glass_server(port)

