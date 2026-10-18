# Provenance notes (not shown to agents)

- Source: authored for this benchmark (drafted by the building agent with claude-opus-5-5 at base 3d105d598dfa582c6cb22ba40b56d11780366890).

# antennapod-0011 — reviewer notes (not shown to agents)

**Category:** refactor. **Base:** upstream 3d105d598dfa582c6cb22ba40b56d11780366890.

## What the task checks and why it is realistic

`DBReader.getNavDrawerData(...)` and `DBReader.getAllTags(int)` each carry a near-identical copy of the
"group feeds into tag folders" loop (same untagged check, same case-insensitive sort), differing only in
deliberate details: the nav-drawer variant keeps `#root` as an ordinary folder, sums per-feed counters
(missing id = 0), and puts `#untagged` (counter always 0) at the front; `getAllTags` skips `#root` as a
folder, prepends an all-feeds `#root` entry (present even for empty input), appends `#untagged` at the end,
and has all counters 0. The ticket asks for the classic maintainer refactor: extract both into pure static
methods `NavDrawerData.groupFeedsByTag(List<Feed>, Map<Long, Integer>)` and `NavDrawerData.buildTagList(List<Feed>)`
(both returning `List<NavDrawerData.TagItem>`), have DBReader delegate, no behaviour change. The hidden tests
are plain JUnit4 (no Robolectric, no DB) built from in-memory `Feed`/`FeedPreferences` objects and pin today's
behaviour, so an agent that "harmonises" the two variants (e.g. skips `#root` in the drawer, sums the
`#untagged` counter, puts `#untagged` in the same place in both, sorts case-sensitively, re-sorts feeds inside a
folder) fails. Every pinned detail is stated explicitly in the ticket. The reference fix keeps the HashMap
insertion order and stable sort of the original code, so it is byte-for-byte equivalent (verified by reading,
not by running — no build was allowed).

## Production files changed

- `storage/database/src/main/java/de/danoeh/antennapod/storage/database/NavDrawerData.java` — new
  `groupFeedsByTag`, `buildTagList` (+ two private helpers); existing comment moved here from DBReader.
- `storage/database/src/main/java/de/danoeh/antennapod/storage/database/DBReader.java` — both methods
  delegate; unused `HashMap` / `FeedPreferences` imports removed. `FeedOrder` comparators untouched.

## Hidden tests

New file `storage/database/src/test/java/de/danoeh/antennapod/storage/database/NavDrawerDataTest.java`
(plain JUnit4). All methods: **expected at base: compile error** (the two methods do not exist yet — D-020
new surface); all pass with the reference fix and pin existing behaviour.

| Test method | Pins | Expected at base |
|---|---|---|
| `testGroupFeedsByTagSortsFoldersIgnoringCase` | folder order case-insensitive | compile error |
| `testGroupFeedsByTagSumsCounters` | counter sum, missing id = 0, extra map ids ignored, feed order = input order | compile error |
| `testGroupFeedsByTagFeedInSeveralTags` | feed in each of its folders, counter added to each | compile error |
| `testGroupFeedsByTagUntaggedFolderFirst` | `#untagged` first (no tags or only `#root`), counter 0, `#root` sorted with others | compile error |
| `testGroupFeedsByTagRootFolder` | `#root` is a normal folder with summed counter; root-only feed in both `#untagged` and `#root` | compile error |
| `testGroupFeedsByTagNoUntaggedFolderWhenAllTagged` | no `#untagged` entry when none untagged | compile error |
| `testGroupFeedsByTagEmpty` | empty input -> empty list | compile error |
| `testBuildTagListRootFirstWithAllFeeds` | `#root` first, all feeds in input order, counter 0 | compile error |
| `testBuildTagListSortsFoldersIgnoringCase` | case-insensitive order, `#root` tag not a separate folder, all counters 0 | compile error |
| `testBuildTagListFeedInSeveralTags` | feed in each of its folders, input order | compile error |
| `testBuildTagListUntaggedLast` | `#untagged` last, contains no-tag and root-only feeds, counter 0 | compile error |
| `testBuildTagListNoUntaggedEntryWhenAllTagged` | no `#untagged` entry when none untagged | compile error |
| `testBuildTagListEmpty` | empty input -> only an empty `#root` entry | compile error |

## Modules whose tests must run

- `:storage:database` (e.g. `:storage:database:testPlayDebugUnitTest`) — hidden tests.
- Optional regression: `:net:download:service` (`DbReaderTest` calls `getNavDrawerData` through the DB).

## Risks

- Tests are plain JUnit on an Android library module. They avoid Android stubs: the `Feed(url, lastModified, title)`
  constructor and the 7-arg `FeedPreferences` constructor are pure Java; `FeedPreferences.getTagsAsString()`
  (which uses `TextUtils`) is never called. Not compiled/run here (no Gradle allowed) — the harness must confirm.
- Tie order of tags that are equal ignoring case (e.g. "News" vs "news") depends on HashMap order and is
  deliberately not tested or specified.
- The ticket names `DBReader.getNavDrawerData` / `getAllTags` because describing the duplication requires it;
  it does not name files, test classes or the private helpers.
