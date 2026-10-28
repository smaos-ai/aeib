# HyperSU SQLite FTS5 & Provenance-Grounded Hyperedge Retrieval Benchmark Report

## 1. Scope & Architecture Evaluated

This report documents the empirical benchmark and falsification evaluation of the **Provenance-Grounded SQLite FTS5 & Variable-Cardinality Hyperedge Retrieval Layer** implemented in:
- [`src/hypersu_store.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/hypersu_store.py)
- [`src/hypersu_fts.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/hypersu_fts.py)
- [`tests/test_hypersu_fts.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_hypersu_fts.py)
- [`tests/test_hypersu_provenance.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_hypersu_provenance.py)
- [`benchmarks/bench_hypersu_retrieval.py`](file:///Users/andriileukhin/Documents/SovereignNexus/benchmarks/bench_hypersu_retrieval.py)
- Raw JSON output: [`reports/hypersu-benchmark.json`](file:///Users/andriileukhin/Documents/SovereignNexus/reports/hypersu-benchmark.json)

### Evaluated Storage & Retrieval Properties
1. **Dedicated `facts` Table with Verifiable Source Spans:** Every fact row stores `file_path`, `start_char`, `end_char`, `content_sha256`, and `extractor_version`, enforcing `len(text) == end_char - start_char` at insertion time.
2. **Explicitly Synchronized `fact_fts` FTS5 Virtual Table:** Uses `fts5(fact_id UNINDEXED, label, text, tokenize = 'porter unicode61')` explicitly synchronized within the same SQLite transaction on `add_fact`, `add_facts_bulk`, and `delete_fact`.
3. **Variable-Cardinality $n$-ary Hyperedges:** Relational tables `hyperedges`, `hyperedge_members`, and `hyperedge_evidence` attach $2 \dots n$ members (`FACT`, `EPISODE`, or `TOPIC`) and their supporting file spans without fixed arity constraints.
4. **Sanitized FTS5 Query Compilation:** `sanitize_fts5_query()` extracts alphanumeric/underscore tokens containing at least one alphanumeric character and quotes each token (`"token"`), preventing FTS5 syntax errors on boolean operators, unbalanced quotes, column filters, or SQL wildcards.

---

## 2. Complexity Model vs. Measured Scaling

Let $N$ be the number of stored facts, $\bar{L}$ the average fact character length, $Q$ the sanitized query token set, $\text{df}(t)$ the document frequency of token $t$, and $k$ the result limit (`LIMIT 10`):

- **Baseline `LIKE '%q%'` Full Scan:**
  $$\text{Time}_{\text{LIKE}} = \mathcal{O}(N \cdot \bar{L})$$
- **Indexed SQLite FTS5 `MATCH` with Top-$k$ CTE:**
  $$\text{Time}_{\text{FTS5}} = \mathcal{O}\!\left(\sum_{t \in Q} \text{df}(t) + k \log k\right)$$

### Overall Latency & Accuracy Across Corpus Sizes (`200` Queries per Size)

Command executed:
```bash
python3 benchmarks/bench_hypersu_retrieval.py --sizes 100 1000 10000 100000 --queries 200 --output reports/hypersu-benchmark.json
```

| Corpus Size ($N$) | Ingestion Time (s) | Index Size (MB) | FTS5 `p50` (ms) | FTS5 `p95` (ms) | FTS5 `p99` (ms) | `LIKE` `p50` (ms) | `LIKE` `p95` (ms) | `LIKE` `p99` (ms) | `p95` Speedup (`LIKE / FTS5`) | Recall@10 | Precision@10 | Provenance Validity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `100` | `0.0099` | `0.1523` | `0.0589` | `0.1352` | `0.2473` | `0.0474` | `0.0674` | `0.1478` | `0.50x` | `1.00` | `1.00` | `1.00` |
| `1,000` | `0.0131` | `0.8516` | `0.0592` | `0.2178` | `0.6096` | `0.3077` | `0.4249` | `0.6659` | `1.95x` | `1.00` | `1.00` | `1.00` |
| `10,000` | `0.1025` | `7.8789` | `0.1249` | `0.2807` | `5.3345` | `3.7876` | `4.7763` | `5.0838` | `17.02x` | `1.00` | `1.00` | `1.00` |
| `100,000` | `0.6983` | `78.4297` | `0.2217` | `0.3656` | `51.3697` | `38.4144` | `44.2313` | `62.7011` | `120.98x` | `1.00` | `1.00` | `1.00` |

### Per-Query-Category Latency Breakdown at $N = 100,000$ Facts

| Query Category | Queries | FTS5 `p50` (ms) | FTS5 `p95` (ms) | Observation |
|---|---:|---:|---:|---|
| `single_term` | `34` | `0.2445` | `0.3640` | Selective technical identifier (`F_FULLFSYNC`, `flock`, `reconcile_out_of_band`, `caid`, `ed25519`) where $\text{df}(t) \ll N$. |
| `multi_term` | `34` | `0.2911` | `0.3656` | Multi-token BM25 scoring over selective posting lists. |
| `phrase` | `33` | `0.2060` | `0.3111` | Exact positional phrase match in FTS5 inverted index. |
| `wildcard_or_special_characters` | `33` | `0.2471` | `0.3569` | Punctuation stripped to safe quoted tokens; pure wildcards (`%`, `_`, `%%__%%`) short-circuit in `< 0.005 ms`. |
| `empty_query` | `33` | `0.0019` | `0.0030` | Rejected before SQLite execution (`[]`). |
| `adversarial_fts_syntax` | `33` | `0.1277` | `56.1084` | Zero `OperationalError` crashes. The `56.1 ms` `p95` occurs on `"'; DROP TABLE facts; --"` because Porter stemming maps `"facts"` $\to$ `"fact"`, which appears in all $100,000$ synthetic noise rows ($\text{df}(\text{"fact"}) = 100,000$), empirically demonstrating the $\mathcal{O}(\sum \text{df}(t) + k \log k)$ bound. |

---

## 3. Falsification Matrix Results

All 25 unit and falsification tests in `tests/test_hypersu_fts.py` and `tests/test_hypersu_provenance.py` executed and passed (`25 passed in 0.22s`):

| Falsification Vector | Test Function | Observed Result |
|---|---|---|
| Mutate source file bytes on disk after ingestion | `test_provenance_valid_and_detects_mutated_or_deleted_source_files` | `verify_fact_provenance` returns `valid=False`, `status_code="SOURCE_DIGEST_MISMATCH"`; `coarse_to_fine_retrieve(..., verify_provenance=True)` excludes the invalidated fact. |
| Delete source file on disk after ingestion | `test_provenance_valid_and_detects_mutated_or_deleted_source_files` | `verify_fact_provenance` returns `valid=False`, `status_code="SOURCE_FILE_MISSING"`; retrieval with `verify_provenance=True` returns `[]`. |
| Invalid `[start_char, end_char]` span bounds at insertion | `test_invalid_span_bounds_rejected_at_insertion` | `add_fact` raises `ValueError` immediately before SQLite write. |
| 18 adversarial FTS5 syntax, quote, wildcard, null-byte, and SQL injection strings | `test_adversarial_fts5_syntax_and_wildcards_never_crash` | `0` `sqlite3.OperationalError` exceptions across `or`, `and`, and `phrase` modes; `like_scan_retrieve("%")` and `like_scan_retrieve("_")` return `[]`. |
| `SIGKILL` (`kill -9`) mid-ingestion transaction | `test_sigkill_mid_ingestion_preserves_fts5_sync_integrity` | Uncommitted `torn-1` row is rolled back on reopen; `check_fts_sync_integrity()` returns `True` (`25` committed rows in both `facts` and `fact_fts`). |
| Explicit FTS5 synchronization on insert / update / delete | `test_fts5_explicit_sync_on_insert_update_and_delete` | Updating a fact's text removes the stale token from `fact_fts` and indexes the replacement token; deleting the fact removes it from both tables (`check_fts_sync_integrity() == True`). |
| Variable-cardinality $n$-ary hyperedge attachment (`4` members across `FACT` and `TOPIC`) | `test_variable_cardinality_n_ary_hyperedge_attachment` | `JOINTLY_SUPPORTS` hyperedge attaches 3 facts and 1 topic with 3 verifiable source spans (`member_count == 4`). |
| Separation of authority with `EO1` (`PreDispatchIntentInterlock`) | `test_eo1_read_only_explanation_separation_of_authority` | After `EO1` latches an intent into `EFFECT_INDETERMINATE`, `explain_eo1_block` returns the prior intent record, 2 provenance-verified `src/eo1_write_before_execute.py` policy spans, and their supporting hyperedge while leaving `interlock.is_caid_latched(caid) == True`. |
