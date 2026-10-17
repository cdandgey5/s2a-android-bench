# Stage: report (optional polish; the orchestrator generates the draft)

Polish the draft report below into a concise, accurate change report for a reviewer. Keep every
fact; do not add claims that the artifacts do not support. Return it as your final message.

```
# Change report: <title>
## Summary
<3–5 sentences: what was asked, what was done, verdict>
## Acceptance criteria → evidence
| AC | Result | Evidence |
## Assumptions made
- ...
## Residual risks
- ...
## Files changed
<from git diff --stat>
## How to verify
<commands>
## Suggested PR description
<short>
```

## Draft
{{draft_report}}
