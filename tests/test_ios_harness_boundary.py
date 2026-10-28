#!/usr/bin/env python3
"""
tests/test_ios_harness_boundary.py — Wave 8 iOS boundary tests (prototype).

Real files, real git repos, real swiftc where the host has it, real Ed25519.
No mocks. Synthetic fixtures are labelled as such.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.ios_incident_emitter import IOSIncidentEmitter
from src.ios_steward_guard import IOSProposal, IOSStewardGuard
from src.ios_xcode_harness import SovereignXcodeHarness, XcodeActionType, XcodeToolCallRequest
from src.sphinx_swift_ast import SphinxSwiftASTParser
from src.xctest_tamper_guard import ALLOW, ESCALATE, HALT, XCTestTamperGuard

HAS_SWIFTC = shutil.which("swiftc", path="/usr/bin:/bin:/usr/sbin:/sbin") is not None


def _req(ws, action=XcodeActionType.BUILD_SCHEME, **kw):
    kw.setdefault("target_name", "App")
    return XcodeToolCallRequest(action=action, workspace_root=str(ws), **kw)


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    d = tmp_path / "AppWorkspace"
    d.mkdir()
    return d


# ============================================================================
# 1. Harness
# ============================================================================


def test_harness_init_and_frozen_request(ws: Path) -> None:
    h = SovereignXcodeHarness(str(ws), developer_dir=str(ws))
    assert h.workspace_root == os.path.realpath(str(ws))
    assert h.developer_dir == os.path.realpath(str(ws))
    for bad in ("", "   ", None):
        with pytest.raises(ValueError, match="ERR_INVALID_WORKSPACE_ROOT"):
            SovereignXcodeHarness(bad)  # type: ignore[arg-type]
    req = _req(ws)
    with pytest.raises(FrozenInstanceError):
        req.action = XcodeActionType.RUN_TESTS  # type: ignore[misc]


@pytest.mark.parametrize("action", ["BUILD_SCHEME_STR", 123, None])
def test_harness_rejects_non_enum_action(ws: Path, action) -> None:
    cmd, reason = SovereignXcodeHarness(str(ws)).build_command(_req(ws, action=action))
    assert cmd is None
    assert reason.startswith("HALT_UNSUPPORTED_XCODE_ACTION")


def test_harness_workspace_boundary(tmp_path: Path, ws: Path) -> None:
    h = SovereignXcodeHarness(str(ws))
    (tmp_path / "AppWorkspace-evil").mkdir()
    (ws / "link_out").symlink_to(tmp_path)
    (ws / "sub").mkdir()
    cases = {
        "": "HALT_WORKSPACE_BOUNDARY_VIOLATION:EMPTY",
        str(tmp_path / "sibling"): "HALT_WORKSPACE_BOUNDARY_VIOLATION:ESCAPES_ROOT",
        str(tmp_path / "AppWorkspace-evil"): "HALT_WORKSPACE_BOUNDARY_VIOLATION:ESCAPES_ROOT",
        str(ws / "link_out"): "HALT_WORKSPACE_BOUNDARY_VIOLATION:ESCAPES_ROOT",
        str(ws / ".." / ".."): "HALT_WORKSPACE_BOUNDARY_VIOLATION:ESCAPES_ROOT",
    }
    for root, expected in cases.items():
        req = XcodeToolCallRequest(XcodeActionType.BUILD_SCHEME, root, "App", scheme_name="App")
        assert h.build_command(req) == (None, expected), root
    non_str = XcodeToolCallRequest(XcodeActionType.BUILD_SCHEME, 7, "App", scheme_name="App")  # type: ignore[arg-type]
    assert h.build_command(non_str) == (None, "HALT_WORKSPACE_BOUNDARY_VIOLATION:EMPTY")
    cmd, reason = h.build_command(_req(ws / "sub", scheme_name="App"))
    assert reason == "" and cmd is not None


def test_harness_argument_validation(ws: Path) -> None:
    h = SovereignXcodeHarness(str(ws))
    (ws / "Derived").mkdir()
    bad = ["; rm -rf /", "$(id)", "a b", "-derivedDataPath=/etc", "../outside", "-x=../../etc", 5]
    for arg in bad:
        cmd, reason = h.build_command(_req(ws, scheme_name="App", extra_arguments=(arg,)))
        assert cmd is None and reason.startswith("HALT_UNSAFE_TOOLCHAIN_ARGUMENT"), arg
    cmd, reason = h.build_command(_req(ws, scheme_name="App", extra_arguments=("-derivedDataPath=Derived", "-quiet")))
    assert reason == "" and cmd[-2:] == ["-derivedDataPath=Derived", "-quiet"]
    cmd, reason = h.build_command(_req(ws, scheme_name="App", workspace_file="/etc/x.xcworkspace"))
    assert cmd is None and reason.startswith("HALT_UNSAFE_TOOLCHAIN_ARGUMENT")


def test_harness_exact_argv_per_action(ws: Path) -> None:
    h = SovereignXcodeHarness(str(ws))
    root = os.path.realpath(str(ws))
    udid = "0123ABCD-0000-1111-2222-333344445555"
    assert h.build_command(_req(ws, scheme_name="App")) == (
        ["xcodebuild", "build", "-scheme", "App", "-workspace", os.path.join(root, "App.xcworkspace")], "")
    assert h.build_command(_req(ws, scheme_name="App", workspace_file="Custom.xcworkspace"))[0][-1] == \
        os.path.join(root, "Custom.xcworkspace")
    assert h.build_command(_req(ws, XcodeActionType.RUN_TESTS, scheme_name="App")) == (
        ["xcodebuild", "test", "-scheme", "App", "-destination", "platform=iOS Simulator,id=booted"], "")
    assert h.build_command(_req(ws, XcodeActionType.RUN_TESTS, scheme_name="App", simulator_udid=udid))[0][-1] == \
        f"platform=iOS Simulator,id={udid}"
    assert h.build_command(_req(ws, XcodeActionType.BOOT_SIMULATOR, simulator_udid=udid)) == (
        ["xcrun", "simctl", "boot", udid], "")
    assert h.build_command(_req(ws, XcodeActionType.WIPE_SIMULATOR_STATE, simulator_udid=udid)) == (
        None, "HALT_SIMULATOR_WIPE_NOT_AUTHORIZED")
    h_wipe = SovereignXcodeHarness(str(ws), allow_simulator_wipe=True)
    assert h_wipe.build_command(_req(ws, XcodeActionType.WIPE_SIMULATOR_STATE, simulator_udid=udid)) == (
        ["xcrun", "simctl", "erase", udid], "")
    with pytest.raises(ValueError, match="ERR_INVALID_SIMULATOR_WIPE_FLAG"):
        SovereignXcodeHarness(str(ws), allow_simulator_wipe=1)  # type: ignore[arg-type]
    assert h.build_command(_req(ws, XcodeActionType.SWIFT_TYPECHECK)) == (["swiftc", "-version"], "")
    assert h.build_command(_req(ws, XcodeActionType.SWIFT_TYPECHECK, extra_arguments=("a.swift",))) == (
        ["swiftc", "-typecheck", "a.swift"], "")


def test_harness_scheme_and_udid_validation(ws: Path) -> None:
    h = SovereignXcodeHarness(str(ws))
    for action in (XcodeActionType.BUILD_SCHEME, XcodeActionType.RUN_TESTS):
        for scheme in (None, "", "App;echo", "App evil"):
            assert h.build_command(_req(ws, action, scheme_name=scheme)) == (
                None, "HALT_MISSING_OR_INVALID_SCHEME_NAME")
    for action in (XcodeActionType.BOOT_SIMULATOR, XcodeActionType.WIPE_SIMULATOR_STATE):
        for udid in (None, "", "not-a-uuid", "booted; rm"):
            assert h.build_command(_req(ws, action, simulator_udid=udid)) == (
                None, "HALT_MISSING_OR_INVALID_SIMULATOR_UDID")
    assert h.build_command(_req(ws, XcodeActionType.RUN_TESTS, scheme_name="App", simulator_udid="x!")) == (
        None, "HALT_INVALID_SIMULATOR_UDID:x!")


def test_harness_env_is_rebuilt_without_host_credentials(ws: Path) -> None:
    os.environ["AWS_SECRET_ACCESS_KEY"] = "wave8-test-canary"
    try:
        env = SovereignXcodeHarness(str(ws)).sanitized_env()
    finally:
        del os.environ["AWS_SECRET_ACCESS_KEY"]
    assert set(env) <= {"PATH", "HOME", "TMPDIR", "LC_ALL", "LANG", "DEVELOPER_DIR"}
    assert "wave8-test-canary" not in env.values()
    assert env["HOME"] == os.path.realpath(str(ws))
    assert env["TMPDIR"] == os.path.realpath(str(ws))


def test_harness_missing_toolchain_fails_closed(tmp_path: Path, ws: Path) -> None:
    empty = tmp_path / "emptybin"
    empty.mkdir()
    h = SovereignXcodeHarness(str(ws), tool_search_path=str(empty))
    assert h.dispatch_sandboxed_tool(_req(ws, XcodeActionType.SWIFT_TYPECHECK)) == (
        False, "", "HALT_XCODE_TOOLCHAIN_UNAVAILABLE:swiftc")
    # validation runs before the toolchain check
    assert h.dispatch_sandboxed_tool(_req(ws, scheme_name="")) == (
        False, "", "HALT_MISSING_OR_INVALID_SCHEME_NAME")


@pytest.mark.skipif(not HAS_SWIFTC, reason="swiftc not installed on host")
def test_harness_real_swiftc_typecheck(ws: Path) -> None:
    h = SovereignXcodeHarness(str(ws))
    ok, out, reason = h.dispatch_sandboxed_tool(_req(ws, XcodeActionType.SWIFT_TYPECHECK), timeout=60)
    assert (ok, reason) == (True, "OK_TOOL_EXECUTION_SUCCESS") and "Swift" in out
    (ws / "good.swift").write_text("let x: Int = 1\nprint(x)\n")
    (ws / "bad.swift").write_text("let x: Int = \"not an int\"\n")
    ok, _, reason = h.dispatch_sandboxed_tool(
        _req(ws, XcodeActionType.SWIFT_TYPECHECK, extra_arguments=("good.swift",)), timeout=120)
    assert (ok, reason) == (True, "OK_TOOL_EXECUTION_SUCCESS")
    ok, _, reason = h.dispatch_sandboxed_tool(
        _req(ws, XcodeActionType.SWIFT_TYPECHECK, extra_arguments=("bad.swift",)), timeout=120)
    assert ok is False and reason.startswith("HALT_PROCESS_EXIT_NON_ZERO:")
    assert h.dispatch_sandboxed_tool(_req(ws, XcodeActionType.SWIFT_TYPECHECK), timeout=1e-9) == (
        False, "", "HALT_TOOLCHAIN_TIMEOUT_EXPIRED")


@pytest.mark.skipif(not HAS_SWIFTC, reason="swiftc not installed on host")
def test_harness_oserror_when_workspace_deleted(tmp_path: Path) -> None:
    d = tmp_path / "Gone"
    d.mkdir()
    h = SovereignXcodeHarness(str(d))
    req = _req(d, XcodeActionType.SWIFT_TYPECHECK)
    d.rmdir()
    assert h.dispatch_sandboxed_tool(req) == (False, "", "HALT_TOOLCHAIN_EXCEPTION:FileNotFoundError")


# ============================================================================
# 2. Steward guard
# ============================================================================


@pytest.fixture()
def approver():
    key = Ed25519PrivateKey.generate()
    return key, IOSStewardGuard(key.public_key().public_bytes_raw().hex())


@pytest.mark.parametrize("path", [
    "App/Info.plist", "App.entitlements", "Sources/PrivacyInfo.xcprivacy",
    "App.xcodeproj/project.pbxproj", "App.xcworkspace/contents.xcworkspacedata",
    "Ext/Widget.entitlements",
    "App.xcproj", "App.xcproj/project.json",
])
def test_steward_authorities_need_approval(approver, path: str) -> None:
    _, guard = approver
    ok, reason = guard.evaluate_ios_proposal(IOSProposal(path, "+ <key>x</key>"))
    assert (ok, reason) == (False, f"HALT_IOS_INVARIANT_CORE_MUTATION_FORBIDDEN:{path}")


@pytest.mark.parametrize("path", [
    "docs/notes_about_Info.plist.txt", "Sources/InfoPlistReader.swift",
    "Sources/entitlements_helper.swift", "xcodeproj_notes.md",
])
def test_steward_no_substring_false_positive(approver, path: str) -> None:
    _, guard = approver
    assert guard.evaluate_ios_proposal(IOSProposal(path, "+ let a = 1")) == (
        True, "OK_IOS_REFLECTIVE_SHELL_AUTHORIZED")


def test_steward_signed_approval_is_bound_to_exact_diff(approver) -> None:
    key, guard = approver
    prop = IOSProposal("App/Info.plist", "+ <key>CFBundleVersion</key><string>2</string>")
    sig = IOSStewardGuard.sign_approval(prop, key)
    assert guard.evaluate_ios_proposal(IOSProposal(prop.target_file_path, prop.proposed_diff, sig)) == (
        True, "OK_IOS_INVARIANT_CORE_CHANGE_APPROVED")
    swapped = IOSProposal(prop.target_file_path, "+ <key>UIBackgroundModes</key>", sig)
    assert guard.evaluate_ios_proposal(swapped)[0] is False
    other_path = IOSProposal("App2/Info.plist", prop.proposed_diff, sig)
    assert guard.evaluate_ios_proposal(other_path)[0] is False
    wrong_key_sig = IOSStewardGuard.sign_approval(prop, Ed25519PrivateKey.generate())
    assert guard.evaluate_ios_proposal(IOSProposal(prop.target_file_path, prop.proposed_diff, wrong_key_sig))[0] is False
    for junk in ("zz", "00" * 64, ""):
        assert guard.evaluate_ios_proposal(IOSProposal(prop.target_file_path, prop.proposed_diff, junk))[0] is False
    # a guard with no pinned approver can never approve
    assert IOSStewardGuard().evaluate_ios_proposal(IOSProposal(prop.target_file_path, prop.proposed_diff, sig))[0] is False


@pytest.mark.parametrize("diff,label", [
    ("+ let k = \"-----BEGIN EC PRIVATE KEY-----\"", "PRIVATE_KEY_LITERAL"),
    ("+ let k = \"-----BEGIN PRIVATE KEY-----\"", "PRIVATE_KEY_LITERAL"),
    ("+ var d = [\"NSAllowsArbitraryLoads\": true]", "NSAllowsArbitraryLoads_ATS_BYPASS"),
    ("+ <key>NSAllowsArbitraryLoads</key>\n+ <true/>", "NSAllowsArbitraryLoads_ATS_BYPASS"),
    ("+ <key>NSAllowsArbitraryLoads</key><true/>", "NSAllowsArbitraryLoads_ATS_BYPASS"),
    ("+ NSAllowsArbitraryLoads = YES", "NSAllowsArbitraryLoads_ATS_BYPASS"),
    ("+ let api_secret = \"sk-live-12345678\"", "HARDCODED_API_SECRET"),
])
def test_steward_forbidden_added_lines(approver, diff: str, label) -> None:
    _, guard = approver
    ok, reason = guard.evaluate_ios_proposal(IOSProposal("Sources/Net.swift", diff))
    assert (ok, reason) == (False, f"HALT_SECURITY_SENSITIVE_CONSTANT_VIOLATION:{label}")


def test_steward_removed_or_false_values_are_allowed(approver) -> None:
    _, guard = approver
    for diff in ("- let k = \"-----BEGIN PRIVATE KEY-----\"\n+ let k = loadFromKeychain()",
                 "+ <key>NSAllowsArbitraryLoads</key><false/>",
                 "--- a/x\n+++ b/x\n- NSAllowsArbitraryLoads = true\n+ NSAllowsArbitraryLoads = false"):
        assert guard.evaluate_ios_proposal(IOSProposal("Sources/Net.swift", diff)) == (
            True, "OK_IOS_REFLECTIVE_SHELL_AUTHORIZED"), diff


def test_steward_secret_scan_applies_even_with_valid_approval(approver) -> None:
    key, guard = approver
    prop = IOSProposal("App/Info.plist", "+ <key>NSAllowsArbitraryLoads</key><true/>")
    sig = IOSStewardGuard.sign_approval(prop, key)
    ok, reason = guard.evaluate_ios_proposal(IOSProposal(prop.target_file_path, prop.proposed_diff, sig))
    assert (ok, reason) == (False, "HALT_SECURITY_SENSITIVE_CONSTANT_VIOLATION:NSAllowsArbitraryLoads_ATS_BYPASS")


@pytest.mark.parametrize("path,prefix", [
    ("", "HALT_INVALID_EMPTY_PATH"), ("   ", "HALT_INVALID_EMPTY_PATH"),
    ("/etc/Info.plist", "HALT_PATH_TRAVERSAL_IN_TARGET"), ("../Info.plist", "HALT_PATH_TRAVERSAL_IN_TARGET"),
    ("a/../../Info.plist", "HALT_PATH_TRAVERSAL_IN_TARGET"), ("..", "HALT_PATH_TRAVERSAL_IN_TARGET"),
    ("App\\Info.plist", "HALT_NON_POSIX_OR_NUL_PATH"), ("App/Info.plist\x00.txt", "HALT_NON_POSIX_OR_NUL_PATH"),
])
def test_steward_bad_paths(approver, path: str, prefix: str) -> None:
    _, guard = approver
    ok, reason = guard.evaluate_ios_proposal(IOSProposal(path, "+ x"))
    assert ok is False and reason.startswith(prefix)


def test_steward_non_text_diff_and_caid(approver) -> None:
    _, guard = approver
    assert guard.evaluate_ios_proposal(IOSProposal("a.swift", b"+x")) == (False, "HALT_DIFF_NOT_TEXT")  # type: ignore[arg-type]
    p = IOSProposal("Sources/A.swift", "+ x")
    c1 = IOSStewardGuard.compute_proposal_caid(p)
    assert c1 == IOSStewardGuard.compute_proposal_caid(IOSProposal("Sources/./A.swift", "+ x"))
    assert len(c1) == 71 and c1.startswith("sha256:")
    assert c1 != IOSStewardGuard.compute_proposal_caid(IOSProposal("Sources/A.swift", "+ y"))
    assert c1 != IOSStewardGuard.compute_proposal_caid(IOSProposal("Sources/B.swift", "+ x"))
    with pytest.raises(ValueError, match="HALT_PATH_TRAVERSAL"):
        IOSStewardGuard.compute_proposal_caid(IOSProposal("../x", "+ x"))
    assert IOSStewardGuard.added_lines("--- a\n+++ b\n+new\n-old\n ctx") == ("new",)
    assert IOSStewardGuard.added_lines("plain\ncontent") == ("plain", "content")


# ============================================================================
# 3. Sphinx Swift extractor
# ============================================================================

SWIFT_FIXTURE = r'''
// func commentedOut() { throw E() } 9999
/* outer /* nested func nestedFunc() 8888 */ still comment func stillComment() 7777 */
let s = "func inString() guard 6666 \" func afterEscape() 5555"
let raw = #"func inRaw() "quoted" 4444"#
let multi = """
func inMulti() throw 3333
"""
func realFunction<T>(x: T) throws -> Int {
    guard let v = Optional(30) else { throw RealError() }
    let ratio = 1.25
    let id2x = 10
    return v + 5 + 120
}
'''


def test_sphinx_lexer_blanks_comments_and_strings() -> None:
    ch = SphinxSwiftASTParser.extract_challenge(SWIFT_FIXTURE)
    assert ch.extracted_func_names == ("realFunction",)
    assert ch.extracted_guard_throws == ("guard", "throw", "throws")
    assert ch.extracted_timeout_ints == (10, 30, 120)
    assert ch.challenge_caid.startswith("sha256:") and len(ch.challenge_caid) == 71
    stripped = SphinxSwiftASTParser.strip_comments_and_strings(SWIFT_FIXTURE)
    assert stripped.count("\n") == SWIFT_FIXTURE.count("\n")
    for token in ("9999", "8888", "7777", "6666", "5555", "4444", "3333"):
        assert token not in stripped


def test_sphinx_unterminated_constructs_do_not_leak() -> None:
    for src in ("/* open comment func a()", "let s = \"open func b()", "let r = #\"open func c()",
                "let m = \"\"\"\nfunc d()"):
        assert SphinxSwiftASTParser.extract_challenge(src).extracted_func_names == ()


def test_sphinx_attestation_and_caid_sensitivity() -> None:
    ch = SphinxSwiftASTParser.extract_challenge(SWIFT_FIXTURE)
    good = (["realFunction"], ["guard", "throw", "throws"], [10, 30, 120])
    assert SphinxSwiftASTParser.verify_reviewer_attestation(ch, *good) == (
        True, "OK_REVIEWER_ATTESTATION_MATCHES_AST")
    assert SphinxSwiftASTParser.verify_reviewer_attestation(ch, ["x"], good[1], good[2]) == (
        False, "HALT_COGNITIVE_DEBT_FUNCTION_MISMATCH")
    assert SphinxSwiftASTParser.verify_reviewer_attestation(ch, good[0], ["guard"], good[2]) == (
        False, "HALT_COGNITIVE_DEBT_GUARD_MISMATCH")
    assert SphinxSwiftASTParser.verify_reviewer_attestation(ch, good[0], good[1], [10, 30]) == (
        False, "HALT_COGNITIVE_DEBT_INT_CONSTANT_MISMATCH")
    assert SphinxSwiftASTParser.verify_reviewer_attestation(ch, good[0], good[1], [10, 30, 120, True]) == (
        False, "HALT_COGNITIVE_DEBT_INT_CONSTANT_MISMATCH")
    ch2 = SphinxSwiftASTParser.extract_challenge(SWIFT_FIXTURE + "\n")
    assert ch2.extracted_func_names == ch.extracted_func_names
    assert ch2.challenge_caid != ch.challenge_caid
    with pytest.raises(TypeError, match="ERR_SWIFT_SOURCE_NOT_TEXT"):
        SphinxSwiftASTParser.extract_challenge(b"func a()")  # type: ignore[arg-type]
    with pytest.raises(FrozenInstanceError):
        ch.challenge_caid = "x"  # type: ignore[misc]


# ============================================================================
# 4. XCTest tamper guard (real git worktree)
# ============================================================================

BASE_TEST = """import XCTest
final class LoginTests: XCTestCase {
    func testLogin() {
        XCTAssertEqual(login(), 200)
    }
    func testTimeout() {
        XCTAssertTrue(timedOut())
    }
}
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, timeout=30)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "AppTests").mkdir(parents=True)
    (r / "Sources").mkdir()
    (r / "AppTests" / "LoginTests.swift").write_text(BASE_TEST)
    (r / "Sources" / "Login.swift").write_text("func login() -> Int { 200 }\n")
    _git(r, "init", "-q")
    _git(r, "add", ".")
    _git(r, "commit", "-q", "-m", "base")
    return r


