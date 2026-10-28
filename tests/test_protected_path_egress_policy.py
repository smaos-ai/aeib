"""Tests for src/protected_path_egress_policy.py (no network is used)."""

import ipaddress
import os

import pytest

from src import protected_path_egress_policy as p
from src.protected_path_egress_policy import (
    PolicyDecision, ProtectedPathEgressPolicy, normalize_host,
)


@pytest.fixture()
def ws(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    return root


@pytest.fixture()
def pol(ws):
    return ProtectedPathEgressPolicy(str(ws))


# ------------------------------------------------------------------ paths
@pytest.mark.parametrize("rel", [
    "src/app.py", "src/new_file.py", "docs/readme.md", "new_dir/deep/file.txt",
    "src/agents.py", "environment.md", "my.env.txt", "github/workflows/x.yml",
    "scripts/hook.sh", "hooks/scripts/x", "src/git/x", "src/cursor.py",
    "mcp.json.bak", "notes/claude.txt", "src/../src/app.py", "./src/app.py",
])
def test_ordinary_writes_allowed(pol, ws, rel):
    res = pol.evaluate_write(rel)
    assert res.decision is PolicyDecision.ALLOW, res
    assert res.reason_code == p.PATH_ALLOWED
    assert res.matched_rule is None
    assert res.resolved_path == os.path.realpath(os.path.join(str(ws), rel))
    assert not res.relative_path.startswith("..")


@pytest.mark.parametrize("rel,rule", [
    (".cursor/mcp.json", "dir:.cursor"),
    (".cursor/rules/x.mdc", "dir:.cursor"),
    (".Cursor/MCP.json", "dir:.cursor"),
    (".claude/settings.json", "dir:.claude"),
    (".agents/skills/x/SKILL.md", "dir:.agents"),
    ("sub/.claude/settings.json", "dir:.claude"),
    (".git/hooks/pre-commit", "dir:.git"),
    (".git/config", "dir:.git"),
    ("vendor/lib/.git", "dir:.git"),
    ("mcp.json", "file:mcp.json"),
    ("config/mcp.json", "file:mcp.json"),
    (".mcp.json", "file:.mcp.json"),
    (".vscode/mcp.json", "file:mcp.json"),
    (".github/workflows/ci.yml", "dir:.github/workflows"),
    (".GitHub/Workflows/ci.yml", "dir:.github/workflows"),
    ("pkg/.github/workflows/ci.yml", "dir:.github/workflows"),
    (".gitlab-ci.yml", "file:.gitlab-ci.yml"),
    ("scripts/hooks/pre-push", "dir:scripts/hooks"),
    ("AGENTS.md", "file:agents.md"),
    ("agents.md", "file:agents.md"),
    ("sub/AGENTS.md", "file:agents.md"),
    ("CLAUDE.md", "file:claude.md"),
    ("TRUTH_MANIFESTO.md", "file:truth_manifesto.md"),
    ("docs/truth/ledger.json", "dir:docs/truth"),
    (".env", "file:.env*"),
    (".env.local", "file:.env*"),
    ("svc/.env.production", "file:.env*"),
    (".envrc", "file:.env*"),
])
def test_protected_requires_approval(pol, rel, rule):
    res = pol.evaluate_write(rel)
    assert res.decision is PolicyDecision.REQUIRES_APPROVAL, res
    assert res.reason_code == p.PATH_PROTECTED_REQUIRES_APPROVAL
    assert res.matched_rule == rule


def test_absolute_path_inside_protected(pol, ws):
    res = pol.evaluate_write(str(ws / ".claude" / "settings.json"))
    assert res.decision is PolicyDecision.REQUIRES_APPROVAL
    assert res.relative_path == ".claude/settings.json"


@pytest.mark.parametrize("rel", ["../outside.txt", "src/../../outside", "/etc/passwd", "/tmp/x"])
def test_escapes_denied(pol, rel):
    res = pol.evaluate_write(rel)
    assert res.decision is PolicyDecision.DENY
    assert res.reason_code == p.ERR_PATH_ESCAPES_WORKSPACE


def test_sibling_prefix_is_not_inside(tmp_path):
    """CVE-2025-54794 class: '/repo-evil' must not count as inside '/repo'."""
    root = tmp_path / "repo"
    evil = tmp_path / "repo-evil"
    root.mkdir()
    evil.mkdir()
    pol = ProtectedPathEgressPolicy(str(root))
    res = pol.evaluate_write(str(evil / "payload.sh"))
    assert res.decision is PolicyDecision.DENY
    assert res.reason_code == p.ERR_PATH_ESCAPES_WORKSPACE
    res = pol.evaluate_write("../repo-evil/payload.sh")
    assert res.reason_code == p.ERR_PATH_ESCAPES_WORKSPACE


def test_symlink_out_of_workspace_denied(tmp_path, ws):
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(str(outside), str(ws / "link"))
    pol = ProtectedPathEgressPolicy(str(ws))
    res = pol.evaluate_write("link/file.txt")
    assert res.decision is PolicyDecision.DENY
    assert res.reason_code == p.ERR_PATH_ESCAPES_WORKSPACE
    assert res.resolved_path == os.path.realpath(str(outside / "file.txt"))


def test_symlink_into_protected_requires_approval(ws):
    (ws / ".git").mkdir()
    (ws / ".git" / "config").write_text("")
    os.symlink(str(ws / ".git" / "config"), str(ws / "innocent.txt"))
    pol = ProtectedPathEgressPolicy(str(ws))
    res = pol.evaluate_write("innocent.txt")
    assert res.decision is PolicyDecision.REQUIRES_APPROVAL
    assert res.relative_path == ".git/config"


def test_protected_name_symlinked_elsewhere_still_requires_approval(ws):
    (ws / ".cursor").mkdir()
    os.symlink(str(ws / "src" / "app.py"), str(ws / ".cursor" / "mcp.json"))
    pol = ProtectedPathEgressPolicy(str(ws))
    res = pol.evaluate_write(".cursor/mcp.json")
    assert res.decision is PolicyDecision.REQUIRES_APPROVAL
    assert res.relative_path == "src/app.py"


def test_workspace_root_given_via_symlink(tmp_path, ws):
    alias = tmp_path / "alias"
    os.symlink(str(ws), str(alias))
    pol = ProtectedPathEgressPolicy(str(alias))
    assert pol.workspace_root == os.path.realpath(str(ws))
    assert pol.evaluate_write(str(alias / "src" / "app.py")).decision is PolicyDecision.ALLOW
    assert pol.evaluate_write(str(ws / "src" / "app.py")).decision is PolicyDecision.ALLOW


@pytest.mark.parametrize("bad", ["", None, 3, "src/a\x00b"])
def test_invalid_paths_denied(pol, bad):
    res = pol.evaluate_write(bad)
    assert res.decision is PolicyDecision.DENY
    assert res.reason_code == p.ERR_PATH_INVALID


@pytest.mark.parametrize("rel", [".", "src/..", "./"])
def test_root_target_denied(pol, rel):
    res = pol.evaluate_write(rel)
    assert res.decision is PolicyDecision.DENY
    assert res.reason_code == p.ERR_PATH_IS_WORKSPACE_ROOT
    assert res.relative_path == "."


def test_root_must_be_directory(tmp_path):
    f = tmp_path / "file"
    f.write_text("")
    with pytest.raises(ValueError):
        ProtectedPathEgressPolicy(str(f))
    with pytest.raises(ValueError):
        ProtectedPathEgressPolicy(str(tmp_path / "missing"))


def test_protected_rule_helper():
    assert p._protected_rule("a/b/c.txt") is None
    assert p._protected_rule("") is None
    assert p._protected_rule("./.git") == "dir:.git"
    assert p._protected_rule("scripts/hooks") == "dir:scripts/hooks"
    assert p._protected_rule("hooks/scripts") is None
    assert p._protected_rule("x/.env") == "file:.env*"


# ------------------------------------------------------------------ egress
@pytest.fixture()
def epol(ws):
    return ProtectedPathEgressPolicy(str(ws), egress_allowlist=[
        "api.example.com:443",
        ("pypi.org", 443),
        "*.trusted.example:443",
        "10.1.2.3:8080",
        "[fd00::1]:9000",
        "203.0.113.7:443",
        "xn--bcher-kva.example:443",
    ])


@pytest.mark.parametrize("host,port,entry", [
    ("api.example.com", 443, "api.example.com:443"),
    ("API.Example.COM", 443, "api.example.com:443"),
    ("api.example.com.", 443, "api.example.com:443"),
    ("pypi.org", 443, "pypi.org:443"),
    ("a.trusted.example", 443, "*.trusted.example:443"),
    ("x.y.trusted.example", 443, "*.trusted.example:443"),
    ("10.1.2.3", 8080, "10.1.2.3:8080"),
    ("[fd00::1]", 9000, "fd00::1:9000"),
    ("fd00:0:0::1", 9000, "fd00::1:9000"),
    ("203.0.113.7", 443, "203.0.113.7:443"),
    ("bücher.example", 443, "xn--bcher-kva.example:443"),
    ("BÜCHER.example", 443, "xn--bcher-kva.example:443"),
])
def test_egress_allowed(epol, host, port, entry):
    res = epol.evaluate_egress(host, port)
    assert res.decision is PolicyDecision.ALLOW, res
    assert res.reason_code == p.EGRESS_ALLOWED
    assert res.matched_entry == entry
    assert res.port == port


@pytest.mark.parametrize("host,port,code", [
    ("api.example.com", 80, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("evil.example.com", 443, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("api.example.com.evil.net", 443, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("xapi.example.com", 443, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("trusted.example", 443, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("eviltrusted.example", 443, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("a.trusted.example", 8443, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("169.254.169.254", 80, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("127.0.0.1", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("::1", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("[::1]", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("10.0.0.5", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("10.1.2.3", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("172.16.0.1", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("172.31.255.255", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("192.168.1.1", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("fc00::1", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("fd00:ec2::254", 80, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("fe80::1", 443, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("::ffff:169.254.169.254", 80, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("0.0.0.0", 80, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("100.100.100.200", 80, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("::", 80, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("172.32.0.1", 443, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("8.8.8.8", 443, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("2001:4860::8888", 443, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("2130706433", 80, p.ERR_EGRESS_AMBIGUOUS_NUMERIC_HOST),
    ("0x7f.1", 80, p.ERR_EGRESS_AMBIGUOUS_NUMERIC_HOST),
    ("0x7f000001", 80, p.ERR_EGRESS_AMBIGUOUS_NUMERIC_HOST),
    ("127.1", 80, p.ERR_EGRESS_AMBIGUOUS_NUMERIC_HOST),
    ("", 443, p.ERR_EGRESS_INVALID_HOST),
    (None, 443, p.ERR_EGRESS_INVALID_HOST),
    ("bad host", 443, p.ERR_EGRESS_INVALID_HOST),
    (" api.example.com", 443, p.ERR_EGRESS_INVALID_HOST),
    ("a..b", 443, p.ERR_EGRESS_INVALID_HOST),
    ("-a.example", 443, p.ERR_EGRESS_INVALID_HOST),
    ("a_b.example", 443, p.ERR_EGRESS_INVALID_HOST),
    ("*.trusted.example", 443, p.ERR_EGRESS_INVALID_HOST),
    ("api.example.com", 0, p.ERR_EGRESS_INVALID_PORT),
    ("api.example.com", 65536, p.ERR_EGRESS_INVALID_PORT),
    ("api.example.com", "443", p.ERR_EGRESS_INVALID_PORT),
    ("api.example.com", True, p.ERR_EGRESS_INVALID_PORT),
    ("api.example.com", -1, p.ERR_EGRESS_INVALID_PORT),
])
def test_egress_denied(epol, host, port, code):
    res = epol.evaluate_egress(host, port)
    assert res.decision is PolicyDecision.DENY, res
    assert res.reason_code == code
    assert res.matched_entry is None


def test_port_bounds_allowed(ws):
    pol = ProtectedPathEgressPolicy(str(ws), ["a.example:1", "a.example:65535"])
    assert pol.evaluate_egress("a.example", 1).decision is PolicyDecision.ALLOW
    assert pol.evaluate_egress("a.example", 65535).decision is PolicyDecision.ALLOW


def test_default_deny_with_empty_allowlist(pol):
    res = pol.evaluate_egress("api.example.com", 443)
    assert res.decision is PolicyDecision.DENY
    assert res.reason_code == p.ERR_EGRESS_NOT_ALLOWLISTED
    assert res.host == "api.example.com"


def test_metadata_ip_allowed_only_when_explicit(ws):
    pol = ProtectedPathEgressPolicy(str(ws), ["169.254.169.254:80"])
    assert pol.evaluate_egress("169.254.169.254", 80).decision is PolicyDecision.ALLOW
    assert pol.evaluate_egress("169.254.169.254", 81).reason_code == p.ERR_EGRESS_PRIVATE_IP_LITERAL
    assert pol.evaluate_egress("169.254.169.253", 80).reason_code == p.ERR_EGRESS_PRIVATE_IP_LITERAL


def test_wildcard_entry_does_not_cover_ip_or_apex(ws):
    pol = ProtectedPathEgressPolicy(str(ws), ["*.example.com:443"])
    assert pol.evaluate_egress("example.com", 443).decision is PolicyDecision.DENY
    assert pol.evaluate_egress("a.example.com", 443).decision is PolicyDecision.ALLOW
    assert pol.evaluate_egress("aexample.com", 443).decision is PolicyDecision.DENY


@pytest.mark.parametrize("entry", [
    "api.example.com", "api.example.com:", "api.example.com:abc", "*:443",
    "a.*.example:443", "*example.com:443", "*.*.example:443", ("a",), ("a", 1, 2),
    ("a.example", 0), ("a.example", "443"), (3, 443), 443, "a.example:70000",
    "bad host:443", "a.example:+443", "a.example: 443",
])
def test_bad_allowlist_entries_rejected(ws, entry):
    with pytest.raises(ValueError):
        ProtectedPathEgressPolicy(str(ws), [entry])


def test_normalize_host():
    assert normalize_host("Example.COM.") == "example.com"
    assert normalize_host("[::FFFF:1.2.3.4]") == ipaddress.ip_address("::ffff:1.2.3.4").compressed
    assert normalize_host("bücher.de") == "xn--bcher-kva.de"
    assert normalize_host("ｅｘａｍｐｌｅ.com") == "example.com"  # NFKC fullwidth
    for bad in ("", "a b", "a\tb", "\napi.x", "a" * 64 + ".com", "x..y", "-x.com", "x-.com"):
        with pytest.raises(ValueError):
            normalize_host(bad)
    with pytest.raises(ValueError):
        normalize_host(None)
    for half_bracket in ("[::1", "::1]", "[a.example"):
        with pytest.raises(ValueError):
            normalize_host(half_bracket)


def test_ip_blocked_helper():
    assert p._ip_blocked(ipaddress.ip_address("::ffff:10.0.0.1"))
    assert not p._ip_blocked(ipaddress.ip_address("::ffff:8.8.8.8"))
    assert not p._ip_blocked(ipaddress.ip_address("1.1.1.1"))
    assert p._ip_blocked(ipaddress.ip_address("fdff:ffff::1"))
    assert not p._ip_blocked(ipaddress.ip_address("fe00::1"))


# ------------------------------------------------------------------ URLs
@pytest.mark.parametrize("url,decision,code", [
    ("https://api.example.com/v1", PolicyDecision.ALLOW, p.EGRESS_ALLOWED),
    ("HTTPS://API.EXAMPLE.COM:443/", PolicyDecision.ALLOW, p.EGRESS_ALLOWED),
    ("wss://api.example.com", PolicyDecision.ALLOW, p.EGRESS_ALLOWED),
    ("http://api.example.com/", PolicyDecision.DENY, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("ws://api.example.com/", PolicyDecision.DENY, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("https://api.example.com:8443/", PolicyDecision.DENY, p.ERR_EGRESS_NOT_ALLOWLISTED),
    ("http://169.254.169.254/latest/meta-data", PolicyDecision.DENY, p.ERR_EGRESS_PRIVATE_IP_LITERAL),
    ("https://api.example.com@evil.net/", PolicyDecision.DENY, p.ERR_EGRESS_URL_USERINFO),
    ("https://user:pw@api.example.com/", PolicyDecision.DENY, p.ERR_EGRESS_URL_USERINFO),
    ("ftp://api.example.com/", PolicyDecision.DENY, p.ERR_EGRESS_UNSUPPORTED_SCHEME),
    ("file:///etc/passwd", PolicyDecision.DENY, p.ERR_EGRESS_UNSUPPORTED_SCHEME),
    ("api.example.com", PolicyDecision.DENY, p.ERR_EGRESS_UNSUPPORTED_SCHEME),
    ("https://", PolicyDecision.DENY, p.ERR_EGRESS_INVALID_HOST),
    ("https://api.example.com:99999/", PolicyDecision.DENY, p.ERR_EGRESS_INVALID_HOST),
    ("https://[::1/", PolicyDecision.DENY, p.ERR_EGRESS_INVALID_HOST),
    (None, PolicyDecision.DENY, p.ERR_EGRESS_INVALID_HOST),
])
def test_evaluate_url(ws, url, decision, code):
    pol = ProtectedPathEgressPolicy(str(ws), ["api.example.com:443"])
    res = pol.evaluate_url(url)
    assert res.decision is decision, res
    assert res.reason_code == code


def test_blocked_networks_extend_existing_guard():
    from src.mcp_egress_guard import MCPEgressSecurityBoundary
    for net in MCPEgressSecurityBoundary.BLOCKED_NETWORKS:
        assert net in p.BLOCKED_NETWORKS
    assert ipaddress.ip_network("fc00::/7") in p.BLOCKED_NETWORKS


@pytest.mark.parametrize("url,port", [
    ("http://api.example.com/", 80), ("ws://api.example.com/", 80),
    ("https://api.example.com/", 443), ("wss://api.example.com/", 443),
])
def test_default_ports_per_scheme(ws, url, port):
    only = ProtectedPathEgressPolicy(str(ws), [f"api.example.com:{port}"])
    res = only.evaluate_url(url)
    assert res.decision is PolicyDecision.ALLOW
    assert res.port == port


def test_result_types_are_immutable(epol, pol):
    import dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        epol.evaluate_egress("api.example.com", 443).decision = PolicyDecision.DENY
    with pytest.raises(dataclasses.FrozenInstanceError):
        pol.evaluate_write("src/app.py").decision = PolicyDecision.DENY


def test_protected_rule_precedence():
    assert p._protected_rule(".git/hooks/mcp.json") == "dir:.git"
    assert p._protected_rule(".github/workflows/.env") == "dir:.github/workflows"
