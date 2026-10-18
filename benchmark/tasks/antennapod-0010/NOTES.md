# Provenance notes (not shown to agents)

- Source: authored for this benchmark (drafted by the building agent with claude-opus-5-5 at base 3d105d598dfa582c6cb22ba40b56d11780366890).

# antennapod-0010 — reviewer notes (not shown to agents)

**What it checks.** A cross-module feature: support for the iTunes `<itunes:episodeType>` item
tag (full / trailer / bonus), end to end. The agent must add a new model enum and accessors on
`FeedItem`, parse the tag in the feed parser with the stated normalisation (case-insensitive,
trimmed, unknown/missing → `FULL`), make `updateFromOther` carry the type across a refresh, and
persist it in the episodes table with a schema upgrade, select-list and cursor-mapping change so
that it survives save + reload and follows a feed refresh. This is realistic: it is the same shape
as recent upstream additions of per-episode feed fields (`podcast:socialInteract`,
`podcast:transcript`), which touched exactly these layers, and episode type is a long-standing,
widely used Apple tag. The hidden tests only use the public API the maintainer comment names
(`FeedItem.EpisodeType` with `FULL`/`TRAILER`/`BONUS`, `getEpisodeType()`, `setEpisodeType()`,
the existing `updateFromOther`) plus existing entry points (`FeedHandler` via the existing test
helper, `FeedDatabaseWriter.updateFeed`, `DBReader.getFeedItemList`). They do not assert column
names, column types, DB version numbers, enum codes or log output.

## Production files changed (gold)
- `model/src/main/java/de/danoeh/antennapod/model/feed/FeedItem.java`: enum `EpisodeType`
  (int `code` + `fromCode`, same as the `FeedPreferences` enums), non-null field defaulting to
  `FULL`, getter/setter, extra DB-constructor parameter, copied in `updateFromOther`.
- `parser/feed/src/main/java/de/danoeh/antennapod/parser/feed/namespace/Itunes.java`: handles
  `episodeType` in `handleElementEnd` for the current item.
- `storage/database/src/main/java/de/danoeh/antennapod/storage/database/PodDBAdapter.java`:
  `KEY_EPISODE_TYPE`, column in `CREATE_TABLE_FEED_ITEMS` (`INTEGER DEFAULT 0`), added to
  `KEYS_FEED_ITEM_WITHOUT_DESCRIPTION`, written in `updateOrInsertFeedItem`, `VERSION`
  3110000 → 3130000.
- `storage/database/src/main/java/de/danoeh/antennapod/storage/database/DBUpgrader.java`:
  `if (oldVersion < 3130000)` adds the column.
- `storage/database/src/main/java/de/danoeh/antennapod/storage/database/mapper/FeedItemCursor.java`:
  reads the column into the DB constructor.

## Hidden test files
- `parser/feed/src/test/java/de/danoeh/antennapod/parser/feed/element/namespace/ItunesEpisodeTypeTest.java` (Robolectric)
- `parser/feed/src/test/resources/feed-rss-testItunesEpisodeType.xml` (fixture: five items: `trailer`, ` Bonus `, `full`, no tag, `teaser`)
- `model/src/test/java/de/danoeh/antennapod/model/feed/FeedItemEpisodeTypeTest.java` (plain JUnit, uses the existing `FeedItemMother`)
- `storage/database/src/test/java/de/danoeh/antennapod/storage/database/EpisodeTypeStorageTest.java` (Robolectric, same setup as `FeedDatabaseWriterTest`)

## Test methods (expected at base)
Every hidden test references `FeedItem.EpisodeType`, which does not exist at base, so each
module's test source set fails to compile at base.

| Module | Test | Expected at base |
|---|---|---|
| `:parser:feed` | `ItunesEpisodeTypeTest.testTrailer` — `trailer` → `TRAILER` | compile error |
| `:parser:feed` | `ItunesEpisodeTypeTest.testBonusIgnoresCaseAndWhitespace` — `" Bonus "` → `BONUS` | compile error |
| `:parser:feed` | `ItunesEpisodeTypeTest.testFull` — `full` → `FULL` | compile error |
| `:parser:feed` | `ItunesEpisodeTypeTest.testMissingIsFull` — no tag → `FULL` | compile error |
| `:parser:feed` | `ItunesEpisodeTypeTest.testUnknownValueIsFull` — `teaser` → `FULL` | compile error |
| `:model` | `FeedItemEpisodeTypeTest.testDefaultIsFull` | compile error |
| `:model` | `FeedItemEpisodeTypeTest.testSetEpisodeType` | compile error |
| `:model` | `FeedItemEpisodeTypeTest.testUpdateFromOther_episodeTypeChanged` — FULL → TRAILER → BONUS via `updateFromOther` | compile error |
| `:storage:database` | `EpisodeTypeStorageTest.testEpisodeTypeSurvivesSaveAndReload` — TRAILER/BONUS/FULL items saved with `updateFeed`, reloaded with `DBReader` | compile error |
| `:storage:database` | `EpisodeTypeStorageTest.testEpisodeTypeUpdatedOnFeedRefresh` — TRAILER saved, refresh with BONUS, reload → BONUS | compile error |

F2P classes:
- `:parser:feed` → `de.danoeh.antennapod.parser.feed.element.namespace.ItunesEpisodeTypeTest`
- `:model` → `de.danoeh.antennapod.model.feed.FeedItemEpisodeTypeTest`
- `:storage:database` → `de.danoeh.antennapod.storage.database.EpisodeTypeStorageTest`

P2P (whole module): `:model`, `:parser:feed`, `:storage:database` (the gold modules; the DB
constructor change only has the `FeedItemCursor` caller, so no other module is affected).
`:storage:database` has the free/play flavors (`playFlavor.gradle`), so its unit tests run as
`testFreeDebugUnitTest` / `testPlayDebugUnitTest`.

## Risks / reviewer attention
- **Task lint `identifier-leak`:** the ticket has to name `EpisodeType` (D-020, the tests use
  it), but `EpisodeType` is also a CamelCase identifier that only the gold patch introduces, so
  `abb task lint` will probably report `identifier-leak` for it. Earlier tasks did not hit this
  because their new surface was a lower-case method name. Either the lint should leave out
  identifiers the tests use (the new surface) or this task needs `tags.ticket_mentions_code: true`.
  Set `tags.new_surface: true` in any case.
- `testFull`, `testMissingIsFull`, `testUnknownValueIsFull` and `testDefaultIsFull` would also
  pass with an implementation that adds the enum but never parses the tag. They are F2P only by
  compile error and pin the default rules the ticket states; the trailer/bonus tests and the
  storage tests cover the real work.
- Gold copies the type in `updateFromOther` without a condition, so removing the tag on refresh
  turns a trailer back into `FULL`. The tests do not check that reverse case: an implementation
  with a nullable field (getter maps null to `FULL`) that copies only non-null values also
  passes.
- The DB version 3130000 was chosen as "next release" (base app is 3.12.3, DB was 3110000). Tests
  do not depend on it; any value above 3110000 with a matching upgrade step works, and so does
  a TEXT column.
- Nothing was compiled or run (brief forbids Gradle here); the harness must confirm that gold
  passes and that base fails to compile.
