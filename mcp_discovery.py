"""
Stream C: MCP Server Discovery
Discovers and catalogs 3 MCP servers (hotel, glass, school)
Returns server metadata and tool definitions for client discovery
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class MCPTool:
    """MCP tool definition"""

    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPServer:
    """MCP server definition"""

    name: str
    port: int
    description: str
    tools: List[MCPTool]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "port": self.port,
            "description": self.description,
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in self.tools
            ],
        }


class MCPServerRegistry:
    """Registry for MCP server discovery"""

    def __init__(self):
        self.servers = self._initialize_servers()

    def _initialize_servers(self) -> List[MCPServer]:
        """Initialize 3 MCP servers (hotel, glass, school)"""

        # Hotel Credit Scoring Server (port 8001)
        hotel_tools = [
            MCPTool(
                name="check_credit_policy",
                description="Check hotel credit policy for merchant eligibility",
                input_schema={"merchant_id": "string", "amount": "number"},
            ),
            MCPTool(
                name="score_credit_risk",
                description="Score credit risk for hotel credit application",
                input_schema={"merchant_id": "string", "history": "object"},
            ),
            MCPTool(
                name="approve_credit_line",
                description="Approve credit line for verified merchant",
                input_schema={"merchant_id": "string", "amount": "number"},
            ),
            MCPTool(
                name="log_credit_decision",
                description="Log credit decision to audit trail",
                input_schema={"merchant_id": "string", "decision": "string"},
            ),
            MCPTool(
                name="query_hotel_compliance",
                description="Query hotel compliance timeline from L2 knowledge",
                input_schema={"query": "string"},
            ),
            MCPTool(
                name="get_policy_boundaries",
                description="Get policy boundaries for hotel credit scoring",
                input_schema={"policy_type": "string"},
            ),
        ]

        hotel_server = MCPServer(
            name="hotel",
            port=8001,
            description="Hotel credit scoring MCP server",
            tools=hotel_tools,
        )

        # Glass Safety Review Server (port 8002)
        glass_tools = [
            MCPTool(
                name="check_safety_policy",
                description="Check safety review policy for glass products",
                input_schema={"product_id": "string", "category": "string"},
            ),
            MCPTool(
                name="analyze_safety_risk",
                description="Analyze safety risk for glass product",
                input_schema={"product_id": "string", "specs": "object"},
            ),
            MCPTool(
                name="approve_safety_review",
                description="Approve safety review for product",
                input_schema={"product_id": "string", "certifications": "array"},
            ),
            MCPTool(
                name="log_safety_decision",
                description="Log safety decision to audit trail",
                input_schema={"product_id": "string", "decision": "string"},
            ),
            MCPTool(
                name="query_safety_standards",
                description="Query safety standards from L2 knowledge",
                input_schema={"standard": "string"},
            ),
            MCPTool(
                name="get_safety_boundaries",
                description="Get policy boundaries for glass safety review",
                input_schema={"policy_type": "string"},
            ),
        ]

        glass_server = MCPServer(
            name="glass",
            port=8002,
            description="Glass safety review MCP server",
            tools=glass_tools,
        )

        # School Access Control Server (port 8003)
        school_tools = [
            MCPTool(
                name="check_access_policy",
                description="Check access control policy for school enrollment",
                input_schema={"student_id": "string", "school_id": "string"},
            ),
            MCPTool(
                name="verify_enrollment_eligibility",
                description="Verify student enrollment eligibility",
                input_schema={"student_id": "string", "grade": "string"},
            ),
            MCPTool(
                name="approve_access_control",
                description="Approve access control for student",
                input_schema={"student_id": "string", "school_id": "string"},
            ),
            MCPTool(
                name="log_access_decision",
                description="Log access control decision to audit trail",
                input_schema={"student_id": "string", "decision": "string"},
            ),
            MCPTool(
                name="query_school_policies",
                description="Query school policies from L2 knowledge",
                input_schema={"query": "string"},
            ),
            MCPTool(
                name="get_access_boundaries",
                description="Get policy boundaries for school access control",
                input_schema={"policy_type": "string"},
            ),
        ]

        school_server = MCPServer(
            name="school",
            port=8003,
            description="School access control MCP server",
            tools=school_tools,
        )

        return [hotel_server, glass_server, school_server]

    def discover(self) -> List[Dict[str, Any]]:
        """
        Discover all configured MCP servers.
        Returns list of server definitions with tools.
        """
        return [server.to_dict() for server in self.servers]

    def get_server(self, name: str) -> Dict[str, Any]:
        """Get specific server definition by name"""
        for server in self.servers:
            if server.name == name:
                return server.to_dict()
        raise ValueError(f"Server '{name}' not found")

    def get_tool(self, server_name: str, tool_name: str) -> Dict[str, Any]:
        """Get specific tool definition from server"""
        server_def = self.get_server(server_name)
        for tool in server_def["tools"]:
            if tool["name"] == tool_name:
                return tool
        raise ValueError(f"Tool '{tool_name}' not found in server '{server_name}'")


# Usage example
if __name__ == "__main__":
    registry = MCPServerRegistry()

    # Discover all servers
    servers = registry.discover()
    print(f"Discovered {len(servers)} MCP servers:")
    for server in servers:
        print(
            f"  - {server['name']} (port {server['port']}): {len(server['tools'])} tools"
        )

    # Get specific server
    hotel = registry.get_server("hotel")
    print(f"\nHotel server tools: {[t['name'] for t in hotel['tools']]}")
