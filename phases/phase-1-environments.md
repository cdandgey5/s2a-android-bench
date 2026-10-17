# Phase 1 — Per-repo environments

**Goal.** For each chosen repo, an image with a warm Gradle cache that runs unit tests
**offline**, the `api-only` network that every agent run uses, and the workspace abstraction
every later phase builds on.

**Prerequisites.** Phase 0 gate. `repos/<repo>.yaml` filled for repo #1 and #2; seed task
`antennapod-0000`.

**Effort.** ~1 week part-time (image builds are slow; iterate on one repo first).

## Deliverables

```
benchmark/abb/harness/images.py       # + render docker/<repo>/{Dockerfile,warm.sh,gradle.properties.append}; build; lock file; prune
benchmark/abb/harness/workspace.py    # Workspace: container lifecycle, snapshot, exec, copy, diff
benchmark/abb/harness/gradle.py       # compose + run Gradle test commands with timeout and log capture
benchmark/abb/harness/junit.py        # JUnit XML -> {test_id: status}
benchmark/abb/harness/network.py      # ensure `abb-agent` internal network + `abb-proxy` sidecar exist; mode -> docker args/env
benchmark/docker/<repo>/              # generated (committed) for each repo
benchmark/docker/proxy/Dockerfile     # tinyproxy allow-list sidecar (api.anthropic.com only)
benchmark/docker/proxy/tinyproxy.conf # seed provided: FilterDefaultDeny Yes; FilterType ere; Filter /etc/tinyproxy/allow; ConnectPort 443; NO Allow/Deny lines
benchmark/docker/proxy/allow          # ^api\.anthropic\.com$
benchmark/images.lock.json            # tag -> digest, build date, cache_commit, warm_commits, base_digests
benchmark/tests/test_junit.py         # fixtures: passed/failed/error/skipped/parameterized XML
benchmark/tests/test_workspace.py     # integration test (skipped unless ABB_INTEGRATION=1)
CLI: abb images build <repo> [--warm-commits ...]   abb images verify <repo> [--network api-only]   abb images prune   abb ws shell <repo> [--commit]
```

## Steps

1. **Render per-repo Docker context** from `repos/<repo>.yaml` per `specs/docker-images.md`:
   `Dockerfile`, `warm.sh` (first `git fetch --all --quiet`; then for each commit in
   `CACHE_COMMIT` + `WARM_COMMITS`: `git checkout -q`, apply stubs, run each `warm_commands`
   entry — as `cmd || true` when `allow_failure: true`, otherwise a non-zero exit fails the
   image build — and finally `./gradlew --stop`), `gradle.properties.append` (from
   `toolchain.gradle_user_home_props`, which sets `org.gradle.caching=false`: a build cache
   would carry compiled classes of later commits into every workspace). Commit the rendered
   files so the images are reproducible from git.
2. **Build** `abb images build antennapod` → tag `abb-antennapod:<yyyymmdd>-<cache7>`; stream
   logs; on success write `images.lock.json` entry with the digest. Expect 10–30 min.
3. **Workspace class** (`workspace.py`):
   ```python
   class Workspace:
       def __init__(self, repo: RepoConfig, image: str, network: str, name: str, mem_gb=8, cpus=4): ...
       def __enter__(self): start container (tini, sleep infinity), return self
       def snapshot(self, base_commit: str) -> str: run the snapshot script from specs/docker-images.md; return HEAD sha
       def exec(self, argv: list[str], *, cwd="/work", timeout_s: int, env: dict|None=None, stream_to: Path|None=None) -> ExecResult(exit_code, stdout_path, duration_s)
       def put(self, src: Path, dst: str); def get(self, src: str, dst: Path)   # docker cp; NOTHING is bind-mounted into agent containers
       def apply_patch(self, patch: Path, *, check_only=False) -> bool
       def diff(self, exclude: list[str]) -> str   # `git add -A -N && git diff --binary base -- . ':(exclude)…'`
       def changed_paths(self) -> list[str]
       def __exit__(...): stop + remove container; never leave containers behind (also on KeyboardInterrupt)
   ```
   Use the Docker SDK (`containers.run(detach=True)`, `exec_run(stream=True, demux=True)`).
   Enforce `--memory`, `--memory-swap`, `--cpus`, network and env from `config/network.yaml`.
   The `exec` timeout uses `timeout -s INT -k 30` semantics (exit 124/137 → timeout).
4. **Gradle runner** (`gradle.py`): `test_command(repo, module, tests: list[str]) -> list[str]`
   per `specs/task-format.md`; `run_tests(ws, repo, selections, timeout_s) -> (exit_code,
   log_path)`; `collect_junit(ws, repo, module) -> dict`. Always pass `--offline
   --console=plain --continue`; validation and grading add `--no-build-cache` and
   `<module>:cleanTest`. Kill the container on timeout (do not try to kill Gradle politely).
