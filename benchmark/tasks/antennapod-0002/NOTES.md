# Provenance notes (not shown to agents)

- Source: mined from https://github.com/AntennaPod/AntennaPod/pull/8773 (merged 2026-09-19), closing https://github.com/AntennaPod/AntennaPod/issues/8772 (opened 2026-09-19); post-cutoff: True.
- PR test files: ['net/common/src/test/java/de/danoeh/antennapod/net/common/UrlCheckerTest.java']
- PR non-test files (gold.patch): ['net/common/src/main/java/de/danoeh/antennapod/net/common/UrlChecker.java']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
- Review edits (agent, 2026-10-18): the upstream issue (#8772) is an AI-generated, code-level report (it names `UrlChecker.prepareUrl` / `UrlChecker.java`, quotes a stack trace through it and describes the fix). Rewritten as the user-visible bug it reports (an uppercase SubscribeOnAndroid link crashes instead of subscribing), with no code names (`ticket_mentions_code: false`).
- S2 review: approved by the owner on 2026-10-18 (unchanged).
- Validation (2026-10-18): `testSubscribeOnAndroidUrlWithoutScheme` (uppercase host, no scheme) also fails at base -> added to F2P; the ticket now mentions scheme-less links.
