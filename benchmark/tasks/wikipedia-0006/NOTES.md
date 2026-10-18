# Provenance notes (not shown to agents)

- Source: mined from https://github.com/wikimedia/apps-android-wikipedia/pull/6544 (merged 2026-04-30), closing https://phabricator.wikimedia.org/T418641 (opened 2026-02-27); post-cutoff: False.
- PR test files: ['app/src/test/java/org/wikipedia/widget/ReadingChallengeWidgetRepositoryTest.kt']
- PR non-test files (gold.patch): ['app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeLargeWidgetContent.kt', 'app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeSmallWidgetContent.kt', 'app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeState.kt', 'app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeWidget.kt', 'app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeWidgetRepository.kt', 'app/src/main/res/drawable/ic_streak_warning.xml']
- F2P draft: every test class the PR touches; narrow it to the methods that fail at base during review.
- Ticket: issue title + body, templates stripped; rewrite before S2 (no file/class names unless the reporter wrote them).
