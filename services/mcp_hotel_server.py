"""
Stream C: Hotel Credit Scoring MCP Server
Port: 8001
Provides tools for hotel credit scoring and policy verification
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict

from mcp_core import HotelCreditEngine


class HotelMCPHandler(BaseHTTPRequestHandler):
    """JSON-RPC handler for hotel MCP server"""

    # Shared state
    hotel_tools = {
        "check_credit_policy": {
            "description": "Check hotel credit policy",
            "handler": "check_credit_policy",
        },
        "score_credit_risk": {
            "description": "Score credit risk",
            "handler": "score_credit_risk",
        },
        "approve_credit_line": {
            "description": "Approve credit line",
            "handler": "approve_credit_line",
        },
        "log_credit_decision": {
            "description": "Log credit decision",
            "handler": "log_credit_decision",
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

        if method == "check_credit_policy":
            return HotelCreditEngine.check_credit_policy(
                params.get("merchant_id", "unknown"),
                params.get("amount", 0),
            )
        elif method == "score_credit_risk":
            return HotelCreditEngine.score_credit_risk(
                params.get("merchant_id", "unknown"),
                params.get("history", {}),
            )
        elif method == "approve_credit_line":
            return HotelCreditEngine.approve_credit_line(
                params.get("merchant_id", "unknown"),
                params.get("amount", 0),
            )
        elif method == "log_credit_decision":
            return HotelCreditEngine.log_credit_decision(
                params.get("merchant_id", "unknown"),
                params.get("decision", "pending"),
            )
        elif method == "list_tools":
            return self.handle_list_tools()
        else:
            return {"error": f"Unknown method: {method}"}

    def handle_list_tools(self) -> Dict[str, Any]:
        """List all available tools"""
        return {
            "tools": list(self.hotel_tools.keys()),
            "server": "hotel",
            "port": 8001,
        }

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def run_hotel_server(port: int = 8001):
    """Start hotel MCP server"""
    server = HTTPServer(("127.0.0.1", port), HotelMCPHandler)
    print(f"Hotel MCP server running on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Hotel MCP server stopped")
        server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    run_hotel_server(port)

