# Stage: map (one-time per repository)

Produce a factual map of this repository for engineers who will change it without network
access. Facts only, each with a file path as evidence. Write two files:

`.s2a/map.md` (≤ 400 lines):
1. **Modules**: every Gradle project with one line on its purpose and its direct dependencies.
2. **Commands**: the exact commands to compile and to run the unit tests of one library module,
   of the app module (check product flavors in build files — task names differ), of one test
   class and of one test method. Run each once to prove it works and paste the last lines of
   output.
3. **Test infrastructure**: frameworks in use (JUnit 4/5, Robolectric and its SDK levels,
   MockK/Mockito, Compose test rule, screenshot tests), fixture and helper locations, naming
   conventions, where tests live for each module.
4. **Conventions** visible in the code: dependency injection, threading/async, persistence,
   navigation, UI toolkit, error handling, logging, string resources, feature flags.
5. **Central files**: the 15 classes/files most other code depends on (rank by how often they
   are imported or referenced — count with grep and show the counts), one line each.
6. **Pitfalls**: anything that bites offline builds or test runs (daemons, flavors, generated
   code, annotation processors, Robolectric downloads).

`.s2a/map.json` — discover the task names per module with `./gradlew <module>:tasks --all`
(look for `*UnitTest`, `compile*UnitTestSources` or `testClasses`, and `lint*`); never guess:
```json
{"modules": [{"path": ":playback", "dir": "playback", "kind": "library|app",
              "unit_test_task": "testDebugUnitTest", "compile_task": "compileDebugUnitTestSources", "lint_task": "lintDebug"},
             {"path": ":app", "dir": "app", "kind": "app",
              "unit_test_task": "testFreeDebugUnitTest", "compile_task": "compileFreeDebugUnitTestSources", "lint_task": "lintFreeDebug"}],
 "smoke": {"module": ":model", "task": "testDebugUnitTest"},
 "test_frameworks": ["junit4", "robolectric"],
 "generated_at_commit": "<git rev-parse HEAD>"}
```
(The orchestrator adds `lint_seconds` after timing the lint command itself.)

{{profile_notes}}