def _bundle(repo: Path, name: str = "Run.xcresult") -> str:
    b = repo / name
    (b / "Data").mkdir(parents=True)
    (b / "Info.plist").write_text("<plist/>")
    (b / "Data" / "data.0").write_bytes(b"\x00\x01result")
    return name


def test_xctest_is_test_file() -> None:
    yes = ["AppTests/LoginTests.swift", "Foo/BarTest.swift", "AppUITests/Flow.swift", "Pkg/Tests/X/Y.swift"]
    no = ["Sources/Login.swift", "Sources/LatestTester.swift", "docs/Tests.md", "AppTests/notes.txt"]
    assert all(XCTestTamperGuard.is_xctest_file(p) for p in yes)
    assert not any(XCTestTamperGuard.is_xctest_file(p) for p in no)


def test_xctest_reads_real_worktree_diff(repo: Path) -> None:
    g = XCTestTamperGuard(str(repo))
    f = repo / "AppTests" / "LoginTests.swift"
    assert g.evaluate_path("AppTests/LoginTests.swift").disposition == ALLOW  # unchanged
    f.write_text(BASE_TEST.replace("        XCTAssertEqual(login(), 200)\n", ""))
    v = g.evaluate_path("AppTests/LoginTests.swift")
    assert (v.disposition, v.reason) == (HALT, "HALT_XCTEST_REWARD_HACKING_ATTEMPT:ASSERTION_DELETION")
    f.write_text(BASE_TEST.replace("XCTAssertEqual(login(), 200)", "XCTAssertTrue(true)"))
    assert g.evaluate_path("AppTests/LoginTests.swift").reason.endswith("TAUTOLOGY_ASSERTION_INJECTION")
    f.write_text(BASE_TEST.replace("    func testTimeout() {\n        XCTAssertTrue(timedOut())\n    }\n", ""))
    assert g.evaluate_path("AppTests/LoginTests.swift").reason.endswith("TEST_CASE_DELETION")
    f.write_text(BASE_TEST.replace("XCTAssertEqual(login(), 200)", "XCTAssertEqual(login(), 200)\n        XCTAssertNotNil(token())"))
    v = g.evaluate_path("AppTests/LoginTests.swift")
    assert (v.disposition, v.reason) == (ALLOW, "OK_XCTEST_MUTATION_COMPLIANT")
    (repo / "Sources" / "Login.swift").write_text("func login() -> Int { 500 }\n")
    assert g.evaluate_path("Sources/Login.swift").reason == "OK_NON_TEST_FILE_MUTATION"


