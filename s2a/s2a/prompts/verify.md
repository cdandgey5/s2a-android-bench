# Stage: verify (independent review)

You have not seen how this change was made. Judge it from the ticket, the spec, and the diff.
You may run builds and tests; you may not change any file. Return the report as your final
message in this exact format, and nothing else:

```
# Verification
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

ACCEPT only if every acceptance criterion and every unchanged-behaviour item is PASS, there are
no regressions, and no defect would block a code review. Flag correctness and requirement gaps;
do not request style changes beyond the conventions checklist. Be specific; vague concerns are
not defects.

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
