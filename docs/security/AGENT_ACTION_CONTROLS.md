# Agent Action Controls (prototype)

Status: **prototype / scaffold**. These controls are tested in this repository
under the stated model (unit tests below). `loads_strict` and `McpToolPinGuard`
are wired into all three MCP boundaries (see "Wiring status"). Nothing here
performs network access.

| Control | Module | Tests |
|---|---|---|
| Package-install gate | [`src/package_install_gate.py`](../../src/package_install_gate.py) | [`tests/test_package_install_gate.py`](../../tests/test_package_install_gate.py) |
| Protected-path write policy + egress allowlist | [`src/protected_path_egress_policy.py`](../../src/protected_path_egress_policy.py) | [`tests/test_protected_path_egress_policy.py`](../../tests/test_protected_path_egress_policy.py) |
| MCP tool-definition pinning (rug pull / shadowing) | [`src/mcp_schema_pinning.py`](../../src/mcp_schema_pinning.py) (`ToolDefinitionPinSet`, `detect_shadowing`) | [`tests/test_mcp_schema_pinning.py`](../../tests/test_mcp_schema_pinning.py) |

## Threat basis

Sources are listed as reported. Items marked **UNVERIFIED** were not opened
and re-checked in this session; see `docs/UNVERIFIED_CLAIMS_REGISTER.md`
policy.

| ID | Threat | Source (as reported) | Status |
|---|---|---|---|
| T1 | Package hallucination / "slopsquatting": LLMs recommend non-existent package names that an attacker can register. Reported figure: ~19.7% of recommended packages hallucinated. | Spracklen et al., "We Have a Package for You!", USENIX Security 2025 | **UNVERIFIED** (figure as reported by the research lane; not re-measured here) |
| T2 | Agent writes agent configuration (`.cursor/mcp.json`) leading to command execution ("CurXecute"). | CVE-2025-54135 (Cursor) | **UNVERIFIED** (advisory text not opened in this session) |
| T3 | Path allowlist checked by string prefix only, so a sibling such as `/repo-evil` passes a check for `/repo`. | CVE-2025-54794 (Claude Code) | **UNVERIFIED** (advisory text not opened in this session) |
| T4 | MCP tool "rug pull" (definition changes after approval) and tool shadowing (a second server registers a colliding tool name / description that steers the model). | Invariant Labs, MCP tool-poisoning write-ups | **UNVERIFIED** |
| T5 | SSRF-style egress to cloud metadata / private ranges, typosquat/lookalike hosts. | General class; no specific figure claimed | n/a |

## Control -> threat -> OWASP Agentic mapping

> [!NOTE]
> The OWASP Top 10 for Agentic Applications (ASI, 2026) mapping below is **our
> interpretation**; OWASP has not reviewed it.

| Control | Decision / reason codes | Threats | OWASP ASI (our interpretation) |
|---|---|---|---|
| `PackageInstallGate.evaluate(argv)` - argv only (shell strings rejected), lockfile-derived allowlist, exact pins, URL/VCS/path and index overrides denied, Damerau-Levenshtein <= 1 typosquat check | `ALLOW` / `DENY` / `NOT_APPLICABLE`; `ERR_UNKNOWN_PACKAGE`, `ERR_TYPOSQUAT_SUSPECTED`, `ERR_UNPINNED_VERSION`, `ERR_VERSION_NOT_IN_LOCKFILE`, `ERR_URL_VCS_PATH_INSTALL`, `ERR_INDEX_OVERRIDE`, `ERR_UNSUPPORTED_OPTION`, `ERR_SHELL_STRING_REJECTED`, `ERR_SHELL_METACHARACTER`, `ERR_PARSE_ERROR`, ... | T1 | ASI04 Agentic Supply Chain; ASI05 Unexpected Code Execution; ASI02 Tool Misuse |
| `ProtectedPathEgressPolicy.evaluate_write(path)` - `realpath` + `commonpath` containment (no prefix test), case-insensitive protected set checked on lexical and resolved names | `ALLOW` / `DENY` / `REQUIRES_APPROVAL`; `ERR_PATH_ESCAPES_WORKSPACE`, `PATH_PROTECTED_REQUIRES_APPROVAL`, `ERR_PATH_INVALID`, `ERR_PATH_IS_WORKSPACE_ROOT` | T2, T3 | ASI05 Unexpected Code Execution; ASI03 Identity & Privilege Abuse; ASI10 Rogue Agents (self-modifying config) |
| `ProtectedPathEgressPolicy.evaluate_egress(host, port)` / `evaluate_url(url)` - default deny, exact host after NFKC/IDNA/lowercase, explicit `*.` wildcards only, blocked IP-literal ranges, ambiguous numeric hosts denied, userinfo URLs denied | `EGRESS_ALLOWED`, `ERR_EGRESS_NOT_ALLOWLISTED`, `ERR_EGRESS_PRIVATE_IP_LITERAL`, `ERR_EGRESS_AMBIGUOUS_NUMERIC_HOST`, `ERR_EGRESS_URL_USERINFO`, `ERR_EGRESS_INVALID_HOST`, `ERR_EGRESS_INVALID_PORT`, `ERR_EGRESS_UNSUPPORTED_SCHEME` | T5 | ASI02 Tool Misuse; ASI01 Agent Goal Hijack (exfiltration step) |
| `ToolDefinitionPinSet.pin_server/check_server`, `detect_shadowing` - `sha256(encode_jcs({name, title?, description?, inputSchema, annotations?}))` per tool via `src.jcs_canonicalizer` | `DEFINITION_CHANGED`, `TOOL_ADDED`, `TOOL_REMOVED`, `DUPLICATE_IN_SERVER`, `SHADOWED_ACROSS_SERVERS`, `UNPINNED_SERVER`, `INVALID_DEFINITION` | T4 | ASI04 Agentic Supply Chain; ASI06 Memory & Context Poisoning; ASI01 Agent Goal Hijack |