def test_xctest_fails_closed_on_unreadable_diff(repo: Path, tmp_path: Path) -> None:
    g = XCTestTamperGuard(str(repo))
    for p in ("../outside.swift", "/etc/passwd", "", "a\x00b"):
        v = g.evaluate_path(p)
        assert v.disposition == HALT and v.reason.startswith("HALT_CANNOT_READ_DIFF"), p
    not_repo = tmp_path / "plain"
    not_repo.mkdir()
    assert XCTestTamperGuard(str(not_repo)).evaluate_path("x.swift").reason == "HALT_CANNOT_READ_DIFF:RuntimeError"
    with pytest.raises(ValueError, match="ERR_INVALID_REPO_ROOT"):
        XCTestTamperGuard("")


def test_xctest_escalation_requires_real_bundle(repo: Path, tmp_path: Path) -> None:
    g = XCTestTamperGuard(str(repo))
    (repo / "AppTests" / "LoginTests.swift").write_text(BASE_TEST.replace("        XCTAssertEqual(login(), 200)\n", ""))
    p = "AppTests/LoginTests.swift"
    name = _bundle(repo)
    assert g.evaluate_path(p, escalation_reason="", xcresult_bundle_path=name).reason == "HALT_XCTEST_ESCALATION_MISSING_REASON"
    assert g.evaluate_path(p, xcresult_bundle_path=name).reason == "HALT_XCTEST_ESCALATION_MISSING_REASON"
    bad = "HALT_XCTEST_ESCALATION_MISSING_OR_INVALID_XCRESULT"
    assert g.evaluate_path(p, escalation_reason="spec changed").reason == bad
    assert g.evaluate_path(p, escalation_reason="spec changed", xcresult_bundle_path="Missing.xcresult").reason == bad
    (repo / "NotABundle").mkdir()
    (repo / "NotABundle" / "f").write_text("x")
    assert g.evaluate_path(p, escalation_reason="r", xcresult_bundle_path="NotABundle").reason == bad
    (repo / "Empty.xcresult").mkdir()
    assert g.evaluate_path(p, escalation_reason="r", xcresult_bundle_path="Empty.xcresult").reason == bad
    outside = tmp_path / "Out.xcresult"
    outside.mkdir()
    (outside / "f").write_text("x")
    assert g.evaluate_path(p, escalation_reason="r", xcresult_bundle_path=str(outside)).reason == bad
    assert g.evaluate_path(p, escalation_reason="r", xcresult_bundle_path="../Out.xcresult").reason == bad
    linked = _bundle(repo, "Linked.xcresult")
    (repo / linked / "evil").symlink_to("/etc/hosts")
    assert g.evaluate_path(p, escalation_reason="r", xcresult_bundle_path=linked).reason == bad

    v = g.evaluate_path(p, escalation_reason="upstream API changed", xcresult_bundle_path=name)
    assert v.disposition == ESCALATE
    assert v.reason == "ESCALATE_CONTRADICTORY_SPEC_OR_BROKEN_ORACLE:ASSERTION_DELETION"
    assert v.xcresult_digest == g.digest_xcresult_bundle(name)
    receipt = XCTestTamperGuard.escalation_receipt(p, v, "upstream API changed")
    assert receipt["xcresult_bundle_digest"] == v.xcresult_digest and receipt["receipt_caid"].startswith("sha256:")
    (repo / name / "Data" / "data.0").write_bytes(b"tampered")
    assert g.digest_xcresult_bundle(name) != v.xcresult_digest
    with pytest.raises(ValueError, match="ERR_RECEIPT_REQUIRES_ESCALATE_VERDICT"):
        XCTestTamperGuard.escalation_receipt(p, g.evaluate_path(p), "r")


