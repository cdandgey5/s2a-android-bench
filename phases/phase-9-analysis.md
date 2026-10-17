# Phase 9 — Analysis: statistics, failure labelling, charts

**Goal.** `abb report <run_id>` regenerates every number, table and chart of the write-up from
`results/` alone, per `specs/metrics-and-stats.md` and `specs/failure-taxonomy.md`.

**Prerequisites.** Phase 8 gate and at least one multi-arm dev-set run with 2–3 trials.

**Effort.** ~1–2 weeks part-time (hand-labelling is the slow part).

## Deliverables

```
benchmark/abb/harness/report.py           # full version
benchmark/abb/harness/stats.py            # pass@1, pass^k, paired bootstrap, detectable delta
benchmark/abb/harness/labeller.py         # headless Claude Code (`-p --output-format json --json-schema --tools "" --max-turns 1`); calibration mode
benchmark/abb/harness/charts.py           # matplotlib; consistent palette; CI whiskers
benchmark/tests/test_stats.py             # known-answer tests (toy data) for every statistic
benchmark/tests/test_report.py            # builds a report from fixture results
CLI: abb report <run_id> [--arms …] [--breakdowns …]      abb labels init|show|set|llm|agreement <run_id> …
```

## Steps

1. **Rows.** `report.load_rows(run_id) -> DataFrame` from every `metrics.json` (+ `setup/`
   rows flagged `is_setup=True`). Validate completeness; list missing trials at the top of the
   summary.
2. **Statistics** (`stats.py`): per spec. Known-answer tests: e.g. 4 tasks × 3 trials toy data
   where pass@1 and pass^3 are computable by hand; bootstrap with fixed seed returns a stable
   CI; `detectable_delta(40, 3, 0.4)` ≈ a number you sanity-check by simulation.
3. **Tables**: `headline.csv` (the pre-registered primary comparison first, then the rest under
   "exploratory"), `by_*.csv` for every breakdown, `pairs.csv`, `failures.csv`, `setup.csv`
   (one-time cost per setup kind × repo, and amortised per task), `controls.csv` (s2a vs
   plain-guided vs plain-gate), `budget.csv` (turns, gate runs, gate seconds, per-stage turns,
   retries, null-cost share per arm), `interface.csv` (`test_compile_failed` per arm × category).
4. **Charts** (`charts.py`): the four charts from the spec; PNG + SVG; readable in grayscale
   (hatching for ablations); titles carry run id and model. Deterministic output:
   `savefig(..., metadata={"Date": None})` (matplotlib otherwise embeds the current date in
   SVG/PNG), fixed figure sizes and DPI, no random jitter without a seed.
5. **`summary.md`**: manifest facts → headline table → pairwise deltas with CIs → breakdowns →
   failure breakdown → secondary metrics → caveats (sample size, detectable delta, dropped
   tasks, interventions definition). Everything generated; no hand edits; the only date in it
   is `manifest.created_at` (never wall-clock), so two runs of `abb report` are byte-identical.
   `abb report <run_id> --out <dir>` writes to an arbitrary directory (default
   `<results root>/<run_id>/report/`).
6. **Labelling tooling**: `abb labels init` (skeleton per unresolved trial; ids are opaque so the
   arm is not visible), `show` (blind bundle: ticket, diff, grade summary; `--with-transcript`
   for the secondary-flag pass only), `set <label>` (writes `labels.json` with `source:
   manual`), `llm` (labeller on unlabelled or on `--calibrate` set), `agreement` (manual vs llm
   confusion matrix + agreement %, per arm).
7. **Labeller** (`labeller.py`): through the headless driver, `claude.exe -p --output-format json
   --json-schema <taxonomy enum schema> --tools "" --max-turns 1 --model <pinned>` with the blind
   bundle on stdin; read `structured_output` (subtype `error_max_structured_output_retries` →
   retry once, then `unlabelled`). No SDK, no API key. Prompt includes the taxonomy table verbatim and the bundle. Cost of labelling is
   reported in `docs/RUNS.md` (it is analysis cost, not arm cost).
8. **Hand-label 20–30 failures** from the latest dev-set run, stratified across arms. Refine
   the taxonomy if needed (edit `specs/failure-taxonomy.md`, bump `taxonomy_version` in
   `labels.json`). Run `abb labels llm --calibrate` until agreement ≥ 80 %.
9. **Convention score** (optional): calibrate on 30 manual scores; include only if Spearman
   ≥ 0.6.
10. Commit `phase 9: analysis`.

## Acceptance gate

```
uv run pytest -q tests/test_stats.py tests/test_report.py
uv run abb report <dev_run_id>                     # report/summary.md + tables/ + charts/ regenerated from scratch
uv run abb labels agreement <dev_run_id>           # >= 80 % primary-label agreement on the manual set
uv run abb report <dev_run_id> --out $env:TEMP\r1; uv run abb report <dev_run_id> --out $env:TEMP\r2; uv run abb report-diff $env:TEMP\r1 $env:TEMP\r2   # deterministic: "identical"
```

Passes when the report is fully generated and deterministic, statistics have known-answer
tests, and the LLM labeller is calibrated against ≥ 20 manual labels.

## Pitfalls

- Don't compute CIs on trials as if independent; the unit is the task (paired bootstrap over
  tasks, trials averaged within task).
- Separate "setup" rows from trial rows before any mean.
- Keep the labeller blind to the arm name (strip it from the bundle) to avoid bias.
