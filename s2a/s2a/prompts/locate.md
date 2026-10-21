# Stage: locate (impact analysis)

Find where the change belongs and what it can affect. Read code; do not change anything.
Return your analysis as your final message in this format:

```
## Candidates (ranked)
1. <path> — <symbol(s)> — <why, with the evidence you read>
2. ...
## Files to create
- <path> — <why the change needs a new file here>   (or "none")
## Call graph
- <symbol> is called by: <paths/symbols>
- <symbol> calls: <paths/symbols>
## Existing tests touching these
- <test path> — <what it covers>
## Blast radius
- Modules affected: ...
- Persisted data / schemas / public APIs / resources touched: ... (or "none")
- Features that share this code: ...
## Reproduction entry points
- <how a unit test could exercise the behaviour: class, method, seams>
```

Rules: the ranked candidates are only paths that exist (you read them); a file the change will need
but that does not exist yet goes under "Files to create", never among the candidates. Prefer the
smallest set of files that fully explains the current behaviour. If the codebase map lists conventions for this area, name the
ones the change must respect.

## Ticket
{{ticket}}

## Codebase map
{{map}}
