# Provenance notes (not shown to agents)

- Source: authored (dev5 refactor task) by the building agent (claude-opus-5-5), 2026-10-18;
  awaits human review at stop point S2.
- Upstream PR/issue: none. Realistic maintainer refactor: `FeedItemPermutors.getPermutor`
  builds each order's comparator inline; the ticket asks to expose them as
  `getComparator(SortOrder)` (named in the ticket: new surface, D-020) with `getPermutor`
  delegating, behaviour unchanged.
- Hidden tests (`test.patch`, Robolectric, added to the existing `FeedItemPermutorsTest`):
  comparators agree with permutors for every comparator-based order (COMPLETION_DATE_NEW_OLD
  is only checked for non-null: the shared test list has no play history), DURATION_LONG_SHORT
  order, `null` for RANDOM / SMART_SHUFFLE_*. At base the test source set does not compile
  (`getComparator` does not exist) -> V1 `test_compile_failed` as expected for `new_surface`.
  The 15 existing tests of the class are P2P and pin the unchanged behaviour.
- LICENSE-NOTE: patches derive from AntennaPod (GPL-3.0).
- S2 review: approved by the owner on 2026-10-18 (unchanged).
