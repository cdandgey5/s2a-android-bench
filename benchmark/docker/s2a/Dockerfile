# abb-<repo>-s2a: thin layer that adds the S2A orchestrator on top of a repo image.
# Build (Phase 6): abb images build-s2a <repo>
#   docker build -f benchmark/docker/s2a/Dockerfile --build-arg BASE=abb-<repo>:<tag> -t abb-<repo>-s2a:<s2a_sha7> <repo root>
# Context = repository root; the root .dockerignore admits only s2a/ and benchmark/docker/.
ARG BASE=abb-antennapod:latest
FROM ${BASE}
COPY --chown=bench:bench s2a /opt/s2a
RUN uv tool install /opt/s2a && s2a --help >/dev/null
