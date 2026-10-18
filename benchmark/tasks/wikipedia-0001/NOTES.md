# Provenance notes (not shown to agents)

- Source: mined from https://github.com/wikimedia/apps-android-wikipedia/pull/6631 (merged 2026-05-26), closing https://phabricator.wikimedia.org/T426910 (opened 2026-05-20); post-cutoff: False.
- PR test files: ['app/src/test/java/org/wikipedia/richtext/CustomHtmlParserTest.kt']
- PR non-test files (gold.patch): ['app/src/main/java/org/wikipedia/richtext/CustomHtmlParser.kt']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
- Ticket edit (2026-10-18): added a developer triage comment with the reference HTML pattern and the expected rendering; the original Phabricator report only says previews look broken and the agent has no network to fetch the HTML. The hidden tests also pin `display: none` with a space, which the comment states.
