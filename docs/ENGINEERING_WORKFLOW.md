# SovereignNexus Engineering Workflow & Security Standards

## 1. Context & State Management (Antigravity Protocol)
- **Artifact-First:** Complex outputs must be generated as discrete artifacts (files, scripts, configs), not inline chat dumps.
- **State Tracking:** Rely on explicit file paths, line numbers, and `GATES.md` checklists to maintain context across session limits.
- **Targeted Edits:** Use precise `grep`/`ripgrep` logic and targeted file replacements rather than full-file rewrites.

## 2. GitHub Supply Chain Security
- **Commit Signing:** All merges to `main` require GPG or SSH-signed commits.
- **SLSA Provenance:** All release artifacts (Docker images, WASM binaries, Python wheels) must be built using the `slsa-framework/slsa-github-generator` with OIDC token permissions.
- **Automated Scanning:** Dependabot and CodeQL are mandatory and must pass on all PRs.

## 3. Network Stability & Routing (Developer Local)
- **SSH Preferred:** Always use `git@github.com:` over HTTPS for repository interactions.
- **Proxy Routing:** If local network throttling occurs, route GitHub traffic via local proxy (e.g., `ProxyCommand nc -X 5 -x 127.0.0.1:7890 %h %p` in `~/.ssh/config`).
- **Mirrors:** Use `ghproxy.com` for cloning large repositories or downloading release assets if direct connections time out.

*Note: AI assistants are strictly prohibited from modifying host machine global git/ssh configurations without explicit, step-by-step user authorization.*
