# Repo-selection experiment (Phase 0 step 6) — 2026-10-17

Script: `benchmark/scripts/try_build.py` (every process through the platform layer, 8 GB Job
Object, scratch `GRADLE_USER_HOME` and `JAVA_TOOL_OPTIONS=-Duser.home=<exp>\home` under
`C:\abb\work\experiments\<repo>`). Raw results: `C:\abb\work\experiments\<repo>\results.json` and
`logs\` (not in git). Host: Windows 11 Home 26200, i9-13900HX, 32 logical CPUs, 31.7 GiB, C: NTFS,
no Defender exclusion, no Dev Drive. Thunderbird and NewPipe are deferred to Phase 7 (plan).

"cold" = first run with an empty Gradle home (downloads + compile + test); "warm" = `--offline`,
`<m>:cleanTest <m>:<task>` (compile up to date); "warm-clean" = `--offline clean <m>:<task>`
(everything recompiled from a warm dependency cache — the closest Phase 0 figure to a fresh trial
workspace); "2 workers" = the same with an init script setting `maxParallelForks = 2` on every
`Test` task. Times are wall-clock of the whole `gradlew.bat --no-daemon` process.

## Results

| | AntennaPod | Wikipedia Android |
|---|---|---|
| URL / license | github.com/AntennaPod/AntennaPod, GPL-3.0 | github.com/wikimedia/apps-android-wikipedia, Apache-2.0 |
| Commit built (default branch) | `3d105d598dfa582c6cb22ba40b56d11780366890` (`develop`, committed 2026-10-11) | `0c7ee9b4682512217e01d829fb0b6d068d268724` (`main`) |
| JDK | **21** (`common.gradle` `sourceCompatibility VERSION_21`; CI `java-version: '21'`) — the seed config said 17 | 17 (`VERSION_17`/`JVM_17`; CI 17) |
| Gradle wrapper | 9.3.1 | 9.8.1 |
| compileSdk → SDK packages AGP resolved | 36 → `platforms;android-36`, `build-tools;36.0.0` | 37 → `platforms;android-37.0`, `build-tools;36.0.0` |
| LOC (Java + Kotlin, excl. build dirs) | 82,111 (Java 81,094, Kotlin 1,017); test LOC 8,498 | 133,297 (Kotlin); test LOC 6,392 |
| Modules with JVM unit tests | 17 (app, model, net/\*, parser/\*, playback/\*, storage/\*, ui/\*) | 2 (`:app`, `:analytics:testkitchen`) |
| Unit-test tasks | 118 (`test{Free,Play}{Debug,Release}UnitTest` on flavored modules, `testDebugUnitTest` elsewhere) | 12 (`test{Alpha,Beta,Custom,Dev,Fdroid,Prod}DebugUnitTest` × 2 modules) |
| Robolectric | 34 test files mention Robolectric; no `@Config(sdk=…)` | 27 test files; `robolectric.properties` `sdk=24` |
| Library module run | `:parser:feed:testDebugUnitTest`: 33 tests, 0 failures | `:analytics:testkitchen:testAlphaDebugUnitTest`: 24 tests, 0 failures |
| — cold / warm / warm-clean | 36 s ¹ / 22 s / 37 s | 111 s / 20 s / 53 s |
| — peak job memory (cold / warm / warm-clean) | 1868 / 1102 / 1930 MB | 2052 / 1014 / 2016 MB |
| App module run | `:app:testFreeDebugUnitTest`: 27 tests, 0 failures | `:app:testAlphaDebugUnitTest`: 343 tests, 0 failures |
| — cold / warm / warm-clean | 209 s / 41 s / 94 s | 490 s / 26 s / 279 s |
| — peak job memory (cold / warm / warm-clean) | 2467 / 1307 / 2436 MB | 5494 / 1032 / 5096 MB |
| — 2 workers: warm / warm-clean (peak) | 59 s (3109 MB) / 61 s (3162 MB) | 19 s (1112 MB) / 250 s (**6529 MB**) |
| `gradlew.bat tasks --all` (cold) | 102 s, 1631 MB | 89 s, 1480 MB |
| Offline after one warm run | yes (all warm runs `--offline`, 0 "Could not resolve") | yes |
| Secrets / stubs needed | none | none: `app/google-services.json`, `repo.keystore`, `repo.properties` are tracked upstream |
| Merged PRs matching `fixes OR closes OR resolves`, merged ≥ 2024-10-17 | ≥ 500 (the `--limit 500` cap) | 287 |
| Tracked files / longest path | 1,304 / 137 chars | 2,634 / 109 chars |
| Paths differing only by case | none | none |
| CI unit-test command | `./gradlew test${variant}UnitTest test${base-variant}UnitTest` (checks.yml) | `./gradlew … testAlphaDebugUnitTest` (android_pr.yml) |
| Ships agent instructions | `CLAUDE.md`, `AGENTS.md` (kept, D-004) | `CLAUDE.md`, `AGENTS.md` (kept, D-004) |

¹ The first `:parser:feed` cold attempt failed in 48 s: AGP's on-the-fly install of
`build-tools;36.0.0` collided with the Wikipedia run that was installing the same package into
the shared SDK at the same moment (`"Install Android SDK Build-Tools 36 v.36.0.0" failed`). The
36 s figure is the re-run after the AntennaPod app run had populated the Gradle home, so it is not
a true cold time. Consequence: the SDK packages each repo needs are now pinned in
`config/toolchain.yaml` and installed by `abb tools install`; no build may install SDK packages
(the sandbox user cannot write `tools/` anyway).

Disk after the experiment: `C:\abb\tools` 2.6 GB, `caches` (two bare mirrors) 0.6 GB,
experiments 1.4 GB (AntennaPod) + 2.4 GB (Wikipedia); C: 78.3 GB free.

## Criteria

| Criterion | AntennaPod | Wikipedia |
|---|---|---|
| Builds without secrets | yes | yes |
| Unit tests pass offline after one warm run | yes | yes |
| Warm test run < 10 min (worst case: recompile from a warm cache) | yes (94 s) | yes (279 s) |
| Robolectric or plain JUnit tests across several modules | yes (17 modules) | 2 modules — accepted: it is the single-app-module candidate by design |
| ~20k–150k LOC | 82k | 133k |
| ≥ 100 linked merged PRs | yes (≥ 500) | yes (287) |
| No two paths differing only by case | yes | yes |
| Longest path < 200 chars | 137 | 109 |

## Decision

**Repo #1: AntennaPod** (Java/XML, multi-module, JDK 21). **Repo #2: Wikipedia Android**
(Kotlin, XML + Compose, one app module + one small library, JDK 17). Both meet every criterion;
no LOC deviation (D-003). Their configs are filled in `benchmark/repos/{antennapod,wikipedia}.yaml`
and pass `abb repos check`.

Memory: the largest peak (Wikipedia `:app` recompile with 2 test workers, 6.5 GB) plus
`claude.exe` (~420 MB in the smoke tests) leaves < 1.3 GB under the planned 8 GB job limit, so
`sandbox.yaml: process.memory_mb` is 10240 (D-034); 2 parallel trials stay within 32 GB.
