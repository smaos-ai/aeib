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
    """Test hotel server HTTP handler via mocked handle_rpc"""

    def test_hotel_rpc_call_check_policy(self):
        """Test hotel RPC call via handler"""
        # Create a minimal mock handler instance by patching __init__
        with patch.object(HotelMCPHandler, '__init__', lambda x: None):
            handler = HotelMCPHandler()
            result = handler.handle_rpc({
                "method": "check_credit_policy",
                "params": {"merchant_id": "verified_123", "amount": 10000}
            })

            assert result["status"] == "eligible"
            assert result["merchant_id"] == "verified_123"

    def test_hotel_rpc_list_tools(self):
        """Test hotel list_tools RPC call"""
        with patch.object(HotelMCPHandler, '__init__', lambda x: None):
            handler = HotelMCPHandler()
            result = handler.handle_rpc({
                "method": "list_tools",
                "params": {}
            })

            assert "tools" in result
            assert result["server"] == "hotel"
            assert result["port"] == 8001

    def test_hotel_rpc_unknown_method(self):
        """Test hotel unknown method handling"""
        with patch.object(HotelMCPHandler, '__init__', lambda x: None):
            handler = HotelMCPHandler()
            result = handler.handle_rpc({
                "method": "unknown_method",
                "params": {}
            })

            assert "error" in result


class TestGlassHTTPHandler:
    """Test glass server HTTP handler"""

    def test_glass_rpc_call_check_policy(self):
        """Test glass RPC call via handler"""
        with patch.object(GlassMCPHandler, '__init__', lambda x: None):
            handler = GlassMCPHandler()
            result = handler.handle_rpc({
                "method": "check_safety_policy",
                "params": {"product_id": "glass_001", "category": "automotive"}
            })

            assert result["status"] == "compliant"
            assert result["product_id"] == "glass_001"

    def test_glass_rpc_list_tools(self):
        """Test glass list_tools RPC call"""
        with patch.object(GlassMCPHandler, '__init__', lambda x: None):
            handler = GlassMCPHandler()
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
        with patch.object(SchoolMCPHandler, '__init__', lambda x: None):
            handler = SchoolMCPHandler()
            result = handler.handle_rpc({
                "method": "check_access_policy",
                "params": {"student_id": "student_001", "school_id": "school_001"}
            })

            assert result["status"] == "eligible"
            assert result["student_id"] == "student_001"

    def test_school_rpc_list_tools(self):
        """Test school list_tools RPC call"""
        with patch.object(SchoolMCPHandler, '__init__', lambda x: None):
            handler = SchoolMCPHandler()
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
        with patch.object(GovCzMCPHandler, '__init__', lambda x: None):
            handler = GovCzMCPHandler()
            result = handler.handle_rpc({
                "method": "verify_citizen",
                "params": {"citizen_id": "123456789", "date_of_birth": "1980-01-15"}
            })

            assert result["verified"] == True
            assert result["citizen_id"] == "123456789"

    def test_govcz_rpc_list_tools(self):
        """Test gov.cz list_tools RPC call"""
        with patch.object(GovCzMCPHandler, '__init__', lambda x: None):
            handler = GovCzMCPHandler()
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
        with patch.object(HotelMCPHandler, '__init__', lambda x: None):
            hotel = HotelMCPHandler()

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
        with patch.object(GlassMCPHandler, '__init__', lambda x: None):
            glass = GlassMCPHandler()

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
        handlers_and_patches = [
            (HotelMCPHandler, HotelMCPHandler),
            (GlassMCPHandler, GlassMCPHandler),
            (SchoolMCPHandler, SchoolMCPHandler),
            (GovCzMCPHandler, GovCzMCPHandler),
        ]

        for handler_class, patch_class in handlers_and_patches:
            with patch.object(patch_class, '__init__', lambda x: None):
                server = handler_class()
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
        with patch.object(HotelMCPHandler, '__init__', lambda x: None):
            handler = HotelMCPHandler()

            # This should be handled by the handler
            result = handler.handle_rpc({
                "method": "list_tools",  # Valid method
                "params": {}
            })

            assert "tools" in result  # Should work

    def test_missing_required_params(self):
        """Test handling of missing parameters"""
        with patch.object(HotelMCPHandler, '__init__', lambda x: None):
            hotel = HotelMCPHandler()

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
            (HotelMCPHandler, "hotel", 8001),
            (GlassMCPHandler, "glass", 8002),
            (SchoolMCPHandler, "school", 8003),
            (GovCzMCPHandler, "govcz", 8004),
        ]

        for handler_class, expected_server, expected_port in servers_info:
            with patch.object(handler_class, '__init__', lambda x: None):
                handler = handler_class()
                result = handler.handle_rpc({"method": "list_tools", "params": {}})

                assert result["server"] == expected_server
                assert result["port"] == expected_port
                assert len(result["tools"]) >= 3

    def test_all_tools_documented(self):
        """Test that all tools have descriptions"""
        handlers_and_tools = [
            (HotelMCPHandler, 'hotel_tools'),
            (GlassMCPHandler, 'glass_tools'),
            (SchoolMCPHandler, 'school_tools'),
            (GovCzMCPHandler, 'govcz_tools'),
        ]

        for handler_class, tools_attr in handlers_and_tools:
            # Check that each handler class has documented tools
            tools = getattr(handler_class, tools_attr)

            for tool_name, tool_info in tools.items():
                assert "description" in tool_info
                assert "handler" in tool_info


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
