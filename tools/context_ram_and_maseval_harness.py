"""
Track 3: Context-as-RAM (`HMem` Hawkes-Process Ranking + Scoped Forgetting),
Anthropic `Dynamic Workflows` (`ultracode`) Zero-Token Programmatic Orchestrator,
and `MASEval` / Tsinghua `SRHarness` System-Level Evaluation Harness.
"""
import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ============================================================================
# 1. CONTEXT WINDOW AS RAM: HAWKES-PROCESS RANKING (`HMem`) + SCOPED FORGET
# ============================================================================
@dataclass
class MemoryChunk:
    chunk_id: str
    kind: str  # "PINNED_CONTRACT" | "UNRESOLVED_EFFECT" | "VERIFIED_FACT" | "SCRATCHPAD"
    token_count: int
    base_utility: float
    access_turns: List[int] = field(default_factory=list)
    content: str = ""

    def hawkes_intensity(
        self, current_turn: int, alpha: float = 0.6, beta: float = 0.35
    ) -> float:
        """
        HMem Hawkes self-exciting temporal relevance:
        lambda(t) = base_utility + sum_{t_i <= t} alpha * exp(-beta * (t - t_i))
        """
        excitation = sum(
            alpha * math.exp(-beta * max(0, current_turn - t_i))
            for t_i in self.access_turns
            if t_i <= current_turn
        )
        return round(self.base_utility + excitation, 6)


class HawkesContextRamManager:
    """
    Treats the LLM context window as strict working RAM (`max_ram_tokens = 1500`):
    - Never evicts `PINNED_CONTRACT` or `UNRESOLVED_EFFECT` chunks.
    - Promotes `VERIFIED_FACT` chunks to episodic disk index when evicted from RAM.
    - Discards stale `SCRATCHPAD` chunks during ranking or `scoped_forget()`.
    """

    def __init__(self, max_ram_tokens: int = 1500) -> None:
        self.max_ram_tokens = max_ram_tokens
        self.working_ram: Dict[str, MemoryChunk] = {}
        self.episodic_store: Dict[str, MemoryChunk] = {}

    def upsert_chunk(self, chunk: MemoryChunk, current_turn: int) -> None:
        chunk.access_turns.append(current_turn)
        self.working_ram[chunk.chunk_id] = chunk
        self._enforce_ram_budget(current_turn)

    def _enforce_ram_budget(self, current_turn: int) -> None:
        total_tokens = sum(c.token_count for c in self.working_ram.values())
        if total_tokens <= self.max_ram_tokens:
            return

        # Separate non-evictable boundary state from evictable working memory
        pinned = [
            c
            for c in self.working_ram.values()
            if c.kind in ("PINNED_CONTRACT", "UNRESOLVED_EFFECT")
        ]
        evictable = [
            c
            for c in self.working_ram.values()
            if c.kind not in ("PINNED_CONTRACT", "UNRESOLVED_EFFECT")
        ]
        # Rank evictable chunks by Hawkes intensity descending (keep highest utility)
        evictable.sort(
            key=lambda c: (c.hawkes_intensity(current_turn), c.chunk_id), reverse=True
        )

        new_ram: Dict[str, MemoryChunk] = {c.chunk_id: c for c in pinned}
        used_tokens = sum(c.token_count for c in pinned)

        for cand in evictable:
            if used_tokens + cand.token_count <= self.max_ram_tokens:
                new_ram[cand.chunk_id] = cand
                used_tokens += cand.token_count
            else:
                # Promote verified facts to episodic storage; drop raw scratchpads
                if cand.kind == "VERIFIED_FACT":
                    self.episodic_store[cand.chunk_id] = cand

        self.working_ram = new_ram

    def scoped_forget_scratchpads(self, current_turn: int) -> Dict[str, int]:
        """
        Scoped Forget (`arXiv:2610.20563` adapted for governed boundaries):
        Purges `SCRATCHPAD` drafts while retaining 100% of `PINNED_CONTRACT`,
        `UNRESOLVED_EFFECT`, and `VERIFIED_FACT` items.
        """
        before_count = len(self.working_ram)
        to_delete = [
            cid for cid, c in self.working_ram.items() if c.kind == "SCRATCHPAD"
        ]
        for cid in to_delete:
            del self.working_ram[cid]
        return {
            "discarded_scratchpads": len(to_delete),
            "retained_ram_chunks": len(self.working_ram),
            "episodic_facts_count": len(self.episodic_store),
            "ram_tokens_used": sum(c.token_count for c in self.working_ram.values()),
        }


# ============================================================================
# 2. PROGRAMMATIC DYNAMIC WORKFLOWS (`ultracode` ZERO-TOKEN ORCHESTRATOR)
# ============================================================================
@dataclass
class WorkflowTokenBudget:
    total: int
    _spent: int = 0

    def spent(self) -> int:
        return self._spent

    def remaining(self) -> int:
        return max(0, self.total - self._spent)

    def charge(self, tokens: int) -> None:
        if self._spent + tokens > self.total:
            raise RuntimeError("HALT_WORKFLOW_TOKEN_BUDGET_EXHAUSTED")
        self._spent += tokens


