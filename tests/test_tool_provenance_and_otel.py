# File: tests/test_tool_provenance_and_otel.py
"""
Verification suite for AT63 / AT63b MCP Tool Provenance Pinning and OpenTelemetry v1.43 Export.
"""
from tools.scitt_ap2_x402_otel_engine import (
    test_banned_words_absence,
    test_scitt_ap2_x402_otel_and_cbom_engine,
)


def test_at63_tool_provenance_and_otel_v143_export() -> None:
    test_scitt_ap2_x402_otel_and_cbom_engine()
    test_banned_words_absence()
