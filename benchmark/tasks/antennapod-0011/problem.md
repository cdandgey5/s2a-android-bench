# Refactor: move the tag/folder grouping out of DBReader so it can be unit tested

### App version

develop

### Feature or improvement you want

`DBReader.getNavDrawerData(...)` and `DBReader.getAllTags(int)` each contain their own copy of the code that groups feeds into tag folders: both build a map of `NavDrawerData.TagItem`s from `feed.getPreferences().getTags()`, both repeat the same "is this feed untagged?" check (no tags, or only `FeedPreferences.TAG_ROOT`), and both sort the folders with the same case-insensitive comparison. The two copies differ in a few deliberate details (see below), which makes it easy to change one and forget the other. On top of that, the grouping can currently only be exercised through the database.

Please pull the grouping into two pure static methods on `NavDrawerData` (package `de.danoeh.antennapod.storage.database`) and make `DBReader` call them. `DBReader` should keep doing what is actually database work (loading the feeds and counters, filtering by feed state / subscriptions filter, sorting the feeds by the selected `FeedOrder`) and then just delegate.

**No behaviour change.** Both methods must return exactly what the corresponding `DBReader` method builds today.

#### `public static List<NavDrawerData.TagItem> groupFeedsByTag(List<Feed> feeds, Map<Long, Integer> feedCounters)`

This is the grouping used by the navigation drawer (`NavDrawerData.tags`).

- One `TagItem` per distinct tag of the given feeds. `#root` (`FeedPreferences.TAG_ROOT`) is **not** special here: feeds tagged `#root` get a `#root` entry like any other tag.
- These entries are sorted by title, case-insensitively (`compareToIgnoreCase`).
- Each entry contains the feeds that have that tag, in the order of the `feeds` list (the caller has already sorted them). A feed with several tags appears in each of those entries.
- The counter of each entry is the sum of `feedCounters.get(feedId)` over its feeds; a feed that has no value in `feedCounters` counts as 0.
- If at least one feed is untagged (no tags at all, or only `#root`), an extra `FeedPreferences.TAG_UNTAGGED` (`#untagged`) entry is put at the **beginning** of the list, before the sorted entries. It contains the untagged feeds in input order, and its counter is always 0. Note that a feed whose only tag is `#root` therefore shows up in both `#untagged` and `#root`. If no feed is untagged, there is no `#untagged` entry.
- Empty input returns an empty list.

#### `public static List<NavDrawerData.TagItem> buildTagList(List<Feed> feeds)`

This is the tag list used by the subscriptions screen (what `getAllTags` returns).

- The first entry is always `#root`, which here means "all feeds": it contains every feed of the input, in input order.
- Then one entry per distinct tag **other than** `#root`, sorted by title case-insensitively; each contains the feeds with that tag in input order (a feed with several tags appears in each).
- If at least one feed is untagged (no tags at all, or only `#root`), an `#untagged` entry with those feeds (input order) is added at the **end** of the list. Otherwise there is no `#untagged` entry.
- All counters in this list are 0.
- Empty input returns a list containing only the (empty) `#root` entry.

### Why should this be added?

Less duplicated logic in `DBReader`, one place to change when folders behave differently in the future, and the folder logic (ordering, counters, the special `#root` / `#untagged` entries) can be covered by plain unit tests built from in-memory `Feed` objects instead of a database.

### Screenshots / Drawings / Technical details

Pure refactoring, nothing should change for users. Please leave the `FeedOrder` comparators in `getNavDrawerData` as they are.
