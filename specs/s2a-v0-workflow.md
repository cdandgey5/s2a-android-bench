# Superseded

The S2A v0 "five prompts in an adapter" design was replaced on 2026-10-16 by a standalone
orchestrator (D-015). Read:

- `specs/s2a-orchestrator.md` — the framework: CLI, modes, stages, gates, budgets, state, profiles,
  and how the benchmark's Arm C wraps it.
- `specs/brownfield-principles.md` — the researched principles each stage implements.
- `phases/phase-6-s2a-orchestrator.md` — how to build it.

Everything that was in this file (map as one-time setup, spec/plan/implement, fresh-session
verifier with tree reset, ablations `nomap`/`noverify`, prompt-hash audit trail, dev-only
tuning) is carried over into the orchestrator spec.
