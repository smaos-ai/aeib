"""pytest configuration and shared fixtures for ocr-audit-engine tests."""

import pytest
import sys
from pathlib import Path

# Ensure src is on python path
src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