# ============================================================================
# 5. Incident emitter
# ============================================================================

# SYNTHETIC .ips fixtures. Key names (procName, exception.type/signal/subtype,
# termination.namespace/code, asi) were observed in a real .ips on this host
# (macOS 27.2) and in Apple's "Interpreting the JSON format of a crash report".
def _ips(body: str) -> str:
    return '{"bug_type":"309","app_name":"SovereignApp","incident_id":"X"}\n' + body


@pytest.mark.parametrize("content,sev,reason", [
    (_ips('{"procName":"SovereignApp","exception":{"type":"EXC_BAD_ACCESS","signal":"SIGSEGV",'
          '"subtype":"KERN_INVALID_ADDRESS at 0x0000000000000010"},"termination":{"namespace":"SIGNAL","code":11}}'),
     "SEV_1_CRITICAL", "HALT_IOS_MEMORY_FAULT_EXC_BAD_ACCESS"),
    (_ips('{"procName":"SovereignApp","exception":{"type":"EXC_BREAKPOINT","signal":"SIGTRAP"},'
          '"asi":{"libswiftCore.dylib":["Fatal error: Unexpectedly found nil"]}}'),
     "SEV_1_CRITICAL", "HALT_IOS_SWIFT_FATAL_ERROR"),
    (_ips('{"procName":"SovereignApp","exception":{"type":"EXC_CRASH","signal":"SIGKILL"},'
          '"termination":{"namespace":"FRONTBOARD","code":2343432205}}'),
     "SEV_2_HIGH", "HALT_IOS_WATCHDOG_TIMEOUT"),
    (_ips('{"procName":"SovereignApp","exception":{"type":"EXC_CRASH","signal":"SIGKILL"},'
          '"termination":{"namespace":"RUNNINGBOARD","code":3735883980}}'),
     "SEV_2_HIGH", "HALT_IOS_BACKGROUND_LOCK_VIOLATION"),
    (_ips('{"procName":"SovereignApp","exception":{"type":"EXC_GUARD"},'
          '"termination":{"namespace":"LIBSYSTEM","code":5}}'),
     "SEV_3_MEDIUM", "HALT_IOS_UNKNOWN_CRASH_SIGNAL"),
])
def test_incident_parses_json_ips(content: str, sev: str, reason: str) -> None:
    s, r, meta = IOSIncidentEmitter.parse_ips_crash_report(content)
    assert (s, r) == (sev, reason)
    assert meta["format"] == "ips_json" and meta["process_name"] == "SovereignApp"
    assert meta["raw_length"] == len(content)


