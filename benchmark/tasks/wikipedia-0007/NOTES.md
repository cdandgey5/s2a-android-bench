# Provenance notes (not shown to agents)

- Source: mined from https://github.com/wikimedia/apps-android-wikipedia/pull/6770 (merged 2026-08-07), fixing
  https://phabricator.wikimedia.org/T434037 (opened 2026-08-04); post-cutoff: True.
- gold.patch is the upstream fix (WikiSite.normalizeLanguageCode maps `nan` to `zh-min-nan`;
  AppLanguageLookUpTable gives `nan` the legacy name). The PR has no unit test: **test.patch was written for
  this benchmark** (`hidden_tests: authored`, D-047), in the style of WikiSiteTest, and pins only behaviour the
  ticket describes (the article opens on zh-min-nan.wikipedia.org) plus the language name the picker shows and
  that neighbouring codes are unchanged. Validation decides which methods fail at base.
- Ticket: the Phabricator report, unchanged.
