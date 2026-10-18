# Provenance notes (not shown to agents)

- Source: mined from https://github.com/wikimedia/apps-android-wikipedia/pull/6750 (merged 2026-08-03), closing https://phabricator.wikimedia.org/T415791 (opened 2026-01-28); post-cutoff: False.
- PR test files: ['app/src/test/java/org/wikipedia/dataclient/donate/CampaignCollectionTest.kt']
- PR non-test files (gold.patch): ['app/src/main/java/org/wikipedia/dataclient/donate/CampaignCollection.kt']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
- Ticket edit (2026-10-18): added an Android status comment; at this task's base (after PR #6269) three of the five parameters exist and the hidden test adds the remaining two.
