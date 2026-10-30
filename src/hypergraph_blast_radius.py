# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
src/hypergraph_blast_radius.py — Kiro-Style Autonomous PR Governor & Hypergraph AST Blast-Radius Engine

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Core Capabilities:
1. AST Reverse-Dependency Graph & BFS Transitive Blast Radius Calculator (integer bps 0..10000).
2. Kiro Crew Anti-Scope-Creep Gate (bounds over-eager agents expanding blast radius).
3. Deterministic 4-Way Routing:
   - AUTO_MERGE: Leaf changes within blast-radius and lines-changed caps.
   - HALT_SCOPE_CREEP: PR size or files touched exceeds proportionality limits.
   - AUTO_REJECT_INVARIANT: Constraint violations or AST integrity tripwire fired.
   - HUMAN_ESCALATE: High-blast-radius changes requiring architectural intent sign-off.
4. Cumulative epoch line cap (max_epoch_cumulative_lines) halting split-PR smurfing attacks.
5. Protected path boundary checks forbidding untrusted mutation of critical infra/auth modules.

Zero floats, pure integer rational basis points, deterministic verification.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, Union

from src.jcs_canonicalizer import encode_jcs as _encode_jcs


def sha256_jcs_caid(payload: Any) -> str:
    """Computes a deterministic Content-Addressed Identifier (CAID) using RFC 8785 JCS."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = _encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


# ---------------------------------------------------------------------------
# PR Diff & Evaluation Data Structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PRDiffSpec:
    pr_id: str
    intent_caid: str
    changed_files: Tuple[str, ...]
    lines_added: int
    lines_deleted: int
    constraint_violations: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.pr_id:
            raise ValueError("ERR_EMPTY_PR_ID")
        if not self.intent_caid.startswith("sha256:"):
            raise ValueError(f"ERR_INVALID_INTENT_CAID:{self.intent_caid}")
        if self.lines_added < 0 or self.lines_deleted < 0:
            raise ValueError("ERR_NEGATIVE_LINE_COUNTS")


@dataclass(frozen=True)
class BlastRadiusReport:
    changed_files: Tuple[str, ...]
    transitive_dependents: Tuple[str, ...]
    total_repo_modules: int
    blast_radius_bps: int  # 0..10000 integer basis points


@dataclass(frozen=True)
class AutonomousPRVerdict:
    pr_id: str
    action: str  # "AUTO_MERGE" | "HALT_SCOPE_CREEP" | "AUTO_REJECT_INVARIANT" | "HUMAN_ESCALATE"
    reason_code: str
    blast_radius_bps: int
    affected_modules: Tuple[str, ...]
    total_lines_changed: int
    files_touched_count: int
    verdict_caid: str


@dataclass(frozen=True)
class PRScopeProposal:
    """Declared scope and proposed changes for an autonomous agent PR."""
    pr_id: str
    author_agent_id: str
    epoch_id: str
    declared_intent: str
    modified_files: List[str]
    added_lines: int
    deleted_lines: int

    def validate(self) -> None:
        if not self.pr_id:
            raise ValueError("ERR_EMPTY_PR_ID")
        if not self.author_agent_id:
            raise ValueError("ERR_EMPTY_AUTHOR_AGENT_ID")
        if not self.epoch_id:
            raise ValueError("ERR_EMPTY_EPOCH_ID")
        if not self.declared_intent:
            raise ValueError("ERR_EMPTY_DECLARED_INTENT")
        if self.added_lines < 0 or self.deleted_lines < 0:
            raise ValueError("ERR_NEGATIVE_LINE_COUNT")
        if not self.modified_files:
            raise ValueError("ERR_EMPTY_MODIFIED_FILES")


@dataclass(frozen=True)
class ScopeEvaluationReport:
    """Deterministic evaluation outcome emitted by HypergraphBlastRadiusGovernor."""
    pr_id: str
    author_agent_id: str
    epoch_id: str
    verdict: str  # "PASS" | "HALT_SCOPE_VIOLATION" | "HALT_BLAST_RADIUS_EXCEEDED" | "HALT_SMURFING_EXCEEDED" | "HALT_PROTECTED_PATH"
    blast_radius_bps: int  # 0..10000 bps
    total_lines_changed: int
    cumulative_epoch_lines: int
    affected_dependents_count: int
    affected_dependents: List[str]
    reasons: List[str]
    caid: str

    def to_canonical_dict(self) -> Dict[str, object]:
        return {
            "affected_dependents": sorted(self.affected_dependents),
            "affected_dependents_count": self.affected_dependents_count,
            "author_agent_id": self.author_agent_id,
            "blast_radius_bps": self.blast_radius_bps,
            "cumulative_epoch_lines": self.cumulative_epoch_lines,
            "epoch_id": self.epoch_id,
            "pr_id": self.pr_id,
            "reasons": sorted(self.reasons),
            "total_lines_changed": self.total_lines_changed,
            "verdict": self.verdict,
        }


# ---------------------------------------------------------------------------
# Graph & AST Analysis Utilities
# ---------------------------------------------------------------------------

class DependencyGraph:
    """In-memory directed dependency graph built from Python AST analysis."""

    def __init__(self) -> None:
        self.forward_deps: Dict[str, Set[str]] = {}
        self.reverse_deps: Dict[str, Set[str]] = {}
        self.all_modules: Set[str] = set()

    def add_module(self, module_name: str) -> None:
        self.all_modules.add(module_name)
        if module_name not in self.forward_deps:
            self.forward_deps[module_name] = set()
        if module_name not in self.reverse_deps:
            self.reverse_deps[module_name] = set()

    def add_dependency(self, source_mod: str, target_mod: str) -> None:
        self.add_module(source_mod)
        self.add_module(target_mod)
        self.forward_deps[source_mod].add(target_mod)
        self.reverse_deps[target_mod].add(source_mod)

    def compute_reverse_dependents_bfs(
        self,
        target_modules: Set[str],
        max_depth: int = 10,
    ) -> Set[str]:
        """Compute all modules that transitively depend on the target modules up to max_depth."""
        visited: Set[str] = set()
        queue: List[Tuple[str, int]] = []

        for target in target_modules:
            if target in self.reverse_deps:
                for parent in self.reverse_deps[target]:
                    if parent not in target_modules and parent not in visited:
                        visited.add(parent)
                        queue.append((parent, 1))

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            if current in self.reverse_deps:
                for parent in self.reverse_deps[current]:
                    if parent not in target_modules and parent not in visited:
                        visited.add(parent)
                        queue.append((parent, depth + 1))

        return visited


def extract_ast_imports(file_path: Path) -> Set[str]:
    """Extract imported module names from a Python source file using standard AST parsing."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except Exception:
        return set()

    imported: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    return imported


