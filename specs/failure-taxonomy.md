# Spec: Failure taxonomy and labelling (Phase 9)

Every unresolved trial gets exactly one primary label (and optional secondary labels).

## Labels (v1 — refine after hand-labelling the first 20–30)

| code | label | Signal |
|---|---|---|
| `MISREAD` | Misunderstood the ticket | implemented something else; spec/plan artifacts show the wrong goal |
| `WRONG_PLACE` | Changed the wrong code | edits in modules/classes unrelated to the gold modules; F2P unchanged |
| `INCOMPLETE` | Incomplete fix | some F2P pass, others fail; or right place, missing case |
| `COMPILE` | Left a compile error | `build_ok == false`, diff non-empty |
| `REGRESSION` | Broke other behaviour | F2P pass but `regressions_n > 0` |
| `ENV_STUCK` | Stuck on Gradle/build/tooling | transcript dominated by build errors, dependency issues, sdk problems; little code change |
| `OUT_OF_TURNS` | Ran out of turns/time/budget | `exit_reason in {max_turns, timeout, budget}` with F2P failing |
| `GAMED_TESTS` | Edited or disabled tests / test config | `agent_touched_tests` with assertions weakened, or `test_config_suspect` |
| `OVERBUILT` | Over-engineered / scope creep broke it | large diff, many files outside gold modules, failing |
| `NO_ATTEMPT` | Stopped early without a diff | empty diff after nudges; asked questions |
| `HARNESS` | Our bug | `exit_reason == harness_error`, or grading failed to apply a valid patch |
| `INTERFACE` | Correct fix with a different shape than the hidden tests expect (`reason == test_compile_failed`, non-empty diff in the F2P module, and the labeller judges the behaviour correct) | task-quality signal; reported separately from agent failures |

Secondary flags (multi-select): `asked_question`, `ignored_repo_conventions`, `wrote_tests`,
`touched_build_files`.

## Process

1. **Manual pass first, blind.** `abb labels init <run_id>` creates `labels.json` skeletons for all
   unresolved trials. The human labels 20–30 of them (stratified across arms) using
   `abb labels show <run_id> <id>` which prints **only** the ticket, the diff and the grade
   summary — no arm name, no artifacts, no transcript (those identify the arm). Record `source:
   manual`. A second, non-blind pass (`--with-transcript`) sets the secondary flags only.
2. **Refine the taxonomy** if labels don't fit; update this file.
3. **LLM labeller** (`abb/harness/labeller.py`, Anthropic Python SDK, model `claude-opus-5-5`,
   structured output with the label enum). Input = the same blind bundle as step 1, output =
   `{primary, secondary[], confidence, rationale}`. Run on the manual set first: require
   ≥ 80 % agreement on primary label, else fix the prompt and retry. Then label the rest with
   `source: llm`. Report agreement per arm and note that 80 % on 20–30 items has a ±15 pp CI.
4. Report: stacked bars per arm; a table of label × arm; 3 example excerpts per label in the
   write-up.

## Convention score (optional secondary metric)

Same labeller module, prompt asks for a 1–5 score on "follows this repo's conventions
(naming, package layout, patterns used by neighbouring code), with evidence", given the diff and
3 nearby files. Calibrate on 30 manual scores (Spearman ≥ 0.6) before reporting.