def test_incident_json_fields_and_legacy_fallback() -> None:
    _, _, meta = IOSIncidentEmitter.parse_ips_crash_report(_ips(
        '{"procName":"SovereignApp","exception":{"type":"EXC_BAD_ACCESS","signal":"SIGSEGV",'
        '"subtype":"KERN_INVALID_ADDRESS at 0x0000000000000010"}}'))
    assert meta["exception_type"] == "EXC_BAD_ACCESS (SIGSEGV)" and meta["fault_address"] == "0x0000000000000010"
    legacy = ("Process: SovereignApp [4129]\nException Type: EXC_BAD_ACCESS (SIGSEGV)\n"
              "Exception Codes: KERN_INVALID_ADDRESS at 0x0000000000000008\n")
    s, r, meta = IOSIncidentEmitter.parse_ips_crash_report(legacy)
    assert (s, r, meta["format"], meta["fault_address"]) == (
        "SEV_1_CRITICAL", "HALT_IOS_MEMORY_FAULT_EXC_BAD_ACCESS", "legacy_text", "0x0000000000000008")
    # header-only / malformed JSON body falls back to legacy text parsing
    s, r, meta = IOSIncidentEmitter.parse_ips_crash_report('{"bug_type":"309"}\n{not json')
    assert meta["format"] == "legacy_text" and r == "HALT_IOS_UNKNOWN_CRASH_SIGNAL"
    assert IOSIncidentEmitter.parse_ips_crash_report("")[:2] == ("SEV_4_LOW", "HALT_IOS_EMPTY_CRASH_REPORT")
    big = "A" * (IOSIncidentEmitter.MAX_IPS_BYTES + 1)
    assert IOSIncidentEmitter.parse_ips_crash_report(big)[:2] == ("SEV_3_MEDIUM", "HALT_IOS_CRASH_REPORT_OVERSIZE")


