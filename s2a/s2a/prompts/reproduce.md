# Stage: reproduce / characterize

Before anything is changed, pin the behaviour in tests, using the module's existing test
framework and conventions (see the map).

- **bug**: write unit tests that fail now and would pass once the bug is fixed — **one test per
  distinct expected behaviour** in the ticket's "done when" list (a single test tends to cover
  one manifestation and leads to partial fixes). They must encode the expected behaviour from
  the ticket, not the implementation. Run them and confirm each fails for the right reason (an
  assertion, not a compile error or a missing fixture).
- **refactor**: write characterization tests that pass now and pin the current observable
  behaviour of the code about to change (inputs → outputs, including edge cases you find by
  reading). Run them and confirm they pass.
- **feature**: write acceptance test skeletons for the "done when" items that compile; mark
  them with the framework's disabled annotation only if they cannot pass before the feature
  exists.

Put the tests in the module's normal unit-test source set, following its naming. Do not touch
production code in this stage. The orchestrator commits the test files you list below (do not
commit yourself). Finish with a final message:

```
## Tests written
- <path> — <test names> — <bug: FAILS as expected | refactor: PASSES | feature: COMPILES>
## Command used
<exact command>
## Notes
<fixtures or seams you needed; anything that prevented a direct reproduction>
```

## Ticket
{{ticket}}

## Locate analysis
{{locate}}

## Codebase map (commands and test infrastructure)
{{map_commands}}
