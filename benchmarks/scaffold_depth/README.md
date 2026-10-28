# Scaffold-depth benchmark (offline scorer; prototype)

Question: does forcing a plan before code (decomposition) reduce placeholder/scaffold code and
improve verified completion, compared with direct generation and with a stronger model?

## Protocol
- 21 hand-written, self-contained Python tasks in `tasks/*.json`, spanning algorithm, bugfix,
  dates, dedup, feature, idempotency, money, parsing, refactor, state machine, text and validation.
  Each task gives an instruction and a starter source.
- Hidden pytest tests and reference solutions live outside the repo, with sha256 pins in
  `manifest.json`. The scorer halts if any pin does not match.
- Candidate modules are placed at `arm_outputs/<arm>/<task_id>/rep<k>.py` and scored by
  `score_arm.py`. Each candidate runs out of process (`python -I -m pytest`, env={'HOME': tmp},
  temp cwd, timeout). This is process isolation, not a sandbox.
- Placeholders are counted by `src/scaffold_detector.py`, an AST check with allowlists (abstract
  methods, Protocols, overloads, exception subclasses, unchanged TODOs). On a 42-snippet
  hand-written corpus it has no FP and no FN; that corpus was written to the detector's spec. The
  pasted substring matcher on the same corpus: TP 13, FP 12, TN 10, FN 7
  (`tests/test_scaffold_detector.py`).
- Controls: reference solutions pass 21/21; starters fail 21/21; a tampered hidden test halts the
  run (`tests/test_scaffold_depth_scorer.py`).

## Pre-registered decision rule
Adopt forced decomposition only if verified completion improves, scaffolds do not increase, and
regressions and evaluation hacks do not increase. Reject it if scaffolds drop but the pass rate
drops. A build decision needs at least 20 tasks with 3 repetitions each.

## Pilot result (2026-10-28, 1 repetition)
| arm | hidden pass | Wilson 95% (bps) | scaffolds |
|---|---|---|---|
| A flash, direct | 21/21 | [8453, 10000] | 0 |
| B flash, plan + no-placeholder instruction | 21/21 | [8453, 10000] | 0 |
| C pro, direct | 21/21 | [8453, 10000] | 0 |

Ceiling effect: every arm solved every task, with no placeholders. On this task set the benchmark
cannot tell the arms apart, so it gives **no evidence for or against** forced decomposition. The
scaffold gap observed in interactive sessions did not reproduce on small self-contained tasks.
Arm audit: each arm only listed and read the task files and wrote its outputs (checked from the
subagent tool-call logs).

## Limitations / next version
- The tasks are too easy, so they need to be harder: multi-file or repo-level changes,
  underspecified requirements, longer contexts, and a few spec/test-conflict tasks (ImpossibleBench,
  arXiv:2510.20270) where a pass means cheating.
- Agentic setting: allow the model to run visible tests, keep hidden tests held out, and report
  the visible-minus-hidden gap (SpecBench arXiv:2605.21384, EvilGenie arXiv:2511.21654).
- The model tiers used are those available to the orchestrator. Outputs from other models (e.g.
  the "Argon" sessions) can be dropped into an arm directory and scored the same way; the scorer
  makes no model calls.
- Token budgets were not equalised. The hidden tests are not cryptographically hidden from a
  determined agent.
