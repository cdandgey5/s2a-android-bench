# Task changes after the split (credibility log)

Every edit to a task after the split was frozen (`tasks/split.yaml`, 2026-10-18) is recorded here: what,
why, the evidence, and what was re-run. Rule (phases/phase-7-scale-tasks.md): a task is not "improved" after
an arm fails on it unless it is a genuine task bug.

## 2026-10-21 — wikipedia-0007 (split: dev): one hidden test asked for something the ticket does not

- **Change:** `test.patch` no longer contains `WikiSiteLanguageCodeTest.minNanLanguageHasTheLegacyLanguageName`
  (it asserted `AppLanguageLookUpTable.getLocalizedName("nan") == "Bân-lâm-gú"`). The three tests that encode
  the ticket stay: `nan` uses the `zh-min-nan.wikipedia.org` subdomain, `nan` normalises to `zh-min-nan`, other
  codes keep their subdomains.
- **Why:** the ticket is the 414 error / wrong subdomain for zh-min-nan; it never asks for the language's
  display name to change. In `20261020-2049-dev-baseline-1` all 20 trials (5 arms) failed only this test, so a
  fix that does what the ticket says could not pass. A genuine task bug, found on a dev task.
- **Re-done:** `abb tasks validate wikipedia-0007 --runs 3` (3/3 V0/V1/V2 OK, 2026-10-21); `abb tasks hash`
  (TASKSET 2eeddcff… -> 80b55a02…; `split.yaml: taskset_history` keeps the old hash); the 10 trials of
  `20261020-2049-dev-baseline-1` on this task re-graded with `scripts/regrade.py` (old grades kept as
  `grade.before-*.json`; `regraded` events in the run's `events.jsonl`).
- **Not changed:** wikipedia-0006 also failed in all 20 trials, but its ticket states both behaviours its
  failing tests check ("completion is a terminal state"; users who never joined see "Challenge concluded: No
  streak"): hard, not broken.
