# Stage: implement — task {{task_id}} of {{task_count}}

Implement exactly this task, then stop. Other tasks are done in later sessions.

## Task
{{task}}

## Acceptance criteria this task covers
{{criteria}}

## Progress so far (from previous sessions)
{{progress}}

## Current change set
```
{{diff_stat}}
```

Procedure:
0. Read the progress notes above and `git log --oneline -10`; run the task's command once
   before changing anything to confirm the baseline builds and the named existing tests pass.
1. Read the files the task names and the tests it names. Confirm the approach still fits.
2. Make the change following the surrounding code's conventions.
3. Add or extend the tests the task names. If a reproduction test exists for this ticket and
   this task is the one that fixes the behaviour, it must pass now.
4. Run the task's command. Fix until it compiles and the named tests pass. Do not weaken or
   skip any test.
5. Finish with a final message:

```
## Done
- <what changed, file by file>
## Tests
- <command> → <result>
## Learned
- <anything the next task's session must know (seams, gotchas, decisions)>
## Assumptions
- <any assumption you had to make>
```

{{previous_attempt_errors}}

## Codebase map (commands and test infrastructure)
{{map_commands}}
