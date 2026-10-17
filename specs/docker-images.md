# Spec: Docker images

Two layers. `abb-base` is shared; `abb-<repo>` adds the repo snapshot and a warm cache.

## `abb-base` (`benchmark/docker/base/Dockerfile`)

Contents:

| Component | Version policy | Why |
|---|---|---|
| Ubuntu 24.04 (via `eclipse-temurin:<JDK>-jdk-noble`) | tag now; the resolved digest is recorded in `images.lock.json` in Phase 0 and pinned in the `FROM` line in Phase 4 | reproducible |
| JDK | build-arg `JDK=17` or `21` → `eclipse-temurin:<JDK>-jdk` packages, or install both and select with `JAVA_HOME` per repo | AntennaPod/Wikipedia: 17 (verify), Thunderbird: 21 (`.java-version`) |
| Android cmdline-tools | `commandlinetools-linux-15859902_latest.zip`, sha256 `4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583` (as of 2026-10-16; re-verify) | `sdkmanager` for platforms/build-tools |
| git, curl, unzip, python3, ripgrep, jq | distro | agent tooling |
| Claude Code | native installer pinned: `curl -fsSL https://claude.ai/install.sh \| bash -s <version>` → `~/.local/bin/claude`; image env `DISABLE_AUTOUPDATER=1 DISABLE_UPDATES=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` so it never updates itself or phones home | all arms |
| `uv` + Spec Kit CLI | `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@<tag>` | arm B |
| S2A orchestrator | **Not in the base image.** Installed as a thin layer `abb-<repo>-s2a:<s2a_sha7>` built `FROM abb-<repo>` (`benchmark/docker/s2a/Dockerfile`, Phase 6), so prompt tuning rebuilds in seconds and never changes the `abb-<repo>` digest tasks were validated against; `s2a_git_sha` goes into `images.lock.json` and the run manifest | arm C |
| non-root user `bench` (uid 1000) | required; the noble base ships a default `ubuntu` user at uid 1000 which is removed first (`userdel -r ubuntu`) | Claude Code refuses `bypassPermissions` as root |
| `cloc` | distro | LOC counts in the repo experiment |

Reference Dockerfile (seed file in `benchmark/docker/base/Dockerfile`):

```dockerfile
# syntax=docker/dockerfile:1.7
ARG JDK=17
FROM eclipse-temurin:${JDK}-jdk-noble

ARG CMDLINE_TOOLS_ZIP=commandlinetools-linux-15859902_latest.zip
ARG CMDLINE_TOOLS_SHA256=4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583
ARG ANDROID_PLATFORM=android-35
ARG ANDROID_BUILD_TOOLS=35.0.0
ARG CLAUDE_CODE_VERSION=latest          # pin to an exact version before Phase 4 ends
ARG SPEC_KIT_REF=main                   # pin to a tag before Phase 5 ends

ENV DEBIAN_FRONTEND=noninteractive \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    GRADLE_USER_HOME=/home/bench/.gradle \
    PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/home/bench/.local/bin:$PATH \
    DISABLE_AUTOUPDATER=1 DISABLE_UPDATES=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates unzip zip jq ripgrep python3 python3-venv tini cloc \
    && rm -rf /var/lib/apt/lists/*

# Android SDK command-line tools (pinned + checksummed)
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools && cd /tmp \
    && curl -fsSLo cmdline-tools.zip https://dl.google.com/android/repository/${CMDLINE_TOOLS_ZIP} \
    && echo "${CMDLINE_TOOLS_SHA256}  cmdline-tools.zip" | sha256sum -c - \
    && unzip -q cmdline-tools.zip -d ${ANDROID_HOME}/cmdline-tools \
    && mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
    && rm cmdline-tools.zip \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager "platform-tools" "platforms;${ANDROID_PLATFORM}" "build-tools;${ANDROID_BUILD_TOOLS}"

# Non-root user: Claude Code refuses bypassPermissions when running as root. The noble base
# ships a default `ubuntu` user at uid 1000 -> remove it or useradd fails ("UID 1000 is not unique").
RUN userdel -r ubuntu 2>/dev/null || true \
    && useradd -m -u 1000 -s /bin/bash bench && chown -R bench:bench ${ANDROID_HOME}
USER bench
WORKDIR /home/bench

# Claude Code (native installer; pin the version)
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_CODE_VERSION} \
    && claude --version

# uv + Spec Kit CLI (then drop uv's git cache so no stray .git lives in the image)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@${SPEC_KIT_REF} \
    && specify --version \
    && uv cache clean

# Pinned-model safety: never let a safety-flag fallback switch models silently.
RUN mkdir -p /home/bench/.claude && printf '%s\n' '{ "switchModelsOnFlag": false }' > /home/bench/.claude/settings.json

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
```

