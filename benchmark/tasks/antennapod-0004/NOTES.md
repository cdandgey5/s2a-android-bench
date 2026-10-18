# Provenance notes (not shown to agents)

- Source: reverted feature https://github.com/AntennaPod/AntennaPod/pull/8745 (merged 2026-09-12); base = first parent of e600c0ff14466b21058dc680863c016492519687.
- PR files: ['net/download/service/src/main/java/de/danoeh/antennapod/net/download/service/feed/local/LocalFeedUpdater.java', 'parser/media/src/main/java/de/danoeh/antennapod/parser/media/m4a/M4AMetadataReader.java', 'parser/media/src/main/java/de/danoeh/antennapod/parser/media/m4a/M4AReader.java', 'parser/media/src/test/java/de/danoeh/antennapod/parser/media/m4a/M4AMetadataReaderTest.java', 'parser/media/src/test/resources/ffmpeg.m4a']
- problem.md is written as a feature request in the project's issue style (no upstream issue).
- Ticket (agent, 2026-10-18): written as a maintainer-style feature request. The hidden tests use the surface the feature introduces (`M4AMetadataReader`, `readInputStream()`, `getDescription()`), so the ticket names it (D-020): `tags.new_surface: true`, and `ticket_mentions_code: true` because a reverted task has no upstream ticket and the names are the public surface, not the fix location. It does not describe the atom parsing.
- Pairs with antennapod-0003 (FLAC half of the same user request, #8694); separate base commits.
