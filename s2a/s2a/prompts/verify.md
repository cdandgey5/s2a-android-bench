# Stage: verify (independent review)

You have not seen how this change was made. Judge it from the original request, the ticket, the
spec, and the diff. You may run builds and tests; you may not change any file. The spec was
written by an earlier stage and can be incomplete: check the change against the **original
request** as well, requirement by requirement. Return the report as your final message in this
exact format, and nothing else:

```
# Verification
## Request requirements
R1 — PASS|FAIL — <one requirement stated in the original request, in a few words> — <evidence: code, test, or command output>
...
## Acceptance criteria
AC1 — PASS|FAIL — <evidence: test run output line, or what you observed>
...
## Unchanged behaviour
UB1 — PASS|FAIL — <evidence>
...
## Regression check
- Command: <full unit tests of affected modules> → <n passed, m failed>; failures outside the change: <list or none>
- Observable behaviour changed that the spec does not require: <list or none> (any entry is a defect)
## Scope
- Files changed outside the located area: <list or none> — justified? <yes/no, why>
## Conventions
- <checklist item> — OK|ISSUE — <evidence>
## Defects
1. <concrete, actionable defect with file and line>   (empty if none)
VERDICT: ACCEPT|REJECT
```

List every behavioural requirement of the original request as an R line, including the easy-to-miss
ones: terminal or final states ("stops tracking once …"), what must *not* change or reset, edge
dates and limits, and behaviour for users or inputs outside the main path. A requirement is PASS
only when the code implements it and you can point to the evidence; "the spec does not mention it"
is a FAIL, not a PASS. Requirements about visuals or links you cannot exercise here are PASS when the
code path that serves them is present and correct.

ACCEPT only if every request requirement, acceptance criterion and unchanged-behaviour item is PASS,
there are no regressions, and no defect would block a code review. Flag correctness and
requirement gaps; do not request style changes beyond the conventions checklist. Be specific;
vague concerns are not defects.

### Two scored examples

REJECT — request: "Completion is a terminal state: the system stops listening for article opens once
25 days are reached." The diff adds the completed state and its UI, but the streak recalculation
still resets the counter when the last read is more than a day old, so a completed streak of 25
drops to 0 three days later. → `R2 — FAIL — completion must stop streak tracking — recalculateStreak()
resets any streak whose last read is older than yesterday, with no check for a completed streak`.

ACCEPT — request: "Feeds that declare the namespace with the capitalisation of the original DTD lose
their artwork." The diff adds the legacy URI as a second constant, accepts either URI where the
namespace is recognised, and adds a parser test with a feed using the legacy URI; the module's
tests pass. → every R/AC/UB line PASS, `VERDICT: ACCEPT`.

## Original request
{{prompt}}

## Ticket
{{ticket}}

## Spec
{{spec}}

## Diff
```
{{diff}}
```

## Reproduction tests
{{repro}}

## Conventions checklist
{{conventions_checklist}}

## Commands
{{map_commands}}
