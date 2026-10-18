# Provenance notes (not shown to agents)

- Source: mined from https://github.com/wikimedia/apps-android-wikipedia/pull/6953 (merged 2026-10-06), closing https://phabricator.wikimedia.org/T413154 (opened 2025-12-19); post-cutoff: False.
- PR test files: ['app/src/test/java/org/wikipedia/page/PageTitleTest.kt']
- PR non-test files (gold.patch): ['app/src/main/java/org/wikipedia/language/LanguageUtil.kt', 'app/src/main/java/org/wikipedia/page/PageTitle.kt']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
- Ticket edit (2026-10-18): added a developer comment naming zh-min-nan and zh-yue, which the hidden test also checks; the user report mentions zh-classical only.
