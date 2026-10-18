# Provenance notes (not shown to agents)

- Source: authored for this benchmark (drafted by the building agent with claude-opus-5-5 at base 0c7ee9b4682512217e01d829fb0b6d068d268724).

# wikipedia-0008 — reviewer notes

**What the task checks.** Offline (reading-list) copies of articles never record which revision was
downloaded: `ReadingListPage.revId` exists in the Room entity and table but nothing in the app sets
it, `SavedPageSyncService.savePageFor` copies only display title and description from the
`PageSummary` it downloads, and `PageSummary.revision` is parsed but unused for saved pages. The task
asks the agent to (1) record the summary revision when saving (`ReadingListPage.applySummary`), (2)
decide staleness with a pure rule (`ReadingListPage.isOutdated`: offline, status SAVED, `0 < revId <
latest`), and (3) add `SavedPageRevisionChecker`, which, given the revision of an article just loaded
online, queues every stale saved occurrence for a forced save (`STATUS_QUEUE_FOR_FORCED_SAVE`) and
triggers the saved-page sync once. It is cross-module in the app sense: `readinglist/database`,
`readinglist/db` (DAO contract), `savedpages`, `page` (load path) and `dataclient/page` (summary). It
is realistic: stale offline copies are a long-standing user complaint, the `revId` column is a
leftover of exactly this intent, and the pitfall that `ReadingListPageDao.markPagesForOffline(...,
offline = true, forcedSave = true)` silently skips pages that are already offline makes the obvious
reuse wrong — the gold sets the status and calls `updateReadingListPages` directly.

**Production files changed (gold)**
- `app/src/main/java/org/wikipedia/readinglist/database/ReadingListPage.kt` — `isOutdated(latestRevision)`, `applySummary(summary)`.
- `app/src/main/java/org/wikipedia/savedpages/SavedPageSyncService.kt` — `savePageFor` uses `page.applySummary(summaryResponse)` (now also stores `revId`; persisted by the existing `updateReadingListPage(page)` after a successful save).
- `app/src/main/java/org/wikipedia/savedpages/SavedPageRevisionChecker.kt` — new class.
- `app/src/main/java/org/wikipedia/page/PageFragmentLoadState.kt` — after the summary is loaded, if the response did not come from the offline cache (no `X-Offline-Save` response header) and the page is in a reading list, fire-and-forget `SavedPageRevisionChecker().checkForUpdates(title, revision)` on `MainScope()` with a logging `CoroutineExceptionHandler` (same pattern as the history upsert in `createPageModel`); page load is not blocked.

No new strings, no DB migration (column already exists).

**Hidden tests** — new file `app/src/test/java/org/wikipedia/savedpages/SavedPageRevisionCheckerTest.kt`
(Robolectric runner, relaxed MockK `ReadingListPageDao`, mirrors `InterestSelectionRepositoryTest`).
The whole file references API that does not exist at base, so every method is a compile error at base.

| Test method | Expected at base |
|---|---|
| `an offline copy saved at an older revision is outdated` | compile error |
| `an offline copy with an unknown revision is not outdated` | compile error |
| `a copy that is not saved offline is not outdated` | compile error |
| `a copy that has not finished saving is not outdated` | compile error |
| `an offline copy at the same or a newer revision is not outdated` | compile error |
| `only the outdated copy is queued for a forced save and the sync is triggered once` | compile error |
| `nothing is written or queued when no copy is outdated` | compile error |
| `saving a page records the revision of the downloaded summary` | compile error |

The DAO-interaction tests are lenient on purpose: writes through either `updateReadingListPage` or
`updateReadingListPages` are captured; the assertion is that the set of persisted pages carrying
`STATUS_QUEUE_FOR_FORCED_SAVE` is exactly the stale one, that the non-stale page objects keep
`STATUS_SAVED` (copy-or-mutate both pass), and that `enqueueSave` ran exactly once (zero times and no
writes when nothing is stale). The summary test decodes the existing fixture
`app/src/test/res/raw/rb_page_summary_valid.json` with `JsonUtil` (its `"revision": "832091465"` is a
quoted number, which kotlinx.serialization accepts — production decodes the live API the same way)
and checks `revId`, `displayTitle` and `description` after `applySummary`.

**Gradle test task:** `:app:testDevDebugUnitTest` (filter `org.wikipedia.savedpages.SavedPageRevisionCheckerTest`).

**Risks**
- The two wiring points (calling `applySummary` from `SavedPageSyncService.savePageFor`, and calling the checker from the page-load path only for network responses) are not exercised by the hidden tests — they need a WorkManager worker with network and a `PageFragment`. An agent could add the helpers without wiring them and still pass; the reviewer should treat wiring as a code-review item.
- Tests rely on MockK intercepting `getAllPageOccurrences`, a Kotlin interface method with a body (default method); MockK handles interface default methods, but it is the first test in the repo to stub one of the DAO's non-`@Query` helpers.
- The ticket names `getAllPageOccurrences` and `updateReadingListPage(s)` as the DAO contract; an implementation that adds its own `@Query` update method would be correct in the app but fail the mocked-DAO test. The ticket states the contract explicitly to avoid this.
- Not compiled or run locally (per brief); the harness must validate fail-at-base / pass-with-gold.
