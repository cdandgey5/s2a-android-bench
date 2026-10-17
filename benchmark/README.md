# abb — Android Brownfield Bench (harness)

Windows-native harness for the brownfield Android agent benchmark (`../PLAN.md`). Python 3.12 via
`uv`; every process (Gradle, git, `claude.exe`) starts through the platform layer in
`abb/harness/platform/` (`../specs/platform-layer.md`). No WSL, no Docker, no API key.

```powershell
cd benchmark
uv sync                       # dev venv (uv-managed CPython 3.12; never the Store Python)
uv run abb --help
uv run abb tools install      # pinned JDK 17/21, Android SDK, CPython, pwsh, claude.exe copy, specify -> ABB_HOME\tools
uv run abb tools check        # re-verify against config/toolchain.lock.yaml
uv run abb auth check         # claude.exe auth status with the mapped subscription token -> oauth_token
uv run abb ws smoke "Print the current directory and exit."   # headless smoke test through the launcher
uv run abb repos check antennapod
uv run pytest -q
```

Configuration lives in `config/` (`limits.yaml`, `sandbox.yaml`, `toolchain.yaml` + the generated
`toolchain.lock.yaml`), `repos/<repo>.yaml` and `tasks/<id>/`. All config paths are relative to
this directory. Data lives under `ABB_HOME` (default `C:\abb`) and `ABB_RESULTS_DIR`.

Secrets: the subscription token is read from the user environment variable `ABB_OAUTH_TOKEN` (or
the git-ignored `.env`, see `.env.example`) and reaches `claude.exe` only through the per-run
environment block, as `CLAUDE_CODE_OAUTH_TOKEN`. Never set that name, or `ANTHROPIC_API_KEY`,
globally: the harness refuses to start if its own environment has either.

Status by phase: `../README.md`. Licence: MIT (`LICENSE`); task patches derived from upstream
repositories carry their upstream licence (`tasks/<id>/LICENSE-NOTE.md`).