def _notice(key, **over):
    kw = dict(incident_id="INC-IOS-1", severity_tier="SEV_1_CRITICAL",
              halt_reason_code="HALT_IOS_MEMORY_FAULT_EXC_BAD_ACCESS", process_name="SovereignApp",
              exception_type="EXC_BAD_ACCESS (SIGSEGV)", fault_address="0x10",
              containment_latency_us=420, evidence_bundle_caid="sha256:" + "b" * 64, signing_key=key)
    kw.update(over)
    return IOSIncidentEmitter.emit_incident_notice(**kw)


def test_incident_signed_notice_red_team() -> None:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes_raw().hex()
    n = _notice(key)
    assert IOSIncidentEmitter.verify_incident_notice(n, pub) is True
    # tamper a signed field
    assert IOSIncidentEmitter.verify_incident_notice({**n, "severity_tier": "SEV_3_MEDIUM"}, pub) is False
    # modify-and-rehash forgery: attacker recomputes CAID but cannot re-sign
    forged = {**n, "process_name": "Other"}
    body = {k: forged[k] for k in IOSIncidentEmitter._SIGNED_FIELDS}
    import hashlib
    from src.jcs_canonicalizer import encode_jcs
    forged["notification_caid"] = "sha256:" + hashlib.sha256(encode_jcs(body)).hexdigest()
    assert IOSIncidentEmitter.verify_incident_notice(forged, pub) is False
    # attacker-key re-signed notice rejected by pinned key
    evil = Ed25519PrivateKey.generate()
    assert IOSIncidentEmitter.verify_incident_notice(_notice(evil), pub) is False
    # signature bit flip, bad hex, extra / missing keys
    flipped = n["signature_hex"][:-1] + ("0" if n["signature_hex"][-1] != "0" else "1")
    assert IOSIncidentEmitter.verify_incident_notice({**n, "signature_hex": flipped}, pub) is False
    assert IOSIncidentEmitter.verify_incident_notice({**n, "signature_hex": "zz"}, pub) is False
    assert IOSIncidentEmitter.verify_incident_notice({**n, "extra": 1}, pub) is False
    assert IOSIncidentEmitter.verify_incident_notice({k: v for k, v in n.items() if k != "fault_address"}, pub) is False
    assert IOSIncidentEmitter.verify_incident_notice({**n, "notification_caid": "sha256:" + "0" * 64}, pub) is False


@pytest.mark.parametrize("over", [
    {"severity_tier": "SEV_9"}, {"containment_latency_us": -1}, {"containment_latency_us": True},
    {"containment_latency_us": 1.5}, {"halt_reason_code": "OK_X"}, {"incident_id": " "},
    {"evidence_bundle_caid": "sha256:not-hex"}, {"process_name": ""}, {"exception_type": " "},
    {"fault_address": ""},
])
def test_incident_emission_rejects_invalid_fields(over) -> None:
    with pytest.raises(ValueError, match="ERR_INVALID_IOS_INCIDENT_NOTICE_FIELDS"):
        _notice(Ed25519PrivateKey.generate(), **over)


# ============================================================================
# 6. Mutation-hardening tests (each targets a surviving mutant; see report)
# ============================================================================


@pytest.mark.parametrize("src,expected", [
    ("a//c\nb", "a   \nb"),
    ("a//c", "a   "),
    ("x/*1/*2*/3*/y", "x" + " " * 11 + "y"),
    ("/* c */func a()", " " * 7 + "func a()"),
    ('p"a\\"b"q', "p" + " " * 6 + "q"),
    ('r#"a"b"#s', "r" + " " * 7 + "s"),
    ('u"""\nx\n"""v', "u   \n \n   v"),
    ('"ab\nc', "   \nc"),
    ('k"\\\\"m', "k" + " " * 4 + "m"),
    ('#""#x', "    x"),
    ('#"#a"#x', "      x"),
    ('""""""x', "      x"),
])
def test_sphinx_lexer_exact_output(src: str, expected: str) -> None:
    out = SphinxSwiftASTParser.strip_comments_and_strings(src)
    assert out == expected
    assert len(out) == len(src)


def test_steward_removal_only_diff_is_not_rescanned_as_content(approver) -> None:
    _, guard = approver
    diff = "- let k = \"-----BEGIN PRIVATE KEY-----\""
    assert IOSStewardGuard.added_lines(diff) == ()
    assert guard.evaluate_ios_proposal(IOSProposal("Sources/K.swift", diff)) == (
        True, "OK_IOS_REFLECTIVE_SHELL_AUTHORIZED")
    with pytest.raises(FrozenInstanceError):
        IOSProposal("a", "b").proposed_diff = "c"  # type: ignore[misc]


def test_xctest_verdict_is_frozen(repo: Path) -> None:
    v = XCTestTamperGuard(str(repo)).evaluate_path("Sources/Login.swift")
    with pytest.raises(FrozenInstanceError):
        v.disposition = HALT  # type: ignore[misc]


def test_incident_parser_boundaries() -> None:
    limit = 8 * 1024 * 1024
    assert IOSIncidentEmitter.MAX_IPS_BYTES == limit
    s, r, meta = IOSIncidentEmitter.parse_ips_crash_report("B" * (limit + 1))
    assert (s, r, meta) == ("SEV_3_MEDIUM", "HALT_IOS_CRASH_REPORT_OVERSIZE", {"parsed_successfully": False})
    assert IOSIncidentEmitter.parse_ips_crash_report("B" * limit)[1] == "HALT_IOS_UNKNOWN_CRASH_SIGNAL"
    # non-dict JSON header with dict body falls back to legacy parsing
    _, _, meta = IOSIncidentEmitter.parse_ips_crash_report('[1]\n{"procName":"X","exception":{"type":"EXC_BAD_ACCESS"}}')
    assert meta["format"] == "legacy_text"
    _, _, meta = IOSIncidentEmitter.parse_ips_crash_report('{"bug_type":"309"}\n[1]')
    assert meta["format"] == "legacy_text"
    # termination code given as a string is still matched
    s, r, _ = IOSIncidentEmitter.parse_ips_crash_report(_ips(
        '{"procName":"A","exception":{"type":"EXC_CRASH"},"termination":{"code":"0x8badf00d"}}'))
    assert r == "HALT_IOS_WATCHDOG_TIMEOUT"


