"""
MCP Server Orchestrator (L5)
Manages all 4 MCP servers (hotel, glass, school, gov.cz)
Provides unified startup, health checks, and integration management
"""

import subprocess
import time
import sys
import json
from typing import List, Dict, Any
from urllib.request import urlopen, Request
from urllib.error import URLError

from mcp_hotel_server import run_hotel_server, HotelMCPHandler
from mcp_glass_server import run_glass_server, GlassMCPHandler
from mcp_school_server import run_school_server, SchoolMCPHandler
from mcp_govcz_server import run_govcz_server, GovCzMCPHandler


class MCPServerOrchestrator:
    """Manages all MCP servers as a coordinated system"""

    def __init__(self):
        self.servers = [
            {"name": "hotel", "port": 8001, "handler": HotelMCPHandler},
            {"name": "glass", "port": 8002, "handler": GlassMCPHandler},
            {"name": "school", "port": 8003, "handler": SchoolMCPHandler},
            {"name": "govcz", "port": 8004, "handler": GovCzMCPHandler},
        ]
        self.processes = []

    def health_check(self, server_name: str, port: int) -> bool:
        """Check if a server is healthy"""
        try:
            request_data = json.dumps({"method": "list_tools", "params": {}}).encode()
            req = Request(
                f"http://127.0.0.1:{port}/rpc",
                data=request_data,
                headers={"Content-Type": "application/json"}
            )
            response = urlopen(req, timeout=2)
            data = json.loads(response.read().decode())
            return "tools" in data and data.get("server") == server_name
        except Exception as e:
            return False

    def get_server_info(self) -> Dict[str, Any]:
        """Get info about all configured servers"""
        return {
            "servers": self.servers,
            "total_servers": len(self.servers),
            "health": {
                server["name"]: self.health_check(server["name"], server["port"])
                for server in self.servers
            }
        }

    def test_rpc_call(self, port: int, method: str, params: Dict) -> Dict[str, Any]:
        """Test an RPC call to a server"""
        try:
            request_data = json.dumps({
                "method": method,
                "params": params
            }).encode()
            req = Request(
                f"http://127.0.0.1:{port}/rpc",
                data=request_data,
                headers={"Content-Type": "application/json"}
            )
            response = urlopen(req, timeout=2)
            return json.loads(response.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def verify_integration(self) -> Dict[str, Any]:
        """Verify all servers are working and integrated"""
        results = {
            "hotel": self.test_rpc_call(8001, "list_tools", {}),
            "glass": self.test_rpc_call(8002, "list_tools", {}),
            "school": self.test_rpc_call(8003, "list_tools", {}),
            "govcz": self.test_rpc_call(8004, "list_tools", {}),
        }

        # Test actual workflows
        results["workflows"] = {
            "hotel_workflow": self.test_hotel_workflow(),
            "glass_workflow": self.test_glass_workflow(),
            "school_workflow": self.test_school_workflow(),
            "govcz_workflow": self.test_govcz_workflow(),
        }

        return results

    def test_hotel_workflow(self) -> Dict[str, Any]:
        """Test complete hotel workflow"""
        try:
            policy = self.test_rpc_call(8001, "check_credit_policy", {
                "merchant_id": "verified_test",
                "amount": 25000
            })
            if policy.get("status") != "eligible":
                return {"success": False, "reason": "Policy check failed"}

            risk = self.test_rpc_call(8001, "score_credit_risk", {
                "merchant_id": "verified_test",
                "history": {}
            })
            if not risk.get("approved"):
                return {"success": False, "reason": "Risk check failed"}

            return {"success": True}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def test_glass_workflow(self) -> Dict[str, Any]:
        """Test complete glass workflow"""
        try:
            policy = self.test_rpc_call(8002, "check_safety_policy", {
                "product_id": "glass_test",
                "category": "automotive"
            })
            if policy.get("status") != "compliant":
                return {"success": False, "reason": "Policy check failed"}

            return {"success": True}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def test_school_workflow(self) -> Dict[str, Any]:
        """Test complete school workflow"""
        try:
            policy = self.test_access_policy = self.test_rpc_call(8003, "check_access_policy", {
                "student_id": "student_test",
                "school_id": "school_test"
            })
            if policy.get("status") != "eligible":
                return {"success": False, "reason": "Policy check failed"}

            return {"success": True}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def test_govcz_workflow(self) -> Dict[str, Any]:
        """Test complete gov.cz workflow"""
        try:
            verification = self.test_rpc_call(8004, "verify_citizen", {
                "citizen_id": "123456789",
                "date_of_birth": "1980-01-01"
            })
            if not verification.get("verified"):
                return {"success": False, "reason": "Citizen verification failed"}

            return {"success": True}
        except Exception as e:
            return {"success": False, "reason": str(e)}


def main():
    """Main orchestrator entry point"""
    orchestrator = MCPServerOrchestrator()

    print("MCP Server Orchestrator")
    print("=" * 50)
    print("\nConfigured servers:")
    for server in orchestrator.servers:
        print(f"  - {server['name'].upper()} on port {server['port']}")

    print("\nServer info:")
    info = orchestrator.get_server_info()
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
