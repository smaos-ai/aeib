"""
Stream C: Czech Government APIs (gov.cz) MCP Server
Port: 8004
Provides tools for Czech government citizen verification and compliance
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict

from mcp_core import GovCzEngine


class GovCzMCPHandler(BaseHTTPRequestHandler):
    """JSON-RPC handler for gov.cz MCP server"""

    govcz_tools = {
        "verify_citizen": {
            "description": "Verify Czech citizen via gov.cz",
            "handler": "verify_citizen",
        },
        "check_regulatory_compliance": {
            "description": "Check regulatory compliance",
            "handler": "check_regulatory_compliance",
        },
        "get_business_registration": {
            "description": "Get business registration from gov.cz",
            "handler": "get_business_registration",
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

        if method == "verify_citizen":
            return GovCzEngine.verify_citizen(
                params.get("citizen_id", "unknown"),
                params.get("date_of_birth", ""),
            )
        elif method == "check_regulatory_compliance":
            return GovCzEngine.check_regulatory_compliance(
                params.get("entity_id", "unknown"),
                params.get("entity_type", "individual"),
            )
        elif method == "get_business_registration":
            return GovCzEngine.get_business_registration(
                params.get("business_id", "unknown"),
            )
        elif method == "list_tools":
            return self.handle_list_tools()
        else:
            return {"error": f"Unknown method: {method}"}

    def handle_list_tools(self) -> Dict[str, Any]:
        """List all available tools"""
        return {
            "tools": list(self.govcz_tools.keys()),
            "server": "govcz",
            "port": 8004,
        }

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def run_govcz_server(port: int = 8004):
    """Start gov.cz MCP server"""
    server = HTTPServer(("127.0.0.1", port), GovCzMCPHandler)
    print(f"Gov.cz MCP server running on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Gov.cz MCP server stopped")
        server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8004
    run_govcz_server(port)
