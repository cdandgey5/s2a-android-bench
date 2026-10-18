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
