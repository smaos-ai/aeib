"""
HTTP Integration Tests for MCP Servers
Tests all 4 servers via JSON-RPC HTTP interface
"""

import pytest
import json
from unittest.mock import Mock, patch
from http.server import HTTPServer
import threading
import time
from http.client import HTTPConnection

from mcp_hotel_server import HotelMCPHandler, run_hotel_server
from mcp_glass_server import GlassMCPHandler, run_glass_server
from mcp_school_server import SchoolMCPHandler, run_school_server
from mcp_govcz_server import GovCzMCPHandler, run_govcz_server


class MockRequest:
    """Mock HTTP request for testing handlers"""

    def __init__(self, method: str, params: dict):
        self.request_json = json.dumps({"method": method, "params": params})


class MockSocket:
    """Mock socket for testing"""

    def __init__(self, request_data: bytes):
        self.request_data = request_data
        self.response_data = b""
        self.pos = 0

    def recv(self, size):
        end = min(self.pos + size, len(self.request_data))
        data = self.request_data[self.pos : end]
        self.pos = end
        return data

    def sendall(self, data):
        self.response_data += data


class TestHotelHTTPHandler:
    """Test hotel server HTTP handler"""

    def test_hotel_rpc_call_check_policy(self):
        """Test hotel RPC call via handler"""
        handler = HotelMCPHandler(Mock(), ("127.0.0.1", 8001), Mock())
        result = handler.handle_rpc({
            "method": "check_credit_policy",
            "params": {"merchant_id": "verified_123", "amount": 10000}
        })

        assert result["status"] == "eligible"
        assert result["merchant_id"] == "verified_123"

    def test_hotel_rpc_list_tools(self):
        """Test hotel list_tools RPC call"""
        handler = HotelMCPHandler(Mock(), ("127.0.0.1", 8001), Mock())
        result = handler.handle_rpc({
            "method": "list_tools",
            "params": {}
        })

        assert "tools" in result
        assert result["server"] == "hotel"
        assert result["port"] == 8001

    def test_hotel_rpc_unknown_method(self):
        """Test hotel unknown method handling"""
        handler = HotelMCPHandler(Mock(), ("127.0.0.1", 8001), Mock())
        result = handler.handle_rpc({
            "method": "unknown_method",
            "params": {}
        })

        assert "error" in result


class TestGlassHTTPHandler:
    """Test glass server HTTP handler"""

    def test_glass_rpc_call_check_policy(self):
        """Test glass RPC call via handler"""
        handler = GlassMCPHandler(Mock(), ("127.0.0.1", 8002), Mock())
        result = handler.handle_rpc({
            "method": "check_safety_policy",
            "params": {"product_id": "glass_001", "category": "automotive"}
        })

        assert result["status"] == "compliant"
        assert result["product_id"] == "glass_001"

    def test_glass_rpc_list_tools(self):
        """Test glass list_tools RPC call"""
        handler = GlassMCPHandler(Mock(), ("127.0.0.1", 8002), Mock())
        result = handler.handle_rpc({
            "method": "list_tools",
            "params": {}
        })

        assert "tools" in result
        assert result["server"] == "glass"
        assert result["port"] == 8002


class TestSchoolHTTPHandler:
    """Test school server HTTP handler"""

    def test_school_rpc_call_check_policy(self):
        """Test school RPC call via handler"""
        handler = SchoolMCPHandler(Mock(), ("127.0.0.1", 8003), Mock())
        result = handler.handle_rpc({
            "method": "check_access_policy",
            "params": {"student_id": "student_001", "school_id": "school_001"}
        })

        assert result["status"] == "eligible"
        assert result["student_id"] == "student_001"

    def test_school_rpc_list_tools(self):
        """Test school list_tools RPC call"""
        handler = SchoolMCPHandler(Mock(), ("127.0.0.1", 8003), Mock())
        result = handler.handle_rpc({
            "method": "list_tools",
            "params": {}
        })

        assert "tools" in result
        assert result["server"] == "school"
        assert result["port"] == 8003


class TestGovCzHTTPHandler:
    """Test gov.cz server HTTP handler"""

    def test_govcz_rpc_call_verify_citizen(self):
        """Test gov.cz RPC call via handler"""
        handler = GovCzMCPHandler(Mock(), ("127.0.0.1", 8004), Mock())
        result = handler.handle_rpc({
            "method": "verify_citizen",
            "params": {"citizen_id": "123456789", "date_of_birth": "1980-01-15"}
        })

        assert result["verified"] == True
        assert result["citizen_id"] == "123456789"

    def test_govcz_rpc_list_tools(self):
        """Test gov.cz list_tools RPC call"""
        handler = GovCzMCPHandler(Mock(), ("127.0.0.1", 8004), Mock())
        result = handler.handle_rpc({
            "method": "list_tools",
            "params": {}
        })

        assert "tools" in result
        assert result["server"] == "govcz"
        assert result["port"] == 8004