class DynamicWorkflowRuntime:
    """
    Models Anthropic Dynamic Workflows (`ultracode`):
    - The orchestrator script runs deterministically in host code (0 orchestrator tokens).
    - Provides `agent()`, `parallel()`, and `pipeline()` primitives with explicit
      `budget.remaining()` enforcement and `SRHarness`/`MASEval` trace recording.
    """

    def __init__(self, total_token_budget: int = 10000) -> None:
        self.budget = WorkflowTokenBudget(total=total_token_budget)
        self.records_jsonl: List[Dict[str, Any]] = []
        self.tool_calls_jsonl: List[Dict[str, Any]] = []

    def agent(
        self,
        role: str,
        task_input: Dict[str, Any],
        worker_fn: Callable[[Dict[str, Any]], Tuple[Dict[str, Any], int]],
    ) -> Dict[str, Any]:
        if self.budget.remaining() <= 0:
            raise RuntimeError("HALT_WORKFLOW_TOKEN_BUDGET_EXHAUSTED")
        output, tokens_used = worker_fn(task_input)
        self.budget.charge(tokens_used)
        self.records_jsonl.append(
            {
                "primitive": "agent",
                "role": role,
                "tokens_used": tokens_used,
                "budget_remaining": self.budget.remaining(),
                "output_keys": sorted(output.keys()),
            }
        )
        return output

    def parallel(
        self,
        tasks: List[Tuple[str, Dict[str, Any], Callable[[Dict[str, Any]], Tuple[Dict[str, Any], int]]]],
    ) -> List[Dict[str, Any]]:
        """Barrier synchronization across independent subagents."""
        results: List[Dict[str, Any]] = []
        for role, inp, fn in tasks:
            results.append(self.agent(role, inp, fn))
        return results

    def pipeline(
        self,
        items: List[Dict[str, Any]],
        stages: List[Tuple[str, Callable[[Dict[str, Any]], Tuple[Dict[str, Any], int]]]],
    ) -> List[Dict[str, Any]]:
        """Streams each independent item through ordered verification stages."""
        out_items: List[Dict[str, Any]] = []
        for item in items:
            curr = dict(item)
            for stage_name, stage_fn in stages:
                curr = self.agent(stage_name, curr, stage_fn)
            out_items.append(curr)
        return out_items


def test_context_ram_hawkes_and_dynamic_workflows() -> None:
    ram = HawkesContextRamManager(max_ram_tokens=1500)

    # Insert pinned contract (400 tokens) and unresolved effect (200 tokens)
    ram.upsert_chunk(
        MemoryChunk("c-contract", "PINNED_CONTRACT", 400, 10.0, content="Act.v1 schema"),
        current_turn=1,
    )
    ram.upsert_chunk(
        MemoryChunk(
            "c-indet",
            "UNRESOLVED_EFFECT",
            200,
            10.0,
            content="op-504 EFFECT_INDETERMINATE",
        ),
        current_turn=1,
    )
    # Insert verified fact (500 tokens) and two large scratchpads (350 tokens each)
    ram.upsert_chunk(
        MemoryChunk("c-fact-1", "VERIFIED_FACT", 500, 2.0, content="AST symbol offset"),
        current_turn=2,
    )
    ram.upsert_chunk(
        MemoryChunk("c-scratch-1", "SCRATCHPAD", 350, 0.2, content="failed attempt 1"),
        current_turn=2,
    )
    # Adding second scratchpad pushes total to 1,800 > 1,500 -> lowest-Hawkes chunk evicted!
    ram.upsert_chunk(
        MemoryChunk("c-scratch-2", "SCRATCHPAD", 350, 0.1, content="failed attempt 2"),
        current_turn=3,
    )

    assert sum(c.token_count for c in ram.working_ram.values()) <= 1500
    assert "c-contract" in ram.working_ram
    assert "c-indet" in ram.working_ram
    assert "c-fact-1" in ram.working_ram

    # Execute Scoped Forget: purges remaining scratchpads while keeping pinned & facts
    forget_stats = ram.scoped_forget_scratchpads(current_turn=4)
    assert forget_stats["discarded_scratchpads"] == 1
    assert "c-indet" in ram.working_ram

    # Verify Dynamic Workflows (`parallel` + `pipeline` + `budget.remaining()`)
    wf = DynamicWorkflowRuntime(total_token_budget=2000)
    sec_res, perf_res = wf.parallel(
        [
            ("haiku-security", {"file": "wal.rs"}, lambda x: ({"sec_ok": True}, 180)),
            ("haiku-perf", {"file": "wal.rs"}, lambda x: ({"perf_ok": True}, 160)),
        ]
    )
    assert sec_res["sec_ok"] is True and perf_res["perf_ok"] is True
    assert wf.budget.spent() == 340
    assert wf.budget.remaining() == 1660


if __name__ == "__main__":
    test_context_ram_hawkes_and_dynamic_workflows()
    print(
        "TRACK 3 CONTEXT-AS-RAM (HAWKES HMEM + SCOPED FORGET) & DYNAMIC WORKFLOWS PASSED."
    )