## Protected write set

Matched case-insensitively on each path component, on both the pre-symlink and
the symlink-resolved relative path:

- directories at any depth: `.cursor/`, `.claude/`, `.agents/`, `.git/`
- adjacent pairs at any depth: `.github/workflows/`, `scripts/hooks/`
- basenames at any depth: `mcp.json`, `.mcp.json`, `.gitlab-ci.yml`,
  `AGENTS.md`, `CLAUDE.md`, `.env*`

Some patterns from the spec are root-anchored (e.g. `.cursor/**`); this policy
matches them at any depth, which can ask for approval more often than strictly
needed (fail-safe direction).

## Blocked IP-literal ranges

`src.mcp_egress_guard.MCPEgressSecurityBoundary.BLOCKED_NETWORKS`
(127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1, fe80::/10) plus
`fc00::/7`, `0.0.0.0/8`, `100.64.0.0/10`, `::/128`. IPv4-mapped IPv6 is
unwrapped before the check. An IP literal is allowed only if that exact
`IP:port` is in the allowlist.

## Known limits

- Egress is evaluated on the requested host string. DNS resolution and
  DNS-rebinding must still be checked at connect time
  (`MCPEgressSecurityBoundary.validate_resolved_ip`).
- The install gate does not cover `npx`, `uvx`, `pipx`, `pip download`,
  `go get`, `gem`, or package-manager config files (`.npmrc`, `pip.conf`);
  writes to those should be added to the protected set or a separate gate.
- Only the *requested* packages are checked. Transitive dependencies (and
  extras such as `requests[socks]`) are resolved by the package manager from
  its index and are not checked by this gate; pair it with hash-checked or
  lockfile-only installs (`pip --require-hashes`, `npm ci`, `cargo --locked`).
- `pip install -r file` is denied rather than parsed.
- `NOT_APPLICABLE` means "not an install command recognised by this gate";
  callers must not treat it as approval of arbitrary commands.
- Lockfiles are read from the workspace top level only; an agent that can
  write a lockfile can widen the allowlist, so lockfile writes should
  themselves be routed through approval (not in the protected set today).
- The path policy checks the path at decision time; a symlink swapped in
  between decision and write (TOCTOU) is not prevented by this module. The
  write sink should open with `O_NOFOLLOW` / `openat` semantics.

## Wiring status (MCP boundaries)

All three MCP boundaries now wire `src.strict_json_ingress.loads_strict` and
`src.mcp_schema_pinning.ToolDefinitionPinSet` (via `McpToolPinGuard`), tested in
[`tests/test_mcp_boundary_hardening_wiring.py`](../../tests/test_mcp_boundary_hardening_wiring.py):

| Boundary | Strict JSON ingress (`loads_strict`) | Tool-definition pinning (`McpToolPinGuard`) | Learn mode default |
|---|---|---|---|
| [`aeib_mcp_proxy.py`](../../aeib_mcp_proxy.py) | Wired at JSON-RPC line ingress (`handle_line` / `_forward_to_upstream`); duplicate keys, `NaN`/`Infinity`, and lone surrogates return `-32700` (`ERR_STRICT_JSON_REJECTED`) | Wired (`pin_set` / `pin_file` / `AEIB_MCP_TOOL_PINS_PATH`). `tools/list` is always gated against pins; `DEFINITION_CHANGED` (rug pull), `TOOL_ADDED`, `TOOL_REMOVED`, `DUPLICATE_IN_SERVER`, `SHADOWED_ACROSS_SERVERS`, and `UNPINNED_SERVER` return `-32096` (`MCP_TOOL_PIN_VIOLATION`) and latch drift | `False` (`learn_pins=False`) |
| [`src/secure_mcp_uds_boundary.py`](../../src/secure_mcp_uds_boundary.py) | Wired in `verify_and_forward` and `_handle_client` before any method routing; rejects malformed/duplicate-key/non-finite JSON with `ERR_STRICT_JSON_REJECTED` | Wired (`pin_set` / `pin_file`, `server_id`, `learn_pins=False`). `tools/list` checks observed tools against pinned digests; once pinning is active or drift is latched, `tools/call` for unpinned or drifted tools is blocked with `ERR_MCP_TOOL_PIN_VIOLATION` | `False` (`learn_pins=False`) |
| [`adapters/mcp/idempotent_mcp_proxy.py`](../../adapters/mcp/idempotent_mcp_proxy.py) | Wired in `handle_raw_json_line` (newline-delimited JSON-RPC ingress) | Wired (`pin_set` / `pin_file`, `server_id`, `learn_pins=False`). Intercepts `tools/list` before non-consequential pass-through and enforces pin checks on `tools/call` when pinning is configured | `False` (`learn_pins=False`) |

> [!NOTE]
> **Backward compatibility on `tools/call` when no `pin_set` is configured:**
> `tools/list` is always fail-closed (`UNPINNED_SERVER` when `pin_set` is empty
> and `learn_pins=False`). Direct `tools/call` requests on a boundary constructed
> without a `pin_set` continue to work unless `pin_set` / `pin_file` is supplied
> or a `tools/list` drift has latched.