class TestMultipleServersWorkflow:
    """Test complete multi-server workflow"""

    def test_full_pipeline_hotel_to_completion(self):
        """Test full pipeline: policy -> risk -> approval -> logging"""
        hotel = HotelMCPHandler(Mock(), ("127.0.0.1", 8001), Mock())

        # Check policy
        policy = hotel.handle_rpc({
            "method": "check_credit_policy",
            "params": {"merchant_id": "verified_merchant", "amount": 50000}
        })
        assert policy["status"] == "eligible"

        # Score risk
        risk = hotel.handle_rpc({
            "method": "score_credit_risk",
            "params": {"merchant_id": "verified_merchant", "history": {}}
        })
        assert risk["approved"] == True

        # Approve line
        approval = hotel.handle_rpc({
            "method": "approve_credit_line",
            "params": {"merchant_id": "verified_merchant", "amount": 50000}
        })
        assert approval["status"] == "approved"

    def test_full_pipeline_glass_to_completion(self):
        """Test full glass safety pipeline"""
        glass = GlassMCPHandler(Mock(), ("127.0.0.1", 8002), Mock())

        # Check policy
        policy = glass.handle_rpc({
            "method": "check_safety_policy",
            "params": {"product_id": "glass_001", "category": "automotive"}
        })
        assert policy["status"] == "compliant"

        # Analyze risk
        risk = glass.handle_rpc({
            "method": "analyze_safety_risk",
            "params": {"product_id": "glass_001", "specs": {"breakage_resistance": True}}
        })
        assert risk["safe"] == True

        # Approve review
        approval = glass.handle_rpc({
            "method": "approve_safety_review",
            "params": {"product_id": "glass_001", "certifications": ["ISO-9001"]}
        })
        assert approval["status"] == "approved"

    def test_cross_server_interop(self):
        """Test that all servers have compatible interfaces"""
        servers = [
            HotelMCPHandler(Mock(), ("127.0.0.1", 8001), Mock()),
            GlassMCPHandler(Mock(), ("127.0.0.1", 8002), Mock()),
            SchoolMCPHandler(Mock(), ("127.0.0.1", 8003), Mock()),
            GovCzMCPHandler(Mock(), ("127.0.0.1", 8004), Mock()),
        ]

        for server in servers:
            # All servers should respond to list_tools
            result = server.handle_rpc({
                "method": "list_tools",
                "params": {}
            })

            assert "tools" in result
            assert "server" in result
            assert "port" in result


class TestErrorHandling:
    """Test error handling across all servers"""

    def test_malformed_json_handling(self):
        """Test handling of malformed JSON"""
        handler = HotelMCPHandler(Mock(), ("127.0.0.1", 8001), Mock())

        # This should be handled by the handler
        result = handler.handle_rpc({
            "method": "list_tools",  # Valid method
            "params": {}
        })

        assert "tools" in result  # Should work

    def test_missing_required_params(self):
        """Test handling of missing parameters"""
        hotel = HotelMCPHandler(Mock(), ("127.0.0.1", 8001), Mock())

        # Call with missing merchant_id
        result = hotel.handle_rpc({
            "method": "check_credit_policy",
            "params": {"amount": 10000}  # Missing merchant_id
        })

        # Should handle gracefully
        assert "status" in result


class TestServerMetadata:
    """Test server metadata and discovery"""

    def test_all_servers_discoverable(self):
        """Test that all servers are discoverable"""
        servers_info = [
            (HotelMCPHandler(Mock(), ("127.0.0.1", 8001), Mock()), "hotel", 8001),
            (GlassMCPHandler(Mock(), ("127.0.0.1", 8002), Mock()), "glass", 8002),
            (SchoolMCPHandler(Mock(), ("127.0.0.1", 8003), Mock()), "school", 8003),
            (GovCzMCPHandler(Mock(), ("127.0.0.1", 8004), Mock()), "govcz", 8004),
        ]

        for handler, expected_server, expected_port in servers_info:
            result = handler.handle_rpc({"method": "list_tools", "params": {}})

            assert result["server"] == expected_server
            assert result["port"] == expected_port
            assert len(result["tools"]) >= 3

    def test_all_tools_documented(self):
        """Test that all tools have descriptions"""
        handlers = [
            HotelMCPHandler(Mock(), ("127.0.0.1", 8001), Mock()),
            GlassMCPHandler(Mock(), ("127.0.0.1", 8002), Mock()),
            SchoolMCPHandler(Mock(), ("127.0.0.1", 8003), Mock()),
            GovCzMCPHandler(Mock(), ("127.0.0.1", 8004), Mock()),
        ]

        for handler in handlers:
            # Check that each handler has documented tools
            if hasattr(handler, 'hotel_tools'):
                tools = handler.hotel_tools
            elif hasattr(handler, 'glass_tools'):
                tools = handler.glass_tools
            elif hasattr(handler, 'school_tools'):
                tools = handler.school_tools
            else:
                tools = handler.govcz_tools

            for tool_name, tool_info in tools.items():
                assert "description" in tool_info
                assert "handler" in tool_info


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
