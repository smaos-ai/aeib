# Fixture (clean): verdict strings derived from computed conditions.
import logging
import sys

logger = logging.getLogger(__name__)


def evaluate(results):
    failures = [r for r in results if not r["ok"]]
    print("[PASS]" if not failures else "[FAIL]")
    print(f"status: {'VERIFIED' if not failures else 'REJECTED'}")
    if failures:
        logger.info("All receipts VERIFIED")
        return "FAIL"
    return "PASS" if results else "EMPTY"


def gate(results):
    failures = [r for r in results if not r["ok"]]
    if failures:
        print(f"[FAIL] {len(failures)} failures", file=sys.stderr)
        sys.exit(1)
    print(f"[PASS] {len(results)} checks, 0 violations")


def verdict(observed, expected):
    assert observed == expected, "mismatch"
    return "VERIFIED"


def header():
    print("check | PASS/FAIL | detail")
    print("UNVERIFIED claims are reported as NOT VERIFIED")
