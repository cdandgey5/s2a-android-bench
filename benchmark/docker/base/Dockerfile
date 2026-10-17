# syntax=docker/dockerfile:1.7
# abb-base: JDK + Android SDK + Claude Code + Spec Kit, non-root user `bench`.
# Build: abb images build-base --jdk 17   (or 21); build context = benchmark/docker/base/
# Re-verify CMDLINE_TOOLS_* on https://developer.android.com/studio before the first build.
# Phase 4 pins the resolved base digest (FROM eclipse-temurin:<JDK>-jdk-noble@sha256:...) and
# records it in images.lock.json.

ARG JDK=17
FROM eclipse-temurin:${JDK}-jdk-noble

ARG CMDLINE_TOOLS_ZIP=commandlinetools-linux-15859902_latest.zip
ARG CMDLINE_TOOLS_SHA256=4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583
ARG ANDROID_PLATFORM=android-35
ARG ANDROID_BUILD_TOOLS=35.0.0
# Pin both of these to exact versions before Phase 4 (Claude Code) and Phase 5 (Spec Kit) end.
ARG CLAUDE_CODE_VERSION=latest
ARG SPEC_KIT_REF=main

ENV DEBIAN_FRONTEND=noninteractive \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    GRADLE_USER_HOME=/home/bench/.gradle \
    PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/home/bench/.local/bin:$PATH \
    # Claude Code: never self-update (would silently move off the pinned version), and send no
    # telemetry/feature-flag/version-check traffic (the api-only proxy would block it anyway).
    DISABLE_AUTOUPDATER=1 \
    DISABLE_UPDATES=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1
# CLAUDE_CODE_VERSION must be >= 2.1.182 for these env vars (and PRINT_BG_WAIT_CEILING) to exist.

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

# Non-root user: Claude Code refuses --permission-mode bypassPermissions when running as root.
# ubuntu:24.04 (the temurin noble base) ships a default `ubuntu` user at uid 1000 -> remove it first,
# otherwise `useradd -u 1000` fails with "UID 1000 is not unique".
RUN userdel -r ubuntu 2>/dev/null || true \
    && useradd -m -u 1000 -s /bin/bash bench && chown -R bench:bench ${ANDROID_HOME}
USER bench
WORKDIR /home/bench

# Claude Code via the native installer (pin CLAUDE_CODE_VERSION; autoupdate is disabled above)
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_CODE_VERSION} \
    && claude --version

# uv + Spec Kit CLI (pin SPEC_KIT_REF to a tag); drop uv's git cache so no stray .git lives in the image
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@${SPEC_KIT_REF} \
    && specify --version \
    && uv cache clean

# The S2A orchestrator is NOT installed here: Phase 6 adds it as a thin layer per repo image
# (benchmark/docker/s2a/Dockerfile) so prompt tuning never rebuilds base or repo images.

# Model-switch guard. The certain guard is the driver's modelUsage assertion; this setting is kept
# only if the pinned Claude Code version documents it (Phase 0 step 5 checks and removes it otherwise).
# No fallbackModel and no ANTHROPIC_MODEL are ever set in this image.
RUN mkdir -p /home/bench/.claude \
    && printf '%s\n' '{ "switchModelsOnFlag": false }' > /home/bench/.claude/settings.json

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
