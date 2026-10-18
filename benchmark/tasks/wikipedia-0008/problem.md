# Saved articles never refresh their offline copy

**Steps to replicate the issue**

1. Turn on "Download reading list articles" and save an article (e.g. "Fermat's Last Theorem") to a reading list. Wait until it shows as available offline.
2. Edit the article on the web (or wait for someone else to), so that it gets a new revision.
3. In the app, open the article from search or the Explore feed while online.
4. Go offline (airplane mode) and open the article from the reading list.

**What happens?**

The offline copy is still the version that was downloaded in step 1. It is never refreshed, no matter how many times the article is opened online afterwards. The only way to get a current offline copy is to remove the article from the list and save it again.

Looking at the data: `ReadingListPage` has a `revId` column, but it is always `0`. When the saved-page sync downloads an article it copies the display title and description from the page summary, but not the summary's `revision`, so the app has no idea which revision the offline copy is.

**What should have happened instead?**

1. When an article is downloaded for offline reading, the revision of the downloaded summary is recorded on the saved page (`ReadingListPage.revId`), together with the display title and description that are already copied today.
2. When an article is opened **online** and its summary's revision is newer than a saved offline copy of it, that copy is queued for a forced re-download (`ReadingListPage.STATUS_QUEUE_FOR_FORCED_SAVE`) and the saved-page sync is started, so the offline copy catches up in the background. This applies to every reading list the article is saved in. Loading the article itself must not wait for this check.

A saved copy counts as outdated only if all of these hold:
- it is saved for offline reading (`offline == true`);
- it has finished downloading (`status == ReadingListPage.STATUS_SAVED`) — copies that are still queued are left alone;
- its recorded revision is known (`revId > 0`) — copies saved before this change have `revId == 0` and are left alone;
- its recorded revision is older than the revision just loaded. Same or newer revision → nothing to do.

If none of the article's saved copies is outdated, nothing is written to the database and the sync is not started.

**Implementation notes (requested API)**

Please keep the logic testable without a real database or WorkManager:

- `ReadingListPage.isOutdated(latestRevision: Long): Boolean` — the rule above.
- `ReadingListPage.applySummary(summary: PageSummary)` — sets `displayTitle`, `description` (empty string when the summary has none) and `revId` from the summary's `displayTitle`, `description` and `revision`. Use it when a page is saved offline.
- A new class `org.wikipedia.savedpages.SavedPageRevisionChecker(readingListPageDao: ReadingListPageDao, enqueueSave: () -> Unit = { SavedPageSyncService.enqueue() })` with `suspend fun checkForUpdates(title: PageTitle, latestRevision: Long)`. It looks up the saved copies of `title` with `ReadingListPageDao.getAllPageOccurrences(title)`, sets the outdated ones to `STATUS_QUEUE_FOR_FORCED_SAVE`, persists them with `ReadingListPageDao.updateReadingListPages()` (or `updateReadingListPage()`), and then calls `enqueueSave` exactly once. When nothing is outdated it writes nothing and does not call `enqueueSave`. The page-loading code should use this class when an article has been loaded from the network (not from the offline cache).
