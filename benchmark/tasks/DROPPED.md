# Dropped candidates (reportable: phases/phase-7 step 8)

Every candidate that was promoted to `tasks/` and later removed, with the date and the reason.
No candidate may be dropped after a trial ran on it (`results/*/events.jsonl` proves the order).

| Date | Candidate | Upstream | Stage | Reason |
|---|---|---|---|---|
| 2026-10-18 | (promoted as antennapod-0010) | [PR #8226](https://github.com/AntennaPod/AntennaPod/pull/8226) ID3 TXXX comment frames | before warm, before any trial | base commit (2026-01-07) still on Gradle 8.13 / AGP 8; with it the octopus `setup_commit` falls to 2025-04-30, so every one-time setup artifact (Spec Kit constitution, S2A map) would be built 18 months before most AntennaPod bases (D-046) |
| 2026-10-18 | (promoted as antennapod-0011) | [PR #7537](https://github.com/AntennaPod/AntennaPod/pull/7537) VTT transcripts | before warm, before any trial | same: base 2025-04-30, Gradle 8.10.2 / AGP 8 (D-046) |
| 2026-10-18 | (promoted as antennapod-0012) | [PR #8389](https://github.com/AntennaPod/AntennaPod/pull/8389) mini rewind after interruption | before warm, before any trial | same: base 2026-04-12, Gradle 8.13 / AGP 8 (D-046) |
| 2026-10-18 | (promoted as wikipedia-0007) | [PR #6986](https://github.com/wikimedia/apps-android-wikipedia/pull/6986) Year in Review top topic slides ([T438529](https://phabricator.wikimedia.org/T438529)) | ticket review, before any trial | the PR's test change only adapts one constructor call in a fixture; the hidden test would pin a data-class signature, not the slides' behaviour (the logic sits in database queries the unit tests do not reach) |
| 2026-10-18 | (promoted as wikipedia-0008) | [PR #7012](https://github.com/wikimedia/apps-android-wikipedia/pull/7012) Year in Review top topics fix (same task) | ticket review, before any trial | same: one changed constructor call; also the same Phabricator story as #6986 |
| 2026-10-18 | (promoted as wikipedia-0009) | [PR #6672](https://github.com/wikimedia/apps-android-wikipedia/pull/6672) Did You Know module ([T418898](https://phabricator.wikimedia.org/T418898)) | ticket review, before any trial | the only hidden test covers a new string helper (`StringUtil.removeBoldTags`), not the module the ticket asks for; naming the helper would turn the task into "write this function" |
| 2026-10-18 | (reverted, promoted as wikipedia-0010) | [PR #6992](https://github.com/wikimedia/apps-android-wikipedia/pull/6992) Year in Review total articles ([T437757](https://phabricator.wikimedia.org/T437757)) | ticket review, before any trial | the hidden tests (percentile buckets) already pass at base — the bucket lookup exists there; the PR's behaviour change (main pages and non-article pages excluded from the count) is in a Room query no unit test covers |
