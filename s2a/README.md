# s2a — Specs → App orchestrator

Give it one prompt in an existing repository; it drives a coding agent through intake → map →
locate → reproduce/characterize → spec → plan → implement (one small committed task at a time)
→ independent verify → bounded fix loop → report, with machine-checked gates between stages,
budgets, and resumable state under `.s2a/`.

```
s2a run "Playback speed resets after restart; it should persist." --profile android   # runs to completion, no questions
s2a run "..." --interactive          # pauses after spec and after plan for approval; continue with `s2a resume`
s2a status <run_id>        s2a resume <run_id>        s2a show <run_id> report
```

Design: `../specs/s2a-orchestrator.md`. Principles it implements: `../specs/brownfield-principles.md`.
Build plan: `../phases/phase-6-s2a-orchestrator.md`. Seeds in `s2a/s2a/`: `pipeline.yaml`,
`profiles/android.yaml`, `prompts/*.md` (they ship inside the package). The Python modules are
built in Phase 6.

Requires Claude Code (pinned); it uses whatever auth that `claude.exe` has — your normal login
when you run it yourself, or a `CLAUDE_CODE_OAUTH_TOKEN` placed in its environment by whoever
starts it headlessly. No API key needed. Exit codes: 0 verified change; 2
finished but the independent verifier still rejects (see the report); 3 a gate could not be
passed; 4 budget/time exhausted; 5 paused for your input (`--interactive`); 6 the model service
refused the request (usage limit or authentication) — state is saved, `s2a resume` continues.
