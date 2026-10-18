# Provenance notes (not shown to agents)

- Source: authored for this benchmark (drafted by the building agent with claude-opus-5-5 at base 3d105d598dfa582c6cb22ba40b56d11780366890).

# antennapod-0012 — reviewer notes

**What it checks / why realistic.** "Keep my folders across OPML export/import" is a long-standing
user wish for AntennaPod, whose folders are feed tags (`FeedPreferences.getTags()`). The task needs
changes in both directions of the existing OPML code in `:storage:importexport`. On import, the
streaming XmlPullParser reader has to track nesting: a folder is an `<outline>` without `xmlUrl`, a
feed gets every enclosing folder, and a feed listed in several folders is merged into one
`OpmlElement` that keeps its first position. On export, feeds are grouped by tag, the internal
`#root` tag is ignored, untagged feeds and feeds with null preferences stay at the top level, and the
ticket fixes the order (top level first, then folders A-Z ignoring case). The hidden tests read
hand-written OPML and round-trip through the writer. They check structure (each feed outline's direct
parent folder and the document order) by parsing the XML, never by comparing its text or whitespace.
The ticket names the only new API, `OpmlElement.getTags()` (D-020), plus the existing
`FeedPreferences.TAG_ROOT`. Applying the tags in the import UI is left as a follow-up, as the
maintainer says in the ticket.

**Production files changed**
- `storage/importexport/src/main/java/de/danoeh/antennapod/storage/importexport/OpmlElement.java`: adds the `Set<String> tags` field and `getTags()`.
- `storage/importexport/src/main/java/de/danoeh/antennapod/storage/importexport/OpmlReader.java`: tracks the stack of open outlines, assigns folder tags and merges duplicates by `xmlUrl`.
- `storage/importexport/src/main/java/de/danoeh/antennapod/storage/importexport/OpmlWriter.java`: writes top-level feeds, then one folder per tag sorted case-insensitively; adds a private `writeFeed` helper.

No app/UI changes. `OpmlImportActivity` and `OpmlBackupAgent` compile unchanged because the API change only adds things.

**Hidden tests**: new file
`storage/importexport/src/test/java/de/danoeh/antennapod/storage/importexport/OpmlTagsTest.java`
(JUnit4 + `RobolectricTestRunner`, the same setup as the existing `OpmlReaderTest`/`OpmlWriterTest`).
At base, every method fails to compile because `OpmlElement.getTags()` does not exist. The note after
each method says what would happen at base if it did compile.

| Test method | Expected at base |
|---|---|
| `testReadFeedInFolderGetsFolderAsTag` | compile error (behaviour: no tags) |
| `testReadTopLevelFeedsHaveNoTags` (top-level feeds before and after a folder: empty; feed in folder: `{Tech}`) | compile error (behaviour: the `{Tech}` assertion fails) |
| `testReadNestedFoldersGiveAllEnclosingFoldersAsTags` (`{News, Local}` for the inner feed, `{News}` for the sibling after the inner folder closes) | compile error |
| `testReadSameFeedInTwoFoldersIsReturnedOnceWithBothTags` (3 elements, first-occurrence order, merged tags) | compile error (behaviour: base returns 4 elements) |
| `testWriteRoundTripIgnoresRootTag` (`{#root, News}` reads back as `{News}`, one element) | compile error (behaviour: base writes flat, so tags are empty) |
| `testWriteFeedWithTwoTagsIsInBothFolders` (the feed outline appears under `News` and under `Tech`; reads back as one element with both tags) | compile error (behaviour: base writes it once, at the top level) |
| `testWriteFeedsWithoutTagsStayAtTopLevel` (null preferences, empty tags and `#root`-only stay direct children of `<body>`; a `News` feed is inside `News`) | compile error (behaviour: the untagged parts pin existing behaviour; the `News/` assertion fails) |
| `testWriteTopLevelFeedsFirstThenFoldersAlphabetically` (`alpha` before `Beta`, so the sort must ignore case; top level first) | compile error (behaviour: base keeps the flat input order) |

The existing `OpmlReaderTest` (7 methods) and `OpmlWriterTest` (3 methods) must still pass. They
pass at base and with the gold patch (P2P), including `testNestedCategoryFeeds`.

**Module whose tests must run:** `:storage:importexport` (unit tests; the module applies
`playFlavor.gradle`, so use e.g. `:storage:importexport:testPlayDebugUnitTest`, or the free variant).

**Risks / judgement calls**
- The tests compare tags with `Set.equals`, so any `Set` implementation (mutable or not) passes. They never mutate `getTags()`.
- The folder outline is identified by its `text` attribute, as the ticket specifies (`<outline text="TagName">`). An extra `title` attribute on folders is allowed.
- The order test pins the order the ticket states explicitly: top-level feeds first in input order, then folders sorted case-insensitively. `alpha`/`Beta` makes a case-sensitive sort fail.
- Leniency the tests do not pin: (a) whether a folder's name comes from `title` or `text` (tests use `text` only); (b) merging of duplicate `xmlUrl`s at the top level of a flat file (gold merges them, as the ticket says); (c) an implementation that also writes `{#root, X}` feeds at the top level would still pass, because the reader merges the duplicate.
- Determinism: no locale, time or network dependence. The writer's `dateCreated` is never asserted. `compareToIgnoreCase` does not depend on the locale.
- Not compiled or run by the author (the brief says no Gradle). The harness must confirm that F2P fails and P2P passes at base.
