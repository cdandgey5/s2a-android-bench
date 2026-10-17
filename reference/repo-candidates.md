# Repository candidates — facts gathered 2026-10-16

All facts below come from the repositories' GitHub pages on 2026-10-16 and must be re-verified
in Phase 0 step 7 (build experiment). "Not stated" means the page did not show it; discover it
in the experiment.

| Repo | URL | License | Default branch | Language | Structure | JDK | Notes |
|---|---|---|---|---|---|---|---|
| **AntennaPod** | https://github.com/AntennaPod/AntennaPod | GPL-3.0 | `develop` | Java (dominant), some Kotlin | multi-module: `app`, `app-wearos`, `event`, `model`, `net`, `parser`, `playback`, `storage`, `system`, `ui`; `store-metadata` is a submodule (not needed) | not stated (expect 17) | Has `playFlavor.gradle` → app module tests are `test<Flavor>DebugUnitTest`. Ships `CLAUDE.md` and `AGENTS.md` (keep; see D-004). ~352 open issues. Good "older Java/XML multi-module" candidate. |
| **Wikipedia Android** | https://github.com/wikimedia/apps-android-wikipedia | Apache-2.0 | `main` | Kotlin (+ Java topic tag) | single `app` module | not stated | `repo.keystore`/`repo.properties` present at root (check whether the build needs them; likely signing only). Expect several product flavors. Good "single-module Kotlin" candidate. |
| **Thunderbird for Android** (K-9) | https://github.com/thunderbird/thunderbird-android | Apache-2.0 | `main` | Kotlin | large multi-module: `app-k9mail`, `app-thunderbird`, `app-common`, `core`, `feature`, `legacy`, `library`, `mail`, `backend`, … | **21** (`.java-version`) | Modern Kotlin/Compose candidate. Risk: build time and memory. OAuth config is only needed for forks that ship; unit tests should not need it. ~1k open issues. |
| **NewPipe** | https://github.com/TeamNewPipe/NewPipe | GPL-3.0 | `dev` | Java + Kotlin | `app` + new KMP folders `shared`, `desktopApp`, `iosApp`; Gradle Kotlin DSL | not stated | KMP may complicate configuration (iOS targets). Try with `-Pkotlin.native.ignoreDisabledTargets=true`. ~1.4k open issues. 4th candidate. |
| Tusky | https://github.com/tuskyapp/Tusky | GPL-3.0 | `develop` | Kotlin | single `app` | — | **Archived on GitHub 2025-05-23, moved to Codeberg.** Issue mining harder; deprioritised. |
| Fossify apps | https://github.com/FossifyOrg | GPL-3.0 | — | Kotlin | small single-module apps | — | Likely too few unit tests; check one (e.g. Gallery/Calendar) only if a 5th repo is needed. |
| Pocket Casts Android | https://github.com/Automattic/pocket-casts-android | MPL-2.0 | — | Kotlin, Compose | multi-module | — | Not checked today; verify it builds without secrets before considering. |
| Now in Android | — | — | — | — | — | **Avoid**: too clean, widely memorised. |

## Recommended starting set

1. **AntennaPod** — repo #1 (Java/XML, multi-module, long issue history).
2. **Wikipedia Android** — repo #2 (Kotlin, single module, Apache-2.0).
3. **Thunderbird for Android** — repo #3 if the warm unit-test run is < 10 min like every
   other repo (Kotlin/Compose, multi-module; likely needs tasks scoped to a module subset).
4. **NewPipe** — repo #4 if KMP does not get in the way.

Phase 0 step 7 decides with measurements, not with this table.

## Windows notes (all candidates)

- Clone with `core.autocrlf=false` and `core.longpaths=true`; `abb repos check` fails a repo with two
  paths differing only by case or a path longer than 200 characters from the root.
- The Gradle wrapper is `gradlew.bat` from PowerShell and `./gradlew` from Git Bash; both ship
  with every candidate.
- Thunderbird's `mise.toml` is a developer convenience; the harness supplies JDK 21 itself.

## What to discover per repo in Phase 0

- Unit-test task names per module (`gradlew.bat tasks --all | Select-String UnitTest`).
- Which modules use Robolectric and which SDK levels (`@Config(sdk=…)`).
- Any required files (`google-services.json`, `secrets.properties`, keystores) and whether a
  stub is enough.
- Cold vs warm test wall time; peak memory.
- Number of unit tests; flakiness on two consecutive runs.