Build: `abb images build-base --jdk 17` and `--jdk 21` → tags `abb-base:jdk17`, `abb-base:jdk21`
(build context `benchmark/docker/base/`).

## `abb-<repo>-s2a` (`benchmark/docker/s2a/Dockerfile`, Phase 6)

```dockerfile
ARG BASE=abb-antennapod:latest        # abb images build-s2a passes the exact tag, e.g. abb-antennapod:20261101-3f2a9c1
FROM ${BASE}
COPY --chown=bench:bench s2a /opt/s2a
RUN uv tool install /opt/s2a && s2a --help >/dev/null
```

`abb images build-s2a <repo>` builds it with the **repository root** as context (the root
`.dockerignore` admits only `s2a/` and `benchmark/docker/`), tags it
`abb-<repo>-s2a:<s2a_sha7>`, and records the parent digest + `s2a_git_sha` in
`images.lock.json`. Only the `s2a-*` arms run in this image; the drift guard checks the parent.

## `abb-<repo>` (`benchmark/docker/<repo>/Dockerfile`, generated from `repos/<repo>.yaml`)

```dockerfile
ARG JDK=17
FROM abb-base:jdk${JDK}
ARG REPO_URL
ARG CACHE_COMMIT
ARG WARM_COMMITS=""         # space-separated task base commits (Phase 1 step 5)

# Full clone kept OUTSIDE the workspace path; used only by the harness to cut snapshots and
# DELETED from agent containers at snapshot time (see "Workspace creation" below).
RUN git clone --quiet ${REPO_URL} /home/bench/upstream \
    && cd /home/bench/upstream && git checkout --quiet ${CACHE_COMMIT}

# Gradle settings that cap memory and keep builds quiet
COPY --chown=bench:bench gradle.properties.append /tmp/gp
RUN mkdir -p ${GRADLE_USER_HOME} && cat /tmp/gp >> ${GRADLE_USER_HOME}/gradle.properties

# Secret stubs (only if repos/<repo>.yaml lists any)
# COPY --chown=bench:bench stubs/ /home/bench/upstream/

# Warm the cache at the cache commit, then at every task base commit
COPY --chown=bench:bench warm.sh /home/bench/warm.sh
RUN bash /home/bench/warm.sh /home/bench/upstream "${CACHE_COMMIT}" ${WARM_COMMITS}
```

`warm.sh` (generated): first `git fetch --all --quiet` (the clone layer is cached by Docker,
so base commits newer than the first build would otherwise be missing); then for each commit,
`git checkout -q <commit>`, apply stubs, run every
entry of `build.warm_commands` in order. An entry with `allow_failure: true` (use it for the
test-running commands, whose test *failures* are irrelevant while warming) runs as
`cmd || true`; every other entry must exit 0 or the image build fails — so compile errors fail
the build as long as the assemble/compile command is not marked `allow_failure`. Finally
`./gradlew --stop`. Expect 10–30 min per repo image.

## Workspace creation (Phase 1, `abb/harness/workspace.py`)

For a task, the harness starts a container from `abb-<repo>:<tag>` and runs:

