# Spec: Repository configuration (`benchmark/repos/<repo>.yaml`)

One file per benchmark repository. Everything the harness needs to build an image, create a
workspace, run tests and scope diffs.

```yaml
key: antennapod                         # used in task ids, image names (abb-antennapod)
display_name: AntennaPod
url: https://github.com/AntennaPod/AntennaPod
license: GPL-3.0
default_branch: develop
language: java                          # java | kotlin | mixed  (dominant language)
ui: xml                                 # xml | compose | mixed
structure: multi_module                 # single_module | multi_module

toolchain:
  jdk: 17                               # major version; image picks eclipse-temurin:<jdk>-jdk
  android:
    cmdline_tools_zip: commandlinetools-linux-15859902_latest.zip
    cmdline_tools_sha256: 4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583
    packages:                           # sdkmanager packages, pinned; discovered in Phase 0
      - "platform-tools"
      - "platforms;android-35"
      - "build-tools;35.0.0"
  gradle_user_home_props: |             # appended to $GRADLE_USER_HOME/gradle.properties
    org.gradle.jvmargs=-Xmx3g -XX:MaxMetaspaceSize=1g
    kotlin.daemon.jvmargs=-Xmx2g
    org.gradle.parallel=false
    org.gradle.caching=false            # a build cache would carry compiled classes of later commits into workspaces
    org.gradle.configuration-cache=false

build:
  # Commands run during image build to warm the cache (network ON). Run at `cache_commit`,
  # then again at every task base_commit for this repo (Phase 1, step 5).
  cache_commit: 3f2a9c1d...             # a recent commit that all tasks' deps are close to
  # Commit at which one-time per-repo setup artifacts (Spec Kit constitution, S2A map) are
  # generated. Defined as `git merge-base --octopus <all task base_commits of this repo>`, i.e.
  # an ancestor of every task's base, so the artifacts cannot describe code that only exists
  # because of a task's fix. Set by `abb tasks coverage` (Phase 7), which also adds it to the
  # warm commits; until then = merge-base of the dev-task base commits.
  setup_commit: 1a2b3c4d...
  warm_commands:
    - cmd: "./gradlew --console=plain assembleFreeDebug"        # discovered in Phase 0; must exit 0
    - cmd: "./gradlew --console=plain testFreeDebugUnitTest"    # also fetches Robolectric jars
      allow_failure: true                                       # test failures are irrelevant while warming
  # Secrets stubbing: files to create so the build does not need real keys.
  stubs:
    - path: "app/google-services.json"
      content_from: "docker/antennapod/stubs/google-services.json"   # only if needed
  env:                                  # extra env for Gradle inside the container
    JAVA_TOOL_OPTIONS: "-Dfile.encoding=UTF-8"

tests:
  test_task_for_module:                 # Gradle unit-test task per module (flavors differ!)
    default: "testDebugUnitTest"
    ":app": "testFreeDebugUnitTest"
  junit_dir: "build/test-results"       # relative to module dir; task name is appended
  verify_modules: [":model", ":app"]    # `abb images verify` runs these (one library module + the app module)
  test_dirs:                            # globs; edits here are REVERTED before grading
    - "**/src/test/**"
    - "**/src/testDebug/**"
    - "**/src/testFree/**"
    - "**/src/androidTest/**"
    - "**/src/sharedTest/**"
    - "**/src/screenshotTest/**"
    - "**/src/testFixtures/**"
  protected_build_paths:                # restored from base at grading unless gold.patch touches the file
    - "gradlew"
    - "gradlew.bat"
    - "gradle/**"
    - "buildSrc/**"
    - "build-logic/**"
    - "**/*.init.gradle*"
  build_config_files:                   # also restored unless gold touches them; the test_config_suspect scan applies to survivors
    - "**/build.gradle"
    - "**/build.gradle.kts"
    - "settings.gradle"
    - "settings.gradle.kts"
    - "gradle.properties"
    - "gradle/libs.versions.toml"

workspace:
  exclude_from_snapshot:                # not copied into the task workspace
    - ".git"
    - ".github"
    - "store-metadata"                  # submodule; not needed to build
  # Repo-provided agent instructions. Decision: KEEP them (they are part of the brownfield
  # repo and every arm sees them). Set to true only to strip them for a controlled experiment.
  strip_agent_instructions: false       # CLAUDE.md, AGENTS.md, .cursorrules, .github/copilot-instructions.md
  diff_exclude:                         # never part of the graded diff
    - ".claude/**"
    - ".specify/**"
    - "specs/**"
    - ".s2a/**"
    - "CLAUDE.md"                       # Spec Kit's plan step rewrites agent-context files;
    - "AGENTS.md"                       # no task ever requires editing them
    - "**/build/**"
    - ".gradle/**"
    - ".idea/**"
    - "*.log"

lint:                                   # optional secondary metric (Phase 3 step 7)
  command: "./gradlew --offline --console=plain :app:lintFreeDebug"
  report_glob: "app/build/reports/lint-results-*.xml"
```

## Notes

- `warm_commands` entries are `{cmd, allow_failure?}`. Only test-running commands should carry
  `allow_failure: true`; a failing assemble/compile command must fail the image build.
- `warm_commands` must fetch everything the agent or grader will later need offline, including
  Robolectric's `android-all-instrumented` jars (they are downloaded on first test run into
  `~/.m2/repository/org/robolectric/`). The Phase 1 gate checks this by running the tests with
  `--network none`.
- `test_task_for_module` exists because app modules with product flavors use
  `test<Flavor>DebugUnitTest` while library modules use `testDebugUnitTest`. Discover with
  `./gradlew :app:tasks --all | grep -i unittest`.
- `strip_agent_instructions` — AntennaPod ships `CLAUDE.md` and `AGENTS.md`. Keeping them is the
  realistic brownfield condition and is identical across arms. Record the choice in the run
  manifest. Independently of this flag, the snapshot script always removes repo-shipped agent
  *automation* (`.claude/settings*.json`, `.claude/hooks/`, `.mcp.json`), because `claude -p`
  without `--bare` would execute hooks and connect MCP servers inside every arm.
- Keep this file the only place with repo-specific knowledge; tasks and arms must not hard-code
  module names or task names.
