# Does a staged orchestrator help Claude Code change real Android apps?

*Draft. Sections marked [after the run] are written only from the audited held-out run
(`20261022-2104-heldout-final`, then `heldout-optional`); everything else is fixed by the design.*

## 1. Question

Coding agents are usually measured on greenfield puzzles or on Python repositories. Most professional work is
the opposite: a ticket against a large, old codebase with its own build, conventions and tests. This project asks
one narrow question about that setting:

> On real tickets in two open-source Android apps, does **S2A** — an orchestrator that runs Claude Code through
> fixed stages with gates (map, intake, locate, reproduce, spec, plan, implement, verify) — resolve more tasks
> than **Claude Code on its own** with the same model and the same budget?

and two secondary ones: is any gain from the *harness* (gates, fresh sessions, verification) or just from
*telling* the model the workflow (`plain-guided`), and how does it compare with GitHub **Spec Kit**, the best-known
spec-driven tool?

## 2. Design

- **Tasks.** 25 tasks from AntennaPod (Java) and the Wikipedia app (Kotlin): 15 from merged upstream PRs (14 mined,
  1 reverted) and 10 authored; each with hidden fail-to-pass and pass-to-pass JVM tests, validated three times
  offline.
  Split once (seed 20261101) into 10 dev and 15 test tasks before any S2A tuning (`benchmark/README.md`).
- **Arms.** `plain`, `plain-guided`, `speckit`, `s2a`, and the ablations `s2a-nomap`, `s2a-noverify` at 3 trials;
  `plain-gate`, `s2a-norepro`, `speckit-sdd` at 1 trial (exploratory).
- **Same budget.** 45 minutes, $15 est., 200 turns per trial for every arm; nudges ("no human is available,
  proceed") capped at 2 per call and 4 per trial. One-time setups (Spec Kit constitution, S2A map) are built once
  per repo with the pinned model and reported separately.
- **Isolation.** Each trial runs as a low-privilege Windows user in a history-free snapshot, with only the model
  API reachable and Gradle offline. The grader applies the hidden tests to the agent's diff afterwards.
- **Truth and checks.** Verbatim transcripts are the record; `abb audit` recomputes every derived number from
  them and the report is withheld if it fails. `abb repro` re-grades sample trials and re-renders the report.
- **Pre-registration.** `docs/PREREG.md`, frozen at `v1.0-frozen` before the held-out run: primary comparison
  `s2a` vs `plain`, pass@1 over the 15 test tasks × 3 trials, paired bootstrap 95 % CI; exclusion and rerun rules;
  the runner refuses a test-split run unless PREREG is unchanged since the tag.
- **Model.** `claude-opus-5-5` through Claude Code 2.1.302, subscription auth (Max 5x), two trials in parallel on
  one laptop.

## 3. What building it taught (dev set only)

These are engineering findings, not results; all came from the dev split or harness tests.

- **Tuning did not move pass@1.** S2A's dev pass@1 stayed at 0.75 on Sonnet 5.5 across the baseline and two
  changes (the verifier checks the original request, not just its own spec; feature tasks get a "files to create"
  section). Both were kept for what they fixed (verifier agreement with the hidden tests 4/6 → 5/6; locate stops
  on feature tasks), but 10 tasks × 2 trials cannot show effects under ≈ 38 pp (`s2a/CHANGELOG.md`).
- **The harness had real bugs, and the audit trail found them.** Concurrent `icacls` grants lost ACEs and broke
  Gradle in 3 trials (D-056); a trial's clock started before its one-time setup was ready (D-060); a setup retry
  overwrote the failed attempt's record (D-061); the setup-leak lint flagged common words (D-062). Each spoiled
  trial was set aside with `abb run invalidate`, kept, and re-run.
- **Model changes break setups, not just trials.** On Opus the S2A map explored longer than on Sonnet and ran out
  of turns before writing its output (D-059); the confirmation run on the pinned model before the freeze caught it.
- **Cost.** On the dev set with Opus, S2A cost ≈ 7× plain per trial ($3.51 vs $0.51 est.) and took ≈ 3.7× the
  wall time; Spec Kit ≈ 4.4× (`docs/RUNS.md`, `20261022-0355-dev-opus-confirm`).

## 4. Results [after the run]

<!-- Headline table and the pre-registered interval from report/summary.md; pass^3; cost per task and per
resolved task; one-time setup cost; controls (s2a vs plain-guided, plain-gate); ablations; usage-limit
sensitivity; post-cutoff and authored rows; detectable effect (≈ 24 pp) stated next to the interval. -->

## 5. Failure analysis [after the run]

<!-- From labels.json (LLM labels, uncalibrated: D-057) and the transcripts. For each major finding, three
transcript excerpts with run/arm/task/trial and line references. -->

## 6. What S2A v1 should change [after the run]

## 7. Limits

- **Sample size.** 15 test tasks × 3 trials: differences under ≈ 24 pp are unlikely to be detected; the
  post-cutoff check (n = 3) is uninformative by design.
- **Scope.** Two Android repositories, JVM unit and Robolectric tests only; no instrumented or UI tests, so UI
  and Compose work is under-represented. Claude Code is the only agent.
- **Contamination.** Mined tasks may be in the model's training data; post-cutoff and authored rows are reported
  separately. No web access during trials.
- **Labels.** Failure categories come from an LLM labeller that was not calibrated against manual labels (D-057).
- **Author isolation is hygiene, not a boundary.** The same agent session drafted the tasks and built S2A; the
  ordering (tasks and their hash before any tuning, test ids refused while tuning) is all that separates them.
- **Subscription auth.** The run used a subscription in batches across usage windows, as the owner decided at
  S5 (`specs/auth-and-usage.md` §5); usage-limit cuts are re-run and reported, never scored.
