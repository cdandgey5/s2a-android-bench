# Provenance notes (not shown to agents)

- Source: mined from https://github.com/AntennaPod/AntennaPod/pull/8656 (merged 2026-08-26), closing https://github.com/AntennaPod/AntennaPod/issues/8655 (opened 2026-08-14); post-cutoff: True.
- PR test files: ['net/download/service/src/test/java/de/danoeh/antennapod/net/download/service/episode/autodownload/DbReaderTest.java']
- PR non-test files (gold.patch): ['net/download/service/src/main/java/de/danoeh/antennapod/net/download/service/episode/autodownload/AutomaticDownloadAlgorithm.java', 'storage/database/src/main/java/de/danoeh/antennapod/storage/database/DBReader.java', 'storage/database/src/main/java/de/danoeh/antennapod/storage/database/PodDBAdapter.java']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
