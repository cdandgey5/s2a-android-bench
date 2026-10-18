## Notes on dimensions out of tolerance (2026-10-18)

- **ui ≠ none (1 of 25, target ≥ 5) and test_kind compose/screenshot (0, target ≥ 1).** Every hidden
  test in this set is a JVM unit test (JUnit or Robolectric; `needs_emulator: false` everywhere),
  and neither repository runs Compose UI or screenshot tests under `src/test` at these commits
  (AntennaPod's UI tests are instrumented; Wikipedia's are Espresso under `src/androidTest`).
  Mined candidates whose only tests were instrumented (AntennaPod #8702, Wikipedia #6282, #6821)
  were left out, and UI-heavy upstream changes (Wikipedia #6672 and the Year in Review slides)
  were dropped because their unit tests did not reach the behaviour (`DROPPED.md`). Several tasks
  still change UI-facing code (talk-page toolbars, reading-list dialogs, the proxy and add-feed
  screens), but their tests check the logic behind it, so the tag stays `none`. UI tests would
  need an emulator or a Compose test harness in `src/test`, which the MVP cut (D-045) does not
  include. Reported as a known limit.
- **files_bucket 6+ (2, target ≈ 5).** Within the "roughly" wording of the target; the larger
  changes in these repositories mostly came without unit tests.
