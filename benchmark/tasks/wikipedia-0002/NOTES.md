# Provenance notes (not shown to agents)

- Source: mined from https://github.com/wikimedia/apps-android-wikipedia/pull/6768 (merged 2026-08-04), closing https://phabricator.wikimedia.org/T433832 (opened 2026-08-03); post-cutoff: True.
- PR test files: ['app/src/test/java/org/wikipedia/dataclient/SharedPreferenceCookieManagerTest.kt']
- PR non-test files (gold.patch): ['app/src/main/java/org/wikipedia/dataclient/SharedPreferenceCookieManager.kt']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
- Ticket edit (2026-10-18): the Phabricator task is a security@ forwarding note whose details are in a private PDF; rewritten as a maintainer security ticket describing the behaviour the hidden tests pin (approved and unapproved hosts, centralauth_ prefix, own cookies, expiry), without naming the class or method.
