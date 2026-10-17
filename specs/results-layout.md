# Spec: Results layout

Root: `$ABB_RESULTS_DIR` (default `ABB_HOME\results`, resolved in `abb/paths.py`). Everywhere this
plan writes `benchmark/results/` it means that root. Never under OneDrive. **The results root is
access-denied to the sandbox user**; the harness user copies files in and out (`Workspace.put/get`).
Phase 1's invariants test, run as the sandbox user, proves the deny.

```
<results root>/<run_id>/
  manifest.json                       # what this run is (below)
  proxy.log                           # every CONNECT the egress proxy allowed or denied
  events.jsonl                        # scheduler log: start/end/skip/retry/resume per trial
  audit.json                          # Phase 4+: `abb audit` recomputation from transcripts (pass/fail per trial)
  probes/<ts>-<arm>-<task>-t<k>-<n>.jsonl   # probe calls that justified a usage_limited / harness_error / abort decision (never wiped)
  probes/<ts>-scheduler-<n>.jsonl     # pause-loop probes; `abb audit` recounts manifest.usage_limited_pauses from this directory
  usage_limited/<arm>/<task_id>/t<k>-a<n>/   # D-028: cut attempts, kept (run.json, transcript/, prompts/); never graded; input to the usage-limit sensitivity check; `abb audit` scans them too
  setup/<setup_kind>/<repo>/          # one-time per-repo setup, reported separately
    run.json  transcript/  prompts/  artifacts/        # setup_kind = speckit-constitution | s2a-map
  <arm>/<task_id>/t<k>/               # k = 1..trials
    run.json                          # RunResult (serialized) + limits used
    transcript/<call_name>.jsonl      # raw stream-json from each headless call, verbatim
    transcript/<call_name>.nudge<j>.jsonl   # nudge continuations
    prompts/<call_name>.md            # exact prompt text sent (for audit)
    diff.patch                        # scoped agent diff (input to grading)
    diff.full.patch                   # unscoped, for forensics
    artifacts/                        # arm artifacts (spec.md, plan.md, map.md, verify.md, state.json …)
    grade.json                        # GradeResult
    junit/                            # TEST-*.xml copied from the grading workspace
    gradle.log                        # grading build output
    metrics.json                      # flattened row used by report.py (below)
    labels.json                       # Phase 9: failure labels (manual and/or llm)
  report/                             # Phase 9 output
    summary.md  tables/*.csv  charts/*.{png,svg}  bootstrap.json
```

## `manifest.json`

```json
{
  "run_id": "20261203-0900-heldout-final",
  "created_at": "2026-12-03T09:00:00Z",
  "label": "heldout-final",
  "prereg_sha256": "...",                     # docs/PREREG.md at freeze time
  "arms": ["plain", "plain-guided", "speckit", "s2a", "s2a-nomap", "s2a-noverify"],
  "task_set": "test",                         # dev | test | all | dev5 | explicit list
  "task_ids": ["antennapod-0001", "..."],
  "task_set_sha256": "...",                   # proves which task contents ran
  "trials": 3,
  "limits": {"timeout_minutes": 45, "max_turns_total": 200, "max_usd": 15.0,
             "max_interventions": 2, "max_interventions_per_trial": 4, "model": "claude-opus-5-5"},
  "agent_version": "2.1.x",
  "speckit_version": "0.x.y",
  "s2a_git_sha": "def456",                    # commit of s2a/ installed in the s2a layer (Phase 6)
  "platform": "windows",
  "env_fingerprints": {"antennapod": "sha256:...", "wikipedia": "sha256:..."},
  "toolchain_lock_sha256": "...",
  "s2a_install": {"sha": "def456", "path": "ABB_HOME\\tools\\bin\\s2a.exe"},
  "interrupt": "ctrl_break",                 # the signal both drivers used for harness-initiated stops (Phase 0 decision)
  "sandbox_mode": "user",                     # user | none (none is refused for split: test)
  "auth_mode": "subscription",                # subscription | api_key
  "plan": "pro",                              # `subscriptionType` from `claude auth status`, recorded by `abb auth check` (not typed by hand)
  "usage_limited_pauses": {"plain": 2, "s2a": 3},
  "strip_agent_instructions": false,
  "allow_env_drift": false,
  "harness_git_sha": "abc123",
  "split_file_sha256": "...",                 # proves the frozen split was used
  "resumes": [{"at": "2026-12-04T02:10:00Z", "reason": "host reboot"}],
  "aborted_reason": null,                     # budget | sigint | usage_limit | auth | model | null
  "host": {"os": "windows", "release": "11 26200", "cpus": 32, "mem_gb": 32}
}
```

## `metrics.json` (one flat row per trial; the report's unit of analysis)

| field | type | source |
|---|---|---|
| run_id, arm, task_id, trial | str/int | runner |
| repo, category, source, tags.*, split, post_cutoff | from task.yaml | runner |
| resolved, build_ok, reason (`null`, `patch_apply_failed`, `test_compile_failed`, `grade_timeout`, …), interface_table (bool), regressions_n, flaky_p2p_n | grade.json | grader |
| agent_touched_tests, build_config_changed, build_config_reverted, test_config_suspect | grade.json.flags | grader |
| diff_files, diff_insertions, diff_deletions, scope_creep_files | grade.json | grader |
| exit_reason, duration_ms, cost_usd (nullable; est. API-equivalent USD), cost_usd_imputed, num_turns, tool_calls, tool_errors, interventions, asked_question, rate_limit_retries, other_retries, model_drift | run.json | arm |
| gate_gradle_runs, gate_seconds | run.json | arm (S2A gates, plain-gate hook) |
| input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cache_hit_rate | run.json (summed over calls) | arm |
| calls_n, calls (json list of {name, cost_usd, num_turns}) | run.json | arm |
| retried (bool), retry_reason | events.jsonl | runner |
| model, agent_version, env_fingerprint, workspace_base, platform | run.json / manifest | runner |
| audit_ok | audit.json | `abb audit` |
| failure_label, failure_label_source (manual/llm), label_confidence | labels.json | Phase 9 |
| convention_score | labels.json | Phase 9 (optional) |

`cache_hit_rate = cache_read_tokens / (input_tokens + cache_read_tokens + cache_write_tokens)`.

## Invariants

- A trial directory is complete iff `run.json`, `diff.patch` and `grade.json` all exist. The
  runner's resume logic uses exactly this rule.
- Files are written atomically (write to `*.tmp`, then rename).
- Nothing under the results root is ever edited by hand except `labels.json` (manual labelling).
- The results root lives outside the repo and is never committed. Published runs are copied by
  Phase 10 to `benchmark/published/<run_id>/{manifest.json, audit.json, report/, labels/}` (plus
  a tarball of the full trial directories attached to the release), and that folder **is**
  committed.
