"""
Stream C: Hotel Credit Scoring MCP Server
Port: 8001
Provides tools for hotel credit scoring and policy verification
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from typing import Any, Dict


class HotelMCPHandler(BaseHTTPRequestHandler):
    """JSON-RPC handler for hotel MCP server"""

    # Shared state
    hotel_tools = {
        "check_credit_policy": {
            "description": "Check hotel credit policy",
            "handler": "handle_check_credit_policy",
        },
        "score_credit_risk": {
            "description": "Score credit risk",
            "handler": "handle_score_credit_risk",
        },
        "approve_credit_line": {
            "description": "Approve credit line",
            "handler": "handle_approve_credit_line",
        },
        "log_credit_decision": {
            "description": "Log credit decision",
            "handler": "handle_log_credit_decision",
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
            return self.handle_check_credit_policy(params)
        elif method == "score_credit_risk":
            return self.handle_score_credit_risk(params)
        elif method == "approve_credit_line":
            return self.handle_approve_credit_line(params)
        elif method == "log_credit_decision":
            return self.handle_log_credit_decision(params)
        elif method == "list_tools":
            return self.handle_list_tools()
        else:
            return {"error": f"Unknown method: {method}"}

    def handle_check_credit_policy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check if merchant meets credit policy"""
        merchant_id = params.get("merchant_id", "unknown")
        amount = params.get("amount", 0)

        # Verify merchant
        if merchant_id.startswith("verified"):
            return {
                "status": "eligible",
                "merchant_id": merchant_id,
                "max_credit_line": 50000 if amount <= 50000 else amount,
                "policy": "standard_hotel_credit",
            }
        else:
            return {
                "status": "ineligible",
                "merchant_id": merchant_id,
                "reason": "Merchant not verified",
            }

    def handle_score_credit_risk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Score credit risk for merchant"""
        merchant_id = params.get("merchant_id", "unknown")
        history = params.get("history", {})

        # Simple risk scoring
        risk_score = 0.3  # Default low risk
        if "payment_defaults" in history:
            risk_score += 0.2 * history["payment_defaults"]

        return {
            "merchant_id": merchant_id,
            "risk_score": min(1.0, risk_score),
            "risk_level": "low" if risk_score < 0.5 else "medium",
            "approved": risk_score < 0.7,
        }

    def handle_approve_credit_line(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Approve credit line for merchant"""
        merchant_id = params.get("merchant_id", "unknown")
        amount = params.get("amount", 0)

        approval_id = f"appr_{merchant_id}_{int(datetime.utcnow().timestamp())}"

        return {
            "approval_id": approval_id,
            "merchant_id": merchant_id,
            "approved_amount": amount,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "approved",
        }

    def handle_log_credit_decision(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Log credit decision to audit trail"""
        merchant_id = params.get("merchant_id", "unknown")
        decision = params.get("decision", "pending")

        log_entry = {
            "merchant_id": merchant_id,
            "decision": decision,
            "timestamp": datetime.utcnow().isoformat(),
            "logged": True,
        }

        return log_entry

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
