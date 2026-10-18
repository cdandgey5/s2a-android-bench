# Provenance notes (not shown to agents)

- Source: mined from https://github.com/AntennaPod/AntennaPod/pull/8722 (merged 2026-09-10), closing https://github.com/AntennaPod/AntennaPod/issues/8721 (opened 2026-09-08); post-cutoff: True.
- PR test files: ['parser/feed/src/test/java/de/danoeh/antennapod/parser/feed/element/namespace/RssParserTest.java', 'parser/feed/src/test/resources/feed-rss-testLegacyItunesNamespace.xml']
- PR non-test files (gold.patch): ['parser/feed/src/main/java/de/danoeh/antennapod/parser/feed/SyndHandler.java', 'parser/feed/src/main/java/de/danoeh/antennapod/parser/feed/namespace/Itunes.java']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
- Review edits (agent, 2026-10-18): removed the issue's diagnosis paragraph that named `SyndHandler` and `Itunes.NSURI` (the fix location) and the AI-assistant footer; kept the feed URL and the namespace URI as the feed declares it. F2P narrowed to `RssParserTest.testLegacyItunesNamespace`; the test resource `feed-rss-testLegacyItunesNamespace.xml` is part of test.patch.
