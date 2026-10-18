**Watchlist: move filter → API parameter logic out of WatchlistViewModel so it can be unit tested**

Type: Tech debt / refactoring · Tags: Android app, Watchlist

### Background

`WatchlistViewModel` currently works out the `list=watchlist` query parameters (`wlallrev`, `wlshow`, `wltype`) and the number shown on the filter badge on its own, reading the watchlist filter preferences directly every time. Because the ViewModel also starts a network fetch as soon as it is created, none of this logic can be covered by a plain unit test, and today it has no test coverage at all.

We'd like to pull this logic into a small, pure helper that takes the filter state as plain inputs, and have the ViewModel delegate to it.

### Requirements

Please add an `object WatchlistFilterHelper` in `org.wikipedia.watchlist` with the following functions. `includedTypeCodes` is the set of `WatchlistFilterTypes.id`s that are currently selected (i.e. what `Prefs.watchlistIncludedTypeCodes` holds; by default the ids of `WatchlistFilterTypes.DEFAULT_FILTER_TYPE_SET`).

* `fun latestRevisions(includedTypeCodes: Collection<String>): String?` — the `wlallrev` value: `null` when `latestRevision` is among the included codes, otherwise `NOT_LATEST_REVISION.value` (`"1"`).
* `fun showCriteriaString(includedTypeCodes: Collection<String>): String` — the `wlshow` value. Each single-choice group that is not on its "All" option contributes the `value` of the selected option, joined with `|` in this group order: watchlist activity (`unread` / `!unread`), automated contributions (`bot` / `!bot`), significance (`minor` / `!minor`), user status (`!anon` for registered / `anon` for unregistered). Groups on "All" contribute nothing, so the default filters give `""`. Example: not latest revision + unseen + human + non-minor + registered → `unread|!bot|!minor|!anon`.
* `fun showTypesString(includedTypeCodes: Collection<String>): String` — the `wltype` value: the `value`s of the included types of change, joined with `|` in the order of `WatchlistFilterTypes.TYPE_OF_CHANGES_GROUP` (`edit`, `new`, `categorize`, `external`, `log`) no matter in which order the codes are passed; `""` when no type of change is included. Defaults → `edit|new|log`.
* `fun filtersCount(includedTypeCodes: Collection<String>, excludedWikiCodes: Collection<String>, appLanguageCodes: List<String>): Int` — the filter badge count:
  * +1 for every app language whose code is in `excludedWikiCodes` (excluded codes that are no longer app languages are not counted),
  * +1 for every type of change that differs from the default — a default type (`DEFAULT_FILTER_TYPE_OF_CHANGES`) that is not selected, or a non-default type that is selected,
  * +1 for every single-choice group whose default option (`DEFAULT_FILTER_OTHERS`) is not selected.
  * Default filters with no excluded languages → `0`.

`WatchlistViewModel` keeps its public `filtersCount()` and simply passes the current preferences and app languages to the helper, and the watchlist request uses the helper for its three parameters.

**No behaviour change**: for every filter combination the app must send exactly the same `wlallrev` / `wlshow` / `wltype` values as today, and the badge must show the same number.

Out of scope: `SuggestedEditsRecentEditsViewModel` has a near-copy of this logic; we'll handle that in a follow-up task.

### Acceptance criteria

* [ ] `WatchlistFilterHelper` exists with the functions above and has no dependency on `Prefs` or the app language state.
* [ ] `WatchlistViewModel` delegates to it; the watchlist and the filter badge behave exactly as before.
* [ ] Unit tests cover the default filters and some non-default combinations.