# ---------------------------------------------------------------------------
# Governor Implementation
# ---------------------------------------------------------------------------

class HypergraphBlastRadiusGovernor:
    """
    Computes exact AST transitive reverse-dependency blast radius in integer basis points
    and enforces Kiro Crew Anti-Scope-Creep proportionality bounds.
    """

    DEFAULT_MAX_BLAST_RADIUS_BPS: int = 4500  # claim: config
    DEFAULT_MAX_PR_LINES: int = 300  # claim: config
    DEFAULT_MAX_EPOCH_CUMULATIVE_LINES: int = 1200  # claim: config

    def __init__(
        self,
        repo_sources: Optional[Mapping[str, str]] = None,
        max_auto_merge_radius_bps: int = 3000,
        max_lines_changed: int = 50,
        max_files_touched: int = 3,
        max_blast_radius_bps: int = DEFAULT_MAX_BLAST_RADIUS_BPS,  # claim: config
        max_pr_lines: int = DEFAULT_MAX_PR_LINES,  # claim: config
        max_epoch_cumulative_lines: int = DEFAULT_MAX_EPOCH_CUMULATIVE_LINES,  # claim: config
        protected_patterns: Optional[List[str]] = None,
        repo_root: Optional[Path] = None,
    ) -> None:
        if repo_sources is not None and len(repo_sources) == 0:
            raise ValueError("ERR_EMPTY_REPO_SOURCES")
        if max_auto_merge_radius_bps < 0 or max_auto_merge_radius_bps > 10000:
            raise ValueError(f"ERR_INVALID_RADIUS_BPS:{max_auto_merge_radius_bps}")
        if max_lines_changed <= 0:
            raise ValueError(f"ERR_INVALID_MAX_LINES:{max_lines_changed}")
        if max_files_touched <= 0:
            raise ValueError(f"ERR_INVALID_MAX_FILES:{max_files_touched}")

        self.max_auto_merge_radius_bps = max_auto_merge_radius_bps
        self.max_lines_changed = max_lines_changed
        self.max_files_touched = max_files_touched

        self.repo_root = repo_root or Path.cwd()
        self.max_blast_radius_bps = max_blast_radius_bps  # claim: config
        self.max_pr_lines = max_pr_lines  # claim: config
        self.max_epoch_cumulative_lines = max_epoch_cumulative_lines  # claim: config
        self.protected_patterns = protected_patterns or [
            "compliance/",
            "config/agentgateway",
            "enclave/",
            "auth/",
            "credentials/",
            "hardware_ledger",
        ]

        self.graph = DependencyGraph()
        self._epoch_line_accumulator: Dict[Tuple[str, str], int] = {}

        # If repo_sources is supplied, index reverse dependencies
        self._all_files: FrozenSet[str] = frozenset(repo_sources.keys()) if repo_sources else frozenset()
        self._module_to_file: Dict[str, str] = {}
        self._reverse_deps: Dict[str, Set[str]] = {f: set() for f in self._all_files}

        if repo_sources:
            for path in self._all_files:
                if path.endswith(".py"):
                    mod_dotted = path[:-3].replace("/", ".")
                    self._module_to_file[mod_dotted] = path
                    short_name = mod_dotted.split(".")[-1]
                    if short_name not in self._module_to_file:
                        self._module_to_file[short_name] = path
            self._build_reverse_dependency_graph(repo_sources)

    def _build_reverse_dependency_graph(self, repo_sources: Mapping[str, str]) -> None:
        for p in self._all_files:
            self.graph.add_module(Path(p).stem)

        for file_path, source_code in sorted(repo_sources.items()):
            try:
                tree = ast.parse(source_code, filename=file_path)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dep_file = self._resolve_import(alias.name)
                        if dep_file is not None and dep_file != file_path:
                            self._reverse_deps[dep_file].add(file_path)
                            self.graph.add_dependency(Path(file_path).stem, Path(dep_file).stem)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    dep_file = self._resolve_import(node.module)
                    if dep_file is not None and dep_file != file_path:
                        self._reverse_deps[dep_file].add(file_path)
                        self.graph.add_dependency(Path(file_path).stem, Path(dep_file).stem)
                    for alias in node.names:
                        combined = f"{node.module}.{alias.name}"
                        sub_file = self._resolve_import(combined)
                        if sub_file is not None and sub_file != file_path:
                            self._reverse_deps[sub_file].add(file_path)
                            self.graph.add_dependency(Path(file_path).stem, Path(sub_file).stem)

    def _resolve_import(self, mod_name: str) -> Optional[str]:
        if mod_name in self._module_to_file:
            return self._module_to_file[mod_name]
        parts = mod_name.split(".")
        for i in range(len(parts), 0, -1):
            prefix = ".".join(parts[:i])
            if prefix in self._module_to_file:
                return self._module_to_file[prefix]
        return None

    def calculate_blast_radius(self, changed_files: Tuple[str, ...]) -> BlastRadiusReport:
        """Runs BFS over reverse dependencies to find all transitively impacted downstream modules."""
        visited: Set[str] = set()
        queue: deque[str] = deque()

        for f in changed_files:
            if f in self._reverse_deps:
                queue.append(f)

        while queue:
            curr = queue.popleft()
            for dependent in sorted(self._reverse_deps.get(curr, ())):
                if dependent not in visited and dependent not in changed_files:
                    visited.add(dependent)
                    queue.append(dependent)

        total_modules = len(self._all_files)
        radius_bps = (len(visited) * 10000) // total_modules if total_modules > 0 else 0

        return BlastRadiusReport(
            changed_files=tuple(sorted(changed_files)),
            transitive_dependents=tuple(sorted(visited)),
            total_repo_modules=total_modules,
            blast_radius_bps=radius_bps,
        )

    def build_graph_from_directory(self, target_dir: Path) -> int:
        """Scan directory and index reverse dependencies. Returns total modules found."""
        if not target_dir.is_dir():
            return 0
        sources: Dict[str, str] = {}
        for pyf in target_dir.rglob("*.py"):
            try:
                sources[str(pyf.relative_to(target_dir))] = pyf.read_text(encoding="utf-8")
            except Exception:
                continue
        self._all_files = frozenset(sources.keys())
        self._module_to_file = {}
        self._reverse_deps = {f: set() for f in self._all_files}
        for path in self._all_files:
            mod_dotted = path[:-3].replace("/", ".")
            self._module_to_file[mod_dotted] = path
            short_name = mod_dotted.split(".")[-1]
            if short_name not in self._module_to_file:
                self._module_to_file[short_name] = path
        self._build_reverse_dependency_graph(sources)
        return len(self._all_files)

    # Helper methods for synthetic module graph registration
    def register_manual_module(self, module_name: str) -> None:
        self.graph.add_module(module_name)

    def register_manual_dependency(self, source_mod: str, target_mod: str) -> None:
        self.graph.add_dependency(source_mod, target_mod)

    def reset_epoch_accumulator(self) -> None:
        self._epoch_line_accumulator.clear()

    # Polymorphic evaluate_pr supporting PRDiffSpec and PRScopeProposal
    def evaluate_pr(
        self, pr_or_proposal: Union[PRDiffSpec, PRScopeProposal]
    ) -> Union[AutonomousPRVerdict, ScopeEvaluationReport]:
        if isinstance(pr_or_proposal, PRDiffSpec):
            return self._evaluate_pr_diff_spec(pr_or_proposal)
        elif isinstance(pr_or_proposal, PRScopeProposal):
            return self._evaluate_pr_scope_proposal(pr_or_proposal)
        else:
            raise TypeError(f"ERR_UNSUPPORTED_PR_SPEC_TYPE: {type(pr_or_proposal)}")

    def _evaluate_pr_diff_spec(self, pr: PRDiffSpec) -> AutonomousPRVerdict:
        total_lines = pr.lines_added + pr.lines_deleted
        files_count = len(pr.changed_files)
        blast = self.calculate_blast_radius(pr.changed_files)

        # 1. Invariant / constraint check
        if pr.constraint_violations:
            verdict_payload = {
                "action": "AUTO_REJECT_INVARIANT",
                "affected": sorted(blast.transitive_dependents),
                "blast_bps": blast.blast_radius_bps,
                "files_count": files_count,
                "pr_id": pr.pr_id,
                "reason": f"ERR_INVARIANT_TRIPWIRE:{','.join(pr.constraint_violations)}",
                "total_lines": total_lines,
            }
            return AutonomousPRVerdict(
                pr_id=pr.pr_id,
                action="AUTO_REJECT_INVARIANT",
                reason_code=f"ERR_INVARIANT_TRIPWIRE:{','.join(pr.constraint_violations)}",
                blast_radius_bps=blast.blast_radius_bps,
                affected_modules=blast.transitive_dependents,
                total_lines_changed=total_lines,
                files_touched_count=files_count,
                verdict_caid=sha256_jcs_caid(verdict_payload),
            )

        # 2. Scope-Creep check (lines changed or files touched)
        if total_lines > self.max_lines_changed or files_count > self.max_files_touched:
            verdict_payload = {
                "action": "HALT_SCOPE_CREEP",
                "affected": sorted(blast.transitive_dependents),
                "blast_bps": blast.blast_radius_bps,
                "files_count": files_count,
                "pr_id": pr.pr_id,
                "reason": f"HALT_OVER_EAGER_AGENT_SCOPE_EXCEEDED:lines={total_lines}>{self.max_lines_changed},files={files_count}>{self.max_files_touched}",
                "total_lines": total_lines,
            }
            return AutonomousPRVerdict(
                pr_id=pr.pr_id,
                action="HALT_SCOPE_CREEP",
                reason_code=f"HALT_OVER_EAGER_AGENT_SCOPE_EXCEEDED:lines={total_lines}>{self.max_lines_changed},files={files_count}>{self.max_files_touched}",
                blast_radius_bps=blast.blast_radius_bps,
                affected_modules=blast.transitive_dependents,
                total_lines_changed=total_lines,
                files_touched_count=files_count,
                verdict_caid=sha256_jcs_caid(verdict_payload),
            )

        # 3. Blast radius check
        if blast.blast_radius_bps > self.max_auto_merge_radius_bps:
            verdict_payload = {
                "action": "HUMAN_ESCALATE",
                "affected": sorted(blast.transitive_dependents),
                "blast_bps": blast.blast_radius_bps,
                "files_count": files_count,
                "pr_id": pr.pr_id,
                "reason": f"HALT_HIGH_BLAST_RADIUS_ARCHITECTURAL_APPROVAL_REQUIRED:blast={blast.blast_radius_bps}>{self.max_auto_merge_radius_bps}",
                "total_lines": total_lines,
            }
            return AutonomousPRVerdict(
                pr_id=pr.pr_id,
                action="HUMAN_ESCALATE",
                reason_code=f"HALT_HIGH_BLAST_RADIUS_ARCHITECTURAL_APPROVAL_REQUIRED:blast={blast.blast_radius_bps}>{self.max_auto_merge_radius_bps}",
                blast_radius_bps=blast.blast_radius_bps,
                affected_modules=blast.transitive_dependents,
                total_lines_changed=total_lines,
                files_touched_count=files_count,
                verdict_caid=sha256_jcs_caid(verdict_payload),
            )

        # 4. Nominal Auto-Merge
        verdict_payload = {
            "action": "AUTO_MERGE",
            "affected": sorted(blast.transitive_dependents),
            "blast_bps": blast.blast_radius_bps,
            "files_count": files_count,
            "pr_id": pr.pr_id,
            "reason": "OK_LEAF_CHANGE_WITHIN_PROPORTIONAL_LIMITS",
            "total_lines": total_lines,
        }
        return AutonomousPRVerdict(
            pr_id=pr.pr_id,
            action="AUTO_MERGE",
            reason_code="OK_LEAF_CHANGE_WITHIN_PROPORTIONAL_LIMITS",
            blast_radius_bps=blast.blast_radius_bps,
            affected_modules=blast.transitive_dependents,
            total_lines_changed=total_lines,
            files_touched_count=files_count,
            verdict_caid=sha256_jcs_caid(verdict_payload),
        )

    def _evaluate_pr_scope_proposal(self, proposal: PRScopeProposal) -> ScopeEvaluationReport:
        proposal.validate()

        reasons: List[str] = []
        total_lines = proposal.added_lines + proposal.deleted_lines

        # 1. Check Protected Path Boundary
        for path in proposal.modified_files:
            for protected in self.protected_patterns:
                if protected in path:
                    reasons.append(f"PROTECTED_PATH_VIOLATION: {path} matches protected pattern '{protected}'")

        if reasons:
            return self._build_scope_report(
                proposal=proposal,
                verdict="HALT_PROTECTED_PATH",
                blast_radius_bps=10000,  # claim: config
                total_lines_changed=total_lines,
                cumulative_epoch_lines=self._get_current_epoch_lines(proposal.epoch_id, proposal.author_agent_id),
                affected_dependents_count=0,
                affected_dependents=[],
                reasons=reasons,
            )

        # 2. Check Cumulative Epoch Line Cap (Anti-Smurfing)
        current_cumulative = self._get_current_epoch_lines(proposal.epoch_id, proposal.author_agent_id)
        projected_cumulative = current_cumulative + total_lines
        if projected_cumulative > self.max_epoch_cumulative_lines:
            reasons.append(
                f"SMURFING_CAP_EXCEEDED: Projected epoch lines {projected_cumulative} exceeds limit {self.max_epoch_cumulative_lines}"
            )
            return self._build_scope_report(
                proposal=proposal,
                verdict="HALT_SMURFING_EXCEEDED",
                blast_radius_bps=0,  # claim: config
                total_lines_changed=total_lines,
                cumulative_epoch_lines=current_cumulative,
                affected_dependents_count=0,
                affected_dependents=[],
                reasons=reasons,
            )

        # 3. Check Single-PR Line Cap
        if total_lines > self.max_pr_lines:
            reasons.append(
                f"LINE_CAP_EXCEEDED: PR total lines {total_lines} exceeds max allowed {self.max_pr_lines}"
            )
            return self._build_scope_report(
                proposal=proposal,
                verdict="HALT_SCOPE_VIOLATION",
                blast_radius_bps=0,  # claim: config
                total_lines_changed=total_lines,
                cumulative_epoch_lines=current_cumulative,
                affected_dependents_count=0,
                affected_dependents=[],
                reasons=reasons,
            )

        # 4. Compute AST Reverse-Dependency Blast-Radius
        modified_mod_names: Set[str] = set()
        for f in proposal.modified_files:
            p = Path(f)
            mod_name = p.stem
            modified_mod_names.add(mod_name)
            self.graph.add_module(mod_name)

        affected_dependents = self.graph.compute_reverse_dependents_bfs(modified_mod_names)
        affected_count = len(affected_dependents)
        total_modules_count = len(self.graph.all_modules)

        if total_modules_count <= 1:
            blast_radius_bps = 0  # claim: config
        else:
            blast_radius_bps = (affected_count * 10000) // total_modules_count

        if blast_radius_bps > self.max_blast_radius_bps:
            reasons.append(
                f"BLAST_RADIUS_EXCEEDED: Blast radius {blast_radius_bps} bps exceeds max permitted {self.max_blast_radius_bps} bps"
            )
            return self._build_scope_report(
                proposal=proposal,
                verdict="HALT_BLAST_RADIUS_EXCEEDED",
                blast_radius_bps=blast_radius_bps,
                total_lines_changed=total_lines,
                cumulative_epoch_lines=current_cumulative,
                affected_dependents_count=affected_count,
                affected_dependents=sorted(list(affected_dependents)),
                reasons=reasons,
            )

        # Commit epoch lines on PASS
        self._epoch_line_accumulator[(proposal.epoch_id, proposal.author_agent_id)] = projected_cumulative
        reasons.append("ALL_CONSTRAINTS_SATISFIED")

        return self._build_scope_report(
            proposal=proposal,
            verdict="PASS",
            blast_radius_bps=blast_radius_bps,
            total_lines_changed=total_lines,
            cumulative_epoch_lines=projected_cumulative,
            affected_dependents_count=affected_count,
            affected_dependents=sorted(list(affected_dependents)),
            reasons=reasons,
        )

    def _get_current_epoch_lines(self, epoch_id: str, author_agent_id: str) -> int:
        return self._epoch_line_accumulator.get((epoch_id, author_agent_id), 0)

    def _build_scope_report(
        self,
        proposal: PRScopeProposal,
        verdict: str,
        blast_radius_bps: int,
        total_lines_changed: int,
        cumulative_epoch_lines: int,
        affected_dependents_count: int,
        affected_dependents: List[str],
        reasons: List[str],
    ) -> ScopeEvaluationReport:
        canonical_payload = {
            "affected_dependents": sorted(affected_dependents),
            "affected_dependents_count": affected_dependents_count,
            "author_agent_id": proposal.author_agent_id,
            "blast_radius_bps": blast_radius_bps,
            "cumulative_epoch_lines": cumulative_epoch_lines,
            "epoch_id": proposal.epoch_id,
            "pr_id": proposal.pr_id,
            "reasons": sorted(reasons),
            "total_lines_changed": total_lines_changed,
            "verdict": verdict,
        }
        encoded = _encode_jcs(canonical_payload)
        caid = hashlib.sha256(encoded).hexdigest()

        return ScopeEvaluationReport(
            pr_id=proposal.pr_id,
            author_agent_id=proposal.author_agent_id,
            epoch_id=proposal.epoch_id,
            verdict=verdict,
            blast_radius_bps=blast_radius_bps,
            total_lines_changed=total_lines_changed,
            cumulative_epoch_lines=cumulative_epoch_lines,
            affected_dependents_count=affected_dependents_count,
            affected_dependents=affected_dependents,
            reasons=reasons,
            caid=caid,
        )