def test_incident_latency_zero_ok_and_invalid_body_rejected_on_verify() -> None:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes_raw().hex()
    n = _notice(key, containment_latency_us=0)
    assert IOSIncidentEmitter.verify_incident_notice(n, pub) is True
    assert IOSIncidentEmitter.verify_incident_notice({**n, "severity_tier": "SEV_9"}, pub) is False


# ============================================================================
# 7. Seatbelt (macOS sandbox-exec) enforcement — real kernel sandbox, no mocks
# ============================================================================

HAS_SEATBELT = os.path.isfile("/usr/bin/sandbox-exec")


def test_harness_sandbox_mode_validation_and_wrap(ws: Path) -> None:
    with pytest.raises(ValueError, match="ERR_INVALID_SANDBOX_MODE"):
        SovereignXcodeHarness(str(ws), sandbox_mode="off")
    plain = SovereignXcodeHarness(str(ws), sandbox_mode="process_isolation_only")
    assert plain.wrap_argv(["/usr/bin/true"]) == (["/usr/bin/true"], "")
    h = SovereignXcodeHarness(str(ws))
    assert h.sandbox_mode == "seatbelt_required"
    if HAS_SEATBELT:
        argv, reason = h.wrap_argv(["/usr/bin/true"])
        assert reason == "" and argv[0] == "/usr/bin/sandbox-exec" and argv[-1] == "/usr/bin/true"
        assert argv[1:3] == ["-D", f"WRITABLE_0={os.path.realpath(str(ws))}"]
        prof = argv[argv.index("-p") + 1]
        assert "(deny network*)" in prof and "(deny file-write*)" in prof
        assert '(subpath (param "WRITABLE_0"))' in prof
        assert os.path.realpath(str(ws)) not in prof  # paths are parameters, not spliced text


def test_harness_seatbelt_rejects_newline_path(tmp_path: Path) -> None:
    d = tmp_path / "we\nird"
    d.mkdir()
    h = SovereignXcodeHarness(str(d))
    with pytest.raises(ValueError, match="ERR_PATH_NOT_SAFE_FOR_SBPL"):
        h.seatbelt_profile()
    if HAS_SEATBELT:
        assert h.wrap_argv(["/usr/bin/true"]) == (None, "HALT_SEATBELT_PROFILE_INVALID:ERR_PATH_NOT_SAFE_FOR_SBPL")
        if HAS_SWIFTC:
            assert h.dispatch_sandboxed_tool(_req(d, XcodeActionType.SWIFT_TYPECHECK)) == (
                False, "", "HALT_SEATBELT_PROFILE_INVALID:ERR_PATH_NOT_SAFE_FOR_SBPL")


@pytest.mark.skipif(not HAS_SEATBELT, reason="sandbox-exec not on host")
def test_seatbelt_quote_in_path_is_safe_and_git_dir_is_read_only(tmp_path: Path) -> None:
    d = tmp_path / 'we"ird'
    (d / ".git").mkdir(parents=True)
    h = SovereignXcodeHarness(str(d))
    argv, reason = h.wrap_argv(["/bin/sh", "-c", 'echo a > in.txt; echo b > .git/hooks_pwn'])
    assert reason == ""
    subprocess.run(argv, cwd=str(d), capture_output=True, timeout=30, env=h.sanitized_env(), check=False)
    assert (d / "in.txt").read_text() == "a\n"
    assert not (d / ".git" / "hooks_pwn").exists()


def _outside_writable_dir(h: SovereignXcodeHarness) -> Path:
    """Real home dir from the password database (not $HOME, which a caller may
    point into an allowed temp dir). Precondition: not inside any writable root."""
    import pwd
    home = Path(os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir))
    _, params = h.seatbelt_profile()
    roots = [p.split("=", 1)[1] for p in params if p != "-D"]
    assert all(os.path.commonpath([r, str(home)]) != r for r in roots), (home, roots)
    return home


@pytest.mark.skipif(not HAS_SEATBELT, reason="sandbox-exec not on host")
def test_seatbelt_denies_writes_outside_workspace_and_local_network(ws: Path) -> None:
    import socket
    import uuid
    h = SovereignXcodeHarness(str(ws))
    outside = _outside_writable_dir(h) / f".aeib_seatbelt_probe_{uuid.uuid4().hex}"
    try:
        argv, _ = h.wrap_argv(["/bin/sh", "-c", f'echo in > "{ws}/in.txt"; echo out > "{outside}"'])
        subprocess.run(argv, capture_output=True, timeout=30, env=h.sanitized_env(), check=False)
        assert (ws / "in.txt").read_text() == "in\n"
        assert not outside.exists()
    finally:
        if outside.exists():
            outside.unlink()
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = str(srv.getsockname()[1])
    try:
        plain = subprocess.run(["/usr/bin/nc", "-z", "-w", "2", "127.0.0.1", port], capture_output=True, timeout=10)
        argv, _ = h.wrap_argv(["/usr/bin/nc", "-z", "-w", "2", "127.0.0.1", port])
        boxed = subprocess.run(argv, capture_output=True, timeout=10)
    finally:
        srv.close()
    assert plain.returncode == 0  # control: the port is reachable without the sandbox
    assert boxed.returncode != 0


@pytest.mark.skipif(not (HAS_SEATBELT and HAS_SWIFTC), reason="needs sandbox-exec and swiftc")
def test_seatbelt_swiftc_works_inside_but_cannot_write_outside(ws: Path) -> None:
    import uuid
    h = SovereignXcodeHarness(str(ws))
    (ws / "good.swift").write_text("let x: Int = 1\nprint(x)\n")
    ok, _, reason = h.dispatch_sandboxed_tool(
        _req(ws, XcodeActionType.SWIFT_TYPECHECK, extra_arguments=("good.swift",)), timeout=180)
    assert (ok, reason) == (True, "OK_TOOL_EXECUTION_SUCCESS")
    # Same compile, but the module cache is forced outside the workspace: the
    # argument check would reject an absolute path, so drive argv directly.
    outside = _outside_writable_dir(h) / f".aeib_seatbelt_cache_{uuid.uuid4().hex}"
    try:
        argv, _ = h.wrap_argv(["/usr/bin/swiftc", "-typecheck", "good.swift", "-module-cache-path", str(outside)])
        res = subprocess.run(argv, cwd=str(ws), env=h.sanitized_env(), capture_output=True, text=True, timeout=180)
        assert res.returncode != 0
        assert "Operation not permitted" in res.stderr
        assert not outside.exists()
    finally:
        if outside.exists():
            shutil.rmtree(outside)