5. **Warm for task commits.** `abb images build <repo> --warm-commits a1b2c3 d4e5f6` re-renders
   with `WARM_COMMITS` so every task's base commit resolves offline. Phase 2 step 7 adds
   `setup_commit`; Phase 7 reruns this once the task list is final.
6. **Offline verification** `abb images verify <repo>`: start a workspace with `--network
   none`, snapshot at `cache_commit`, run `tests.test_task_for_module` for each module in
   `tests.verify_modules` (one library module, the app module), parse JUnit, print counts and
   wall time. Fails if Gradle tries to resolve anything (`Could not resolve` / `No cached
   version` in the log) or if Robolectric tries to download (`Downloading:` / `android-all`).
   Then run the seed task `antennapod-0000`'s hidden test at its base commit (it must fail)
   and with `gold.patch` (it must pass) — the first use of the test-command path end to end.
7. **Workspace invariants test** (`test_workspace.py`, integration): after `snapshot()`:
   `git -C /work log --all --oneline | wc -l` is 1; `git -C /work remote -v` prints nothing;
   `test ! -e /home/bench/upstream`; `test ! -e /results`; `find / -name .git -not -path
   /work/.git -not -path '/home/bench/.cache/*' 2>/dev/null` prints nothing; `~/.gradle` has no
   `caches/build-cache-1` and no `daemon/*/*.log`; `/work/.claude/settings.json`,
   `/work/.claude/hooks`, `/work/.mcp.json` do not exist while `/work/CLAUDE.md` (if the repo
   ships one) does; and a grep of `~/.gradle` and `~/.m2` for every class name added by any
   task's `gold.patch` (`abb tasks lint --setup-leak --gradle-home`, seeded with
   `antennapod-0000`) finds nothing.
8. **Debug helper** `abb ws shell <repo> [--commit]`: opens an interactive shell in a fresh
   workspace. You will use this constantly.
9. **`api-only` network** (`network.py`, `docker/proxy/`): `docker network create --internal
   abb-agent`; build and start `abb-proxy` (tinyproxy with the seed conf: `FilterDefaultDeny
   Yes`, `FilterType ere`, allow file `^api\.anthropic\.com$`, `ConnectPort 443`, **no
   `Allow`/`Deny` lines** — the stock conf's `Allow 127.0.0.1` would reject every container)
   attached to both `abb-agent` and the default bridge; agent workspaces join `abb-agent` only,
   with `HTTPS_PROXY`/`HTTP_PROXY` and `CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1` set (the internal
   network has no DNS route out, so the proxy must resolve the API host). Check from inside a
   workspace, in this order so a DNS failure is not misread as a filter failure: `curl -sS
   --max-time 10 -x http://abb-proxy:8888 https://api.anthropic.com/v1/models` returns an HTTP
   status (401 without a key is fine); `curl -sS --max-time 5 https://github.com` fails; `git
   clone https://github.com/AntennaPod/AntennaPod` fails; the Phase 0 Claude smoke test
   (through the proxy) succeeds without retries (`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`
   is set in the image). Add these checks to
   `abb images verify --network api-only`. A dev-only `--network open` escape hatch exists for
   debugging; it is recorded in the manifest and refused for `--tasks test`.
10. **Prune.** `abb images prune` removes untagged/old `abb-*` tags and runs `docker builder
    prune -f`; print `docker system df` before and after.
11. Repeat 1–6 for repo #2. Commit `phase 1: environments`.

## Acceptance gate

```
uv run abb images verify antennapod      # prints: tests run/passed, wall time < 10 min, "offline: OK", seed task fail→pass
uv run abb images verify wikipedia       # same (seed task step skipped)
uv run abb images verify antennapod --network api-only   # github.com unreachable, git clone fails, Claude smoke test OK
ABB_INTEGRATION=1 uv run pytest -q tests/test_workspace.py tests/test_junit.py
cat benchmark/images.lock.json
```

Passes when both repos' unit tests run offline from a history-free workspace in under 10
minutes, the invariants test is green (no upstream clone, no `/results`, no build cache, no
gold-added classes in the Gradle home), and the proxy blocks everything but the API.

## Pitfalls

- Robolectric downloads `android-all-instrumented-<api>` jars at first test run into
  `~/.m2/repository`. The warm step must *run* tests, not just compile them, for every API
  level the repo's tests use (`@Config(sdk = …)` variations); warm serially (parallel first
  downloads race). Grep the warm log for `android-all` downloads and add explicit test runs
  for modules that use other SDK levels.
- `git archive` ignores files matched by `export-ignore` in `.gitattributes`; check nothing
  needed for the build is excluded.
- Layer size: `/home/bench/.gradle` can reach 5–10 GB. That's fine; keep one image per repo
  and prune old tags.
- Kotlin daemon memory: set `kotlin.daemon.jvmargs` (already in `gradle_user_home_props`).
