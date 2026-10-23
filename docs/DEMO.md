# Demo: one task, three arms (3 minutes)

The same ticket, the same model (`claude-opus-5-5`), the same budget. What differs is everything around the
change. Material: the Opus dev-set confirmation run `20261022-0355-dev-opus-confirm`, task `antennapod-0000`
(a dev task, so it can be shown in full; held-out tasks are shown only in the write-up).

## 0:00 — the ticket (20 s)

`benchmark/tasks/antennapod-0000/problem.md`: a podcast feed writes episode durations with a decimal comma
(`00:52:17,5`, `3137,5`), and AntennaPod shows no length for its episodes until one is played; `00:52:17.5` works.
Hidden test: `DurationParserTest.testSecondsWithDecimalCommaInMillis`.

## 0:20 — plain: one call (40 s)

Claude Code alone, one headless call. **7 turns, 2.4 min, est. $0.29 — resolved.**

```diff
-        String[] parts = durationStr.trim().split(":");
+        String[] parts = durationStr.trim().replace(",", ".").split(":");
```

Show `results/20261022-0355-dev-opus-confirm/plain/antennapod-0000/t1/transcript/`: three tool calls — read the
parser and its test, edit with one `sed` and add tests, run `:parser:feed:test` — then stop. No notes, no plan.

## 1:00 — Spec Kit: the bug path (40 s)

`/speckit-bug-assess` → `/speckit-bug-fix` → `/speckit-bug-test`. **17 turns, 7.0 min, est. $1.03 — resolved**,
with a one-line fix in `toMillis` (`seconds = seconds.replace(',', '.');`) and new tests. Show the three notes it
leaves under `.specify/bugs/duration-decimal-comma/`: `assessment.md` (symptom, reproduction, suspected code paths,
root-cause hypothesis, risks), `fix.md` (summary and changes), `test.md`. The value is the paper trail a reviewer
can read.

## 1:40 — S2A: staged, gated, verified (60 s)

`intake → locate → reproduce → spec → plan → implement → verify → report`, each stage a fresh session with its
own turn cap, each followed by a gate. **44 turns, 10.2 min, est. $1.76 — resolved**, the same `toMillis`
one-liner as Spec Kit plus three regression tests it wrote before the fix.

Walk the artifacts in `s2a/antennapod-0000/t1/artifacts/`:

- `locate.md` — ranked candidates, `DurationParser.toMillis` first, with the smallest fix and why existing
  formats cannot change.
- `gates/001-repro_parser_feed/` — the reproduce gate: its three new tests **FAIL** before the fix (evidence that
  it found the bug, not just a plausible edit).
- `spec.md`, `plan.md` — acceptance criteria and one task, T1.
- `gates/005-task-T1-_parser_feed/`, `gates/006-repro_parser_feed/` — after T1 the build and the same tests
  pass (`BUILD SUCCESSFUL`).
- `verify.md` — an independent session checks every acceptance criterion and the original request against the
  diff and the gate logs: ACCEPT.
- `report.md` — what changed, the evidence per criterion, assumptions, residual risks.

## 2:40 — the point (20 s)

On an easy bug all three arms are right, and the extra stages cost time and tokens (S2A ≈ 6× plain here). The
benchmark asks whether that structure pays off on the harder held-out tasks: see the README's results table and
`docs/WRITEUP.md`. One easy dev task is an illustration, not evidence.