# ============================================================================
# 8. Pinned test oracle over the whole worktree
# ============================================================================


def test_xctest_expected_value_change_is_caught_without_lexical_pattern(repo: Path) -> None:
    g = XCTestTamperGuard(str(repo))
    (repo / "AppTests" / "LoginTests.swift").write_text(BASE_TEST.replace("200)", "500)"))
    v = g.evaluate_path("AppTests/LoginTests.swift")
    # the old lexical rules see an XCTAssertEqual deletion; a pure value edit in a
    # helper line is caught by the pinned-oracle rule:
    assert v.disposition == HALT
    (repo / "AppTests" / "LoginTests.swift").write_text(BASE_TEST.replace("final class", "// tweak\nfinal  class"))
    v = g.evaluate_path("AppTests/LoginTests.swift")
    assert (v.disposition, v.reason) == (HALT, "HALT_XCTEST_REWARD_HACKING_ATTEMPT:EXISTING_TEST_LINE_MODIFIED")


def test_xctest_worktree_scan_covers_delete_rename_new_and_other_tools(repo: Path) -> None:
    g = XCTestTamperGuard(str(repo))
    assert g.evaluate_worktree() == ()
    (repo / "AppTests" / "NewFlowTests.swift").write_text("import XCTest\n")
    (repo / "Sources" / "Login.swift").write_text("func login() -> Int { 1 }\n")
    reasons = sorted(v.reason for v in g.evaluate_worktree())
    assert reasons == ["OK_NEW_TEST_FILE:AppTests/NewFlowTests.swift"]
    _git(repo, "mv", "AppTests/LoginTests.swift", "AppTests/Renamed.swift")
    verdicts = g.evaluate_worktree()
    assert any(v.disposition == HALT and v.reason.endswith("TEST_FILE_DELETED:AppTests/LoginTests.swift")
               for v in verdicts)
    _git(repo, "mv", "AppTests/Renamed.swift", "AppTests/LoginTests.swift")
    (repo / "AppTests" / "LoginTests.swift").unlink()
    assert [v.reason for v in g.evaluate_worktree() if v.disposition == HALT] == [
        "HALT_XCTEST_REWARD_HACKING_ATTEMPT:TEST_FILE_DELETED:AppTests/LoginTests.swift"]


def test_xctest_worktree_fails_closed_outside_git(tmp_path: Path) -> None:
    d = tmp_path / "nogit"
    d.mkdir()
    (v,) = XCTestTamperGuard(str(d)).evaluate_worktree()
    assert (v.disposition, v.reason) == (HALT, "HALT_CANNOT_READ_WORKTREE:RuntimeError")


def test_xctest_resolve_inside_repo_contract(repo: Path, tmp_path: Path) -> None:
    g = XCTestTamperGuard(str(repo))
    for bad in ("", "   ", "a\x00b", "/etc/passwd", "../x", None):
        assert g._resolve_inside_repo(bad) is None, bad  # type: ignore[arg-type]
    assert g._resolve_inside_repo("AppTests/LoginTests.swift") == os.path.realpath(
        str(repo / "AppTests" / "LoginTests.swift"))


def test_dispatch_guarded_tool_wires_steward_and_xctest_worktree(repo: Path) -> None:
    h = SovereignXcodeHarness(str(repo))
    # 1. Blocked by IOSStewardGuard when an unapproved authority diff is proposed
    ok, _, reason = h.dispatch_guarded_tool(
        _req(repo, XcodeActionType.SWIFT_TYPECHECK),
        proposals=(IOSProposal("App/Info.plist", "+ <key>CFBundleVersion</key>"),),
    )
    assert (ok, reason) == (False, "HALT_IOS_INVARIANT_CORE_MUTATION_FORBIDDEN:App/Info.plist")

    # 2. Blocked by XCTestTamperGuard when an existing test file is modified in the git worktree
    (repo / "AppTests" / "LoginTests.swift").write_text(BASE_TEST.replace("200)", "500)"))
    ok, _, reason = h.dispatch_guarded_tool(_req(repo, XcodeActionType.SWIFT_TYPECHECK))
    assert (ok, reason) == (
        False,
        "HALT_WORKTREE_XCTEST_TAMPER:HALT_XCTEST_REWARD_HACKING_ATTEMPT:ASSERTION_DELETION",
    )

    # 3. Clean worktree + reflective-shell proposal passes pre-dispatch guards
    (repo / "AppTests" / "LoginTests.swift").write_text(BASE_TEST)
    if HAS_SWIFTC:
        ok, _, reason = h.dispatch_guarded_tool(
            _req(repo, XcodeActionType.SWIFT_TYPECHECK),
            proposals=(IOSProposal("Sources/Login.swift", "+ let clean = 1"),),
            timeout=60,
        )
        assert (ok, reason) == (True, "OK_TOOL_EXECUTION_SUCCESS")


def test_harness_accepts_path_like_argument_inside_workspace(ws: Path) -> None:
    """Kills `_inside_root -> None`: a valid relative path containing '/' must be accepted."""
    (ws / "Sources").mkdir()
    h = SovereignXcodeHarness(str(ws))
    cmd, reason = h.build_command(_req(ws, XcodeActionType.SWIFT_TYPECHECK, extra_arguments=("Sources/a.swift",)))
    assert (cmd, reason) == (["swiftc", "-typecheck", "Sources/a.swift"], "")
    assert h._inside_root("Sources/a.swift") is True
    assert h._inside_root("../outside.swift") is False


@pytest.mark.skipif(not os.path.isfile("/usr/bin/getconf") or os.uname().sysname != "Darwin",
                    reason="needs macOS getconf")
def test_darwin_user_cache_dir_is_resolved_and_writable_in_profile(ws: Path) -> None:
    """Kills getconf-branch mutants: the per-user cache dir is resolved for a valid name,
    None for an invalid name, and appears as WRITABLE_1 in the Seatbelt profile."""
    from src.ios_xcode_harness import _darwin_user_dir
    cache = _darwin_user_dir("DARWIN_USER_CACHE_DIR")
    assert cache is not None and os.path.isdir(cache) and cache == os.path.realpath(cache)
    assert _darwin_user_dir("AEIB_NOT_A_GETCONF_NAME") is None
    _, params = SovereignXcodeHarness(str(ws)).seatbelt_profile()
    assert params == ["-D", f"WRITABLE_0={os.path.realpath(str(ws))}", "-D", f"WRITABLE_1={cache}"]
