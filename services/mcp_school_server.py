"""
Stream C: School Access Control MCP Server
Port: 8003
Provides tools for school enrollment and access control
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict

from mcp_core import SchoolAccessEngine


class SchoolMCPHandler(BaseHTTPRequestHandler):
    """JSON-RPC handler for school MCP server"""

    school_tools = {
        "check_access_policy": {
            "description": "Check access policy",
            "handler": "check_access_policy",
        },
        "verify_enrollment_eligibility": {
            "description": "Verify enrollment eligibility",
            "handler": "verify_enrollment_eligibility",
        },
        "approve_access_control": {
            "description": "Approve access control",
            "handler": "approve_access_control",
        },
        "log_access_decision": {
            "description": "Log access decision",
            "handler": "log_access_decision",
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

        if method == "check_access_policy":
            return SchoolAccessEngine.check_access_policy(
                params.get("student_id", "unknown"),
                params.get("school_id", "unknown"),
            )
        elif method == "verify_enrollment_eligibility":
            return SchoolAccessEngine.verify_enrollment_eligibility(
                params.get("student_id", "unknown"),
                params.get("grade", "unknown"),
            )
        elif method == "approve_access_control":
            return SchoolAccessEngine.approve_access_control(
                params.get("student_id", "unknown"),
                params.get("school_id", "unknown"),
            )
        elif method == "log_access_decision":
            return SchoolAccessEngine.log_access_decision(
                params.get("student_id", "unknown"),
                params.get("decision", "pending"),
            )
        elif method == "list_tools":
            return self.handle_list_tools()
        else:
            return {"error": f"Unknown method: {method}"}

    def handle_list_tools(self) -> Dict[str, Any]:
        """List all available tools"""
        return {
            "tools": list(self.school_tools.keys()),
            "server": "school",
            "port": 8003,
        }

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def run_school_server(port: int = 8003):
    """Start school MCP server"""
    server = HTTPServer(("127.0.0.1", port), SchoolMCPHandler)
    print(f"School MCP server running on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("School MCP server stopped")
        server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
    run_school_server(port)

