# Stage: plan

Produce an ordered implementation plan as your final message: first the Markdown, then a
fenced JSON block the orchestrator will parse.

Rules:
- Tasks are small (one commit each, roughly ≤ 200 changed lines, independently buildable and
  testable) and ordered so the build and tests stay green after every task. A feature that
  needs several new classes or functions is split so each task adds at most two new units.
- If the change is hard to make safely in the current structure, put a **preparatory
  refactoring** task first (introduce a seam, extract a method/class) with characterization
  tests, then the behaviour change as a separate task — refactoring commits keep behaviour
  identical; behaviour changes get their own commit.
- Reuse the architecture, dependencies and test conventions the map documents; a task that
  introduces a new library, pattern or mechanism must say why no existing one fits.
- Feature flags only if the codebase already has a flag mechanism and the change is risky;
  never invent one.
- For each task choose the least invasive approach that matches how the codebase already does
  things: `sprout` (new method/class called from one place), `wrap` (wrap existing behaviour),
  or `modify` (change in place).
- Every acceptance criterion is covered by at least one task; every task names the tests that
  prove it and the exact command to run them (from the map).
- List files to change; mark new files as `(new)`.

```
# Plan: <title>
## Tasks
### T1 <title>  [approach: sprout|wrap|modify]  covers: AC1, AC3
- Files: path (modify) · path (new)
- Change: <what, precisely>
- Tests: <add/extend> <class.method>
- Command: <exact>
### T2 ...
## Rollback
<how to revert safely>
```
```json
{"tasks": [{"id": "T1", "title": "...", "approach": "sprout", "covers": ["AC1"], "files": ["..."],
            "module": ":playback", "task": "testDebugUnitTest", "tests": ["com.example.FooTest.bar"],
            "fixes_repro": false}]}
```

`module` and `task` must come from the codebase map (the orchestrator builds the compile and
test commands from them; it never runs a command string you write). For a **bug**, exactly one
task has `"fixes_repro": true`: the task after which the reproduction tests must pass
(preparatory tasks before it may leave them failing).

## Spec
{{spec}}

## Locate analysis
{{locate}}

## Codebase map (commands and conventions)
{{map}}
