# Provenance notes (not shown to agents)

- Source: authored for this benchmark (drafted by the building agent with claude-opus-5-5 at base 0c7ee9b4682512217e01d829fb0b6d068d268724).

# wikipedia-0009 — reviewer notes

**Category:** refactor (no behaviour change). **Base:** upstream `0c7ee9b4682512217e01d829fb0b6d068d268724`.

## What the task checks and why it is realistic

`WatchlistViewModel` turns the watchlist filter preferences into the `list=watchlist` API parameters
(`wlallrev`, `wlshow`, `wltype`) and computes the filter-badge count. It does this in private
functions (plus a public `filtersCount()`) that read `Prefs.watchlistIncludedTypeCodes`,
`Prefs.watchlistExcludedWikiCodes` and `WikipediaApp.instance.languageState` directly, and the
ViewModel's `init { fetchWatchlist() }` goes to the network, so none of it is unit-testable today.
The ticket is the kind of tech-debt task Wikipedia Android maintainers file: move the logic into a pure
`object WatchlistFilterHelper` that takes the filter state as plain inputs and let the ViewModel
delegate, without changing a single request parameter or the badge number. The hidden tests pin
today's exact outputs (computed by reading the base code, not the survey) for the default filters and
for non-default combinations reachable from the filter screen: `wlallrev` (`null` vs `"1"`), the exact
`wlshow` string and its group order, the `wltype` string in `TYPE_OF_CHANGES_GROUP` order regardless of
input order (and `""` when every type of change is unchecked), and the badge-count rules (single-choice
groups, symmetric difference for types of change, excluded app languages only). An agent that moves the
existing code faithfully passes; an agent that "simplifies" and changes an output fails.

Observations from the base code that the ticket states explicitly:
- `latestRevisions()` is `!containsAll(LATEST_REVISIONS_GROUP) && !contains(LATEST_REVISION)` → `"1"`,
  which reduces to "null iff `latestRevision` is included".
- In the user-status group, `REGISTERED` (`!anon`) is appended before `UNREGISTERED` (`anon`); only one
  is ever selected via the UI, and no test selects both.
- The count only includes excluded codes that are current app languages
  (`appLanguageCodes.count { excludedWikiCodes.contains(it) }`).

The near-copy in `SuggestedEditsRecentEditsViewModel` is explicitly out of scope and untouched.

## Production files changed

- `app/src/main/java/org/wikipedia/watchlist/WatchlistFilterHelper.kt` (new; logic moved verbatim from the ViewModel, parameterised)
- `app/src/main/java/org/wikipedia/watchlist/WatchlistViewModel.kt` (private `latestRevisions()` / `showCriteriaString()` / `showTypesString()` removed; `fetchWatchlist()` and `filtersCount()` delegate to the helper)

## Hidden tests

File: `app/src/test/java/org/wikipedia/watchlist/WatchlistFilterHelperTest.kt` (plain JUnit4, no Robolectric; only `WatchlistFilterTypes` enum ids are used as inputs).

| Test method | Expected at base |
|---|---|
| `default filters ask for the latest revision only` | compile error |
| `default filters send an empty show criteria` | compile error |
| `default filters send page edits, page creations and logged actions` | compile error |
| `default filters count as no filters` | compile error |
| `not latest revision asks for all revisions` | compile error |
| `non-default single choice filters are sent in group order` | compile error |
| `only the non-default single choice filter is sent` | compile error |
| `types of change are sent in the order of the type of changes group` | compile error |
| `no types of change sends an empty type string` | compile error |
| `each non-default single choice group counts as one filter` | compile error |
| `each type of change that differs from the default counts as one filter` | compile error |
| `each excluded app language counts as one filter` | compile error |
| `excluded languages that are not app languages are not counted` | compile error |

All tests are F2P only because `WatchlistFilterHelper` is new surface (D-020); every expected value
equals what the base ViewModel code produces for the same inputs. There are no P2P tests in the new
file; the existing suite must keep passing.

## Module / Gradle task

`:app` — `:app:testDevDebugUnitTest` (filter: `org.wikipedia.watchlist.WatchlistFilterHelperTest`).

## Risks

- The ticket must name `WatchlistViewModel` as the class whose logic is being moved; for a refactor
  ticket that is unavoidable (otherwise "no behaviour change" has no reference point). No file paths,
  test classes or test methods are named.
- Signature sensitivity: tests call the four functions positionally with `Set<String>` for
  `includedTypeCodes` / `excludedWikiCodes` and `List<String>` for `appLanguageCodes`, so implementations
  that use `Collection`, `Set`/`List` or `Iterable` for these parameters all compile. The parameter order of
  `filtersCount(includedTypeCodes, excludedWikiCodes, appLanguageCodes)` is stated in the ticket and
  matters.
- `WatchlistFilterTypes` references `R.string` ids; plain JVM tests already load such classes
  (e.g. `YearInReviewFlowDeciderTest` → `ArticleTopics`), and `includeAndroidResources = true` is set, so no
  Robolectric runner is needed.
- Not compiled or run by the author (brief forbids Gradle); the harness validation must confirm
  compile + pass with the gold patch and compile failure at base.
