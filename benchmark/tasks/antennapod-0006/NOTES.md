# Provenance notes (not shown to agents)

- Source: mined from https://github.com/AntennaPod/AntennaPod/pull/8835 (merged 2026-10-11), closing https://github.com/AntennaPod/AntennaPod/issues/8643 (opened 2026-08-04); post-cutoff: True.
- PR test files: ['net/common/src/test/java/de/danoeh/antennapod/net/common/UrlCheckerTest.java']
- PR non-test files (gold.patch): ['net/common/src/main/java/de/danoeh/antennapod/net/common/UrlChecker.java', 'ui/preferences/src/main/java/de/danoeh/antennapod/ui/preferences/screen/ProxyDialog.java']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
