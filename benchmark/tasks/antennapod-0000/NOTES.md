# Provenance notes (not shown to agents)

- Source: authored (Phase 0 seed task) by the building agent (claude-opus-5-5), 2026-10-17;
  awaits human review at stop point S2 with the rest of dev5.
- Upstream PR/issue: none. The change is realistic (European locales write decimal commas) but
  nobody made it upstream as of the base commit.
- Where the bug is: `DurationParser.toMillis(String seconds)` in `:parser:feed` parses the seconds
  part with `Float.parseFloat` only when it contains `.`, otherwise `Long.parseLong`; both throw
  `NumberFormatException` on `,`, which `Itunes` logs and swallows, so the item gets no duration.
- Test files and hidden-test safety: `test.patch` adds one method to the existing
  `DurationParserTest` and calls only `DurationParser.inMillis(String)`, which exists at base
  (interface rule, D-020). Values are exact in binary floating point (`.5`, `.25`).
- Non-test helpers the tests need: none.
- Manual fail->pass check (Phase 0, experiment checkout, JDK 21, offline): base + test.patch ->
  1 of 6 tests fails (`testSecondsWithDecimalCommaInMillis`); base + gold + test -> 6/6 pass.
  Formal 3x validation is Phase 2 (`abb tasks validate`).
- Validation history: see `.validation/` (git-ignored) and the `validation:` block in task.yaml.
