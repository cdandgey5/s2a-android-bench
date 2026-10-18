# TRIAGE — dev5 human review (stop point S2)

**S2 result (2026-10-18): approved by the owner, no task dropped or edited.**

Drafted by the building agent (`drafted_by: agent`, `drafted_with_model: claude-opus-5-5`) on
2026-10-17/18. For each task read **`problem.md`** (the only text the agent sees), **`gold.patch`**
(reference fix) and **`test.patch`** (hidden tests); `NOTES.md` says where it came from and what
was edited. Edit or reject in place, then reply `approved` or `approved, dropped: <ids>`.

What to check in every task:
1. Is `problem.md` a fair, realistic ticket? No file/class/test names unless the real reporter
   wrote them (or, for new-surface features, the public API the tests use); nothing that points
   at where the fix goes.
2. Do the hidden tests pin the behaviour the ticket asks for, and nothing the ticket does not ask
   for? Could a correct but differently shaped fix fail them?
3. Is the reference fix minimal and correct?

| Task | Source | Category | Upstream | Base | What was edited / why to look closely |
|---|---|---|---|---|---|
| `antennapod-0000` | authored (seed) | bugfix | — | `3d105d59` | decimal comma in `itunes:duration`; one-line fix in the duration parser; plain JUnit |
| `antennapod-0001` | mined | bugfix | [#8721](https://github.com/AntennaPod/AntennaPod/issues/8721) / [PR #8722](https://github.com/AntennaPod/AntennaPod/pull/8722) | `d05a58b4` | artwork missing for feeds using the legacy iTunes namespace URI. Removed the issue's paragraph naming `SyndHandler` / `Itunes.NSURI` (the fix location) and its AI-assistant footer; F2P = `RssParserTest.testLegacyItunesNamespace` |
| `antennapod-0002` | mined | bugfix | [#8772](https://github.com/AntennaPod/AntennaPod/issues/8772) / [PR #8773](https://github.com/AntennaPod/AntennaPod/pull/8773) | `79107853` | uppercase SubscribeOnAndroid link crashes. The upstream issue is an AI-generated code-level report (stack trace through `UrlChecker.prepareUrl`); **ticket rewritten** as the user-visible bug. F2P = uppercase + mixed-case host tests |
| `antennapod-0003` | mined | feature | [#8694](https://github.com/AntennaPod/AntennaPod/issues/8694) / [PR #8747](https://github.com/AntennaPod/AntennaPod/pull/8747) | `e600c0ff` | FLAC (Vorbis comment) description as shownotes. The issue asks for M4A **and** FLAC; the PR/tests cover FLAC (+ Ogg FLAC). Removed "Suggested implementation" + ffprobe dump; **added a maintainer comment** scoping it to FLAC. 7 F2P methods (validation will move any that already pass at base to P2P); tests ship binary `ffmpeg.flac`/`ffmpeg.oga` |
| `antennapod-0004` | reverted | feature | [PR #8745](https://github.com/AntennaPod/AntennaPod/pull/8745) | parent of #8745 | M4A description as shownotes (the other half of #8694). **Ticket written** as a maintainer feature request that names the new public surface the tests use (`M4AMetadataReader`, `readInputStream()`, `getDescription()`) — `new_surface: true` (D-020) |
| `antennapod-0005` | authored | refactor | — | `3d105d59` | expose `FeedItemPermutors.getComparator(SortOrder)`; `getPermutor` delegates; behaviour unchanged. Hidden Robolectric tests: comparators agree with permutors, `null` for shuffles; the 15 existing tests pin behaviour (P2P). One validation run already passed V0/V1/V2 |

Candidates mined but not used (in `C:\abb\state\candidates\antennapod\`, ranked in `TRIAGE.json`):
#8835 IPv6 proxy host and #8771 single-label hosts (hidden tests call a method the fix adds and
the ticket does not name — interface rule), #8702 (instrumented test only), #8656, #8743, #8433,
#8398, #8389, #8380.

## Edits after S2 (from validation, 2026-10-18)

Validation found two task bugs (not flakiness); both fixed and re-validated. Review the diffs with
`git log -p -- benchmark/tasks/antennapod-0002 benchmark/tasks/antennapod-0003`.

- `antennapod-0002`: the hidden test for a scheme-less uppercase link
  (`SUBSCRIBEONANDROID.COM/...`) also fails at base. It is now F2P, and step 1 of the ticket
  mentions that some sites print links without `https://`.
- `antennapod-0003`: the hidden tests use `MediaFormatDetector.Format.FLAC`, which the fix adds.
  The maintainer comment now names it (D-020), so the task is `new_surface`. Lint now also checks
  ALL-CAPS constants, and it indexes identifiers from code only (not from comments or strings).


---

# TRIAGE — Phase 7 review (stop point S2, 2026-10-18)

**S2 result (2026-10-18): approved by the owner, no task dropped or edited.**

19 new tasks (MVP cut D-045: 25 in total, 13 AntennaPod / 12 Wikipedia). Same three questions as
above for every task (fair ticket? tests pin only what it asks? fix minimal and correct?). Edit or
reject in place, then reply `approved` or `approved, dropped: <ids>` (or ask for changes).
Candidates removed before your review, with reasons: `DROPPED.md`. Coverage vs targets:
`COVERAGE.md` (UI/Compose short, explained there). Each task's `NOTES.md` lists what was edited.

Status column = single validation run (V0 base: P2P pass; V1 base+tests: F2P fail; V2 +gold:
all pass). The 3× validation nights (S3) come after your approval.

### Mined (upstream issue + upstream fix)

| Task | Upstream | Category | What was edited / why to look closely |
|---|---|---|---|
| `antennapod-0006` | [#8643](https://github.com/AntennaPod/AntennaPod/issues/8643) / [PR #8835](https://github.com/AntennaPod/AntennaPod/pull/8835) | bugfix | IPv6 proxy host. Added a **maintainer comment naming `UrlChecker.isValidHost(String)`** (the check lives in a dialog; tests need the new method, D-020) and the rule that `host:port` stays invalid |
| `antennapod-0007` | [#8752](https://github.com/AntennaPod/AntennaPod/issues/8752) / [PR #8771](https://github.com/AntennaPod/AntennaPod/pull/8771) | bugfix | Feed URLs without TLD. Maintainer comment names `UrlChecker.isValidUrl(String)` and lists what the tests check (search words are not URLs, broken input rejected) |
| `antennapod-0008` | [#8655](https://github.com/AntennaPod/AntennaPod/issues/8655) / [PR #8656](https://github.com/AntennaPod/AntennaPod/pull/8656) | refactor | Auto-download query in SQL. Reporter is a developer who names the slow code (kept: the reporter wrote it). Maintainer comment defines `DBReader.getAutoDownloadCandidates(boolean, boolean)` precisely — **check the eligibility rules match your reading of the test** |
| `antennapod-0009` | [#8269](https://github.com/AntennaPod/AntennaPod/issues/8269) / [PR #8743](https://github.com/AntennaPod/AntennaPod/pull/8743) | bugfix | Opus `synopsis` description. **Removed the reporter's last paragraph** (it named the class and the one-line fix) |
| `wikipedia-0001` | [T426910](https://phabricator.wikimedia.org/T426910) / [PR #6631](https://github.com/wikimedia/apps-android-wikipedia/pull/6631) | bugfix | Nested `display:none` in citation previews. **Added a developer triage comment with the reference HTML** (offline agent cannot fetch it) and `display: none` with a space (tested) |
| `wikipedia-0002` | [T433832](https://phabricator.wikimedia.org/T433832) / [PR #6768](https://github.com/wikimedia/apps-android-wikipedia/pull/6768) | bugfix | CentralAuth cookie disclosure. The task is a security@ note with a private PDF: **ticket rewritten** as a maintainer security task stating which hosts may receive the cookies |
| `wikipedia-0003` | [T413154](https://phabricator.wikimedia.org/T413154) / [PR #6953](https://github.com/wikimedia/apps-android-wikipedia/pull/6953) | bugfix | zh-classical share link. Added a comment naming zh-min-nan and zh-yue (also tested) |
| `wikipedia-0004` | [T415791](https://phabricator.wikimedia.org/T415791) / [PR #6750](https://github.com/wikimedia/apps-android-wikipedia/pull/6750) | feature | Fundraising URL placeholders. The spec is the real task; added a status comment: 3 of 5 placeholders exist at this base, `$appVersion;`/`$appInstallId;` are missing |
| `wikipedia-0005` | [T419369](https://phabricator.wikimedia.org/T419369) / [PR #6381](https://github.com/wikimedia/apps-android-wikipedia/pull/6381) | bugfix | `notwikis` limit error. Developer comment names the **new signature `Service.getAllNotifications(filter, continueStr)`** (the hidden test calls it; new surface) |
| `wikipedia-0006` | [T418641](https://phabricator.wikimedia.org/T418641) / [PR #6544](https://github.com/wikimedia/apps-android-wikipedia/pull/6544) | feature | Reading Challenge widget states. Real user story unchanged; 22 state tests, many pin existing behaviour (P2P) |
| `wikipedia-0007` | [T434037](https://phabricator.wikimedia.org/T434037) / [PR #6770](https://github.com/wikimedia/apps-android-wikipedia/pull/6770) | bugfix | `nan` → zh-min-nan. Ticket unchanged; **the PR has no test: hidden tests written here** (`hidden_tests: authored`) |

### Authored (ticket, fix and tests written for this benchmark; `drafted_by: agent`)

| Task | Category | Request | Look closely at |
|---|---|---|---|
| `antennapod-0010` | cross_module | `itunes:episodeType` (full/trailer/bonus): parse, store (DB migration), refresh | the FULL-by-default tests also pass for an enum without parsing — only the trailer/bonus/storage tests check the work |
| `antennapod-0011` | refactor | move tag-folder grouping out of `DBReader` into `NavDrawerData.groupFeedsByTag` / `buildTagList`, no behaviour change | the ticket spells out the two current behaviours in detail — is that too much of a hint, or necessary for "no behaviour change"? |
| `antennapod-0012` | feature | OPML folders ↔ tags (`OpmlElement.getTags()`), import and export | order rules (top-level first, folders A–Z) are tested; applying tags in the import screen is declared a follow-up |
| `wikipedia-0008` | cross_module | re-download saved articles whose offline copy is older than the current revision (`SavedPageRevisionChecker`) | the two wirings (record revision on save, check on page load) are **not** covered by tests — an agent could add the helpers only |
| `wikipedia-0009` | refactor | watchlist query parameters and badge count into `WatchlistFilterHelper` | exact strings per filter combination; the ticket gives the group order |
| `wikipedia-0010` | refactor | talk-page title conversion + toolbar markup into `TalkPageTitleHelper` (6 files) | exact HTML strings are tested; the ticket gives the format and worked examples |
| `wikipedia-0011` | feature | `ReadingListTitleValidator` (trim, blank, case/Unicode duplicates, `MAX_LENGTH`) | **`MAX_LENGTH = 255` is from memory of the ReadingLists schema** (not checked offline); tests use the constant, not the number |
| `wikipedia-0012` | feature | GeoHack `params` with signed decimals (`51.5072;-0.1276`), out-of-range → no location | range check is tested on the conversion result, not in the link handler |

### Single validation run (2026-10-18, environment `sha256:45f0558c…` AntennaPod / `sha256:55e53532…` Wikipedia)

All 19 new tasks: **V0 passes** (no P2P failure at base), **V1 fails** (the hidden tests fail at base;
for the 12 new-surface tasks they fail to compile, D-020), **V2 passes** (every F2P class passes with
the reference fix, no P2P regression). Two needed fixes first, both listed in their NOTES.md:
`wikipedia-0006` (tests use a field the fix adds — now named in the ticket, `new_surface: true`) and
`wikipedia-0007` (one assertion of the benchmark's own tests did not hold with the upstream fix —
removed). The 3× validation of all 25 tasks (S3) follows your approval.
