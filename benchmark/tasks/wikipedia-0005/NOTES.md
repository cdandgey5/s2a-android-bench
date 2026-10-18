# Provenance notes (not shown to agents)

- Source: mined from https://github.com/wikimedia/apps-android-wikipedia/pull/6381 (merged 2026-03-16), closing https://phabricator.wikimedia.org/T419369 (opened 2026-03-09); post-cutoff: False.
- PR test files: ['app/src/test/java/org/wikipedia/notifications/NotificationClientTest.kt']
- PR non-test files (gold.patch): ['app/src/main/java/org/wikipedia/dataclient/Service.kt', 'app/src/main/java/org/wikipedia/notifications/NotificationPollBroadcastReceiver.kt', 'app/src/main/java/org/wikipedia/notifications/NotificationRepository.kt', 'app/src/main/java/org/wikipedia/notifications/NotificationViewModel.kt', 'app/src/main/java/org/wikipedia/notifications/PollNotificationWorker.kt']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
- Ticket edit (2026-10-18): added a developer comment naming the new signature of `Service.getAllNotifications` (the hidden test calls it with two arguments, so it does not compile at base: new_surface, D-020) and the unknown-wiki case the fix also handles.