```bash
set -e
rm -rf /work && mkdir /work
cd /home/bench/upstream
git archive --format=tar <base_commit> | tar -x -C /work     # files only, no history
cd /work
# apply stubs, strip excludes (repos.workspace.exclude_from_snapshot)
# Remove repo-shipped agent AUTOMATION (hooks, MCP servers, settings) - without --bare, `claude -p`
# would run them inside every arm. Repo-shipped INSTRUCTIONS (CLAUDE.md, AGENTS.md) stay (D-004).
rm -rf .claude/settings.json .claude/settings.local.json .claude/hooks .mcp.json
git init -q && git add -A && git -c user.name=bench -c user.email=bench@local commit -qm "base"
git tag base
# Remove Gradle daemon logs (they name files compiled at later commits). The build cache is never
# enabled (org.gradle.caching=false), so there is no build-cache-1 to keep; remove it if present.
rm -rf /home/bench/.gradle/daemon/*/*.log /home/bench/.gradle/caches/build-cache-1
# Remove the full clone from THIS container so the agent cannot read any fix commit.
# The agent runs as `bench` and owns that directory, so file permissions would not protect it.
# Overlay whiteout is cheap; grading/validation containers are fresh from the image and still have it.
rm -rf /home/bench/upstream
```

Guarantees: `/work/.git` has exactly one commit, no remotes, no reflog of upstream, and
`/home/bench/upstream` no longer exists in the agent's container (the only `.git` under `/` is
`/work/.git`), so neither `git log --all` nor `find / -name .git` can leak the fix. Phase 1's
invariants test checks all of this. The harness records `git rev-parse HEAD` of `/work` in
`run.json` as `workspace_base`.

## Container run flags (used by every phase)

```
# detached: the harness talks to the container with `docker exec` (no TTY)
docker run --rm -d \
  --name abb-<run_id>-<arm>-<task>-t<k> \
  --memory 8g --memory-swap 8g --cpus 4 \
  --network <net> \                      # see below
  -e ANTHROPIC_API_KEY \                 # from host env, never baked
  -e CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=60000 \
  abb-<repo>:<tag>
```

**Nothing is bind-mounted into an agent container** — not the results root, not the task
directory. Inputs go in with `docker cp` (`Workspace.put`); outputs come out with
`Workspace.get`. Phase 1's invariants test asserts `/results` does not exist.

Network policy (`config/network.yaml`):

| Mode | Used for | How |
|---|---|---|
| `none` | validation, grading, image gate | `--network none` |
| `api-only` | agent runs (every arm) | `docker network create --internal abb-agent` (no external route). A proxy sidecar `abb-proxy` (built from `docker/proxy/`, seed provided: tinyproxy with `FilterDefaultDeny Yes`, `FilterType ere`, allow file `^api\.anthropic\.com$`, `ConnectPort 443`, and **no `Allow`/`Deny` lines** — the stock conf's `Allow 127.0.0.1` would reject every container) is attached to **both** `abb-agent` and the default bridge. Agent containers join `abb-agent` only, with `HTTPS_PROXY=http://abb-proxy:8888` (Claude Code honours the proxy env vars). Claude Code additionally gets `--disallowedTools WebFetch,WebSearch`. |
| `open` | image builds only | default bridge |

`api-only` is a **Phase 1 deliverable, not a stretch goal** (D-009): the agent has Bash, so a
tool deny list alone cannot stop `git clone https://github.com/...` or `curl` of the fix PR,
and Gradle run without `--offline` would pull dependencies the offline grader cannot resolve.
Phase 1's gate proves it: inside an agent workspace `curl -sS --max-time 5 https://github.com`
must fail while the Claude smoke test succeeds. Record the mode in the manifest.

## Image tags and digests

Images are tagged `abb-<repo>:<yyyymmdd>-<short-cache-commit>`. `abb images build` writes
`benchmark/images.lock.json` with the digest per tag. Tasks record the digest they were validated
against; `abb run` refuses to run a task against a different digest unless `--allow-image-drift`.
