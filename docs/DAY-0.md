# Day 0 — human bootstrap (about two hours, once)

Everything below is done by you, not by the agent, because it needs admin rights, accounts, or
a WSL restart that would kill the agent's own shell. When it is done, open Claude Code inside
WSL at `~/abb` and paste the kickoff prompt from `START-HERE.md`.

## 1. Windows side

1. **WSL2 + Ubuntu.** `wsl --install -d Ubuntu-24.04` (or confirm an existing distro:
   `wsl -l -v` shows `VERSION 2`).
2. **Docker Desktop** with the WSL2 backend **and** *Settings → Resources → WSL integration →
   enable for your Ubuntu distro* (the backend alone is not enough; `docker` must work inside
   the distro).
3. **`%USERPROFILE%\.wslconfig`** (create if missing):
   ```
   [wsl2]
   memory=24GB
   processors=8
   swap=8GB
   ```
   Then `wsl --shutdown` and restart Docker Desktop.
4. **Disk.** Two sparse disks grow on the Windows drive: the Ubuntu vhdx
   (`%LOCALAPPDATA%\Packages\CanonicalGroupLimited...\LocalState\ext4.vhdx`) and Docker
   Desktop's data vhdx (`%LOCALAPPDATA%\Docker\wsl\...\ext4.vhdx`). Together they need
   **≥ 120 GB free on that Windows drive** (base images ~4 GB each, repo images 5–10 GB each,
   several tags, clones, results). Check the drive in Explorer — `df -h ~` inside WSL shows the
   vhdx's virtual size (1 TB) and proves nothing. Free space or move the vhdx first.

## 2. Inside WSL (Ubuntu shell)

```bash
sudo apt-get update && sudo apt-get install -y git curl jq unzip build-essential
curl -LsSf https://astral.sh/uv/install.sh | sh            # uv
curl -fsSL https://claude.ai/install.sh | bash             # Claude Code (native installer)
type -p gh >/dev/null || (sudo mkdir -p -m 755 /etc/apt/keyrings \
  && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null \
  && sudo apt-get update && sudo apt-get install -y gh)
gh auth login                                              # browser flow; needs repo scope
source ~/.profile                                          # ~/.local/bin (uv, claude) is on PATH only in a new login shell
uv --version && claude --version && gh --version
docker info | grep -iE 'operating system|total memory|cpus'   # must work without sudo; >= 20 GB, >= 6 CPUs
df -h /mnt/c                                               # the Windows drive: >= 120 GB free (df -h ~ is meaningless here)
docker system df                                           # baseline before any image exists
```

## 3. Keys and budget

- A **Console API key** with credit (a Claude subscription login does not work via
  `-e ANTHROPIC_API_KEY` inside containers). Put it in `~/.bashrc`:
  `export ANTHROPIC_API_KEY=sk-ant-...` — never in the repo.
- Set a **spend alert** in the Console (weeks 1–3 should cost tens of dollars; agent runs start
  in Phase 4).
- Confirm both pinned ids exist (the endpoint pages at 20 by default, so ask for 1000):
  ```bash
  source ~/.bashrc
  curl -s 'https://api.anthropic.com/v1/models?limit=1000' -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" | jq -r '.data[].id' | grep -E '^claude-(opus|sonnet)-5-5$'
  ```
  Both lines must print; otherwise pick the current ids and write them into D-001 and
  `benchmark/config/limits.yaml`.
- Decide the **dev budget per trial** (`benchmark/config/limits.yaml: profiles.dev.max_usd`,
  default 5.0) and the total you are willing to spend before the first results table.

## 4. The working clone

The OneDrive folder is already a git repository (commit "plan: initial import", 2026-10-17),
so clone it rather than copying it:

```bash
git clone /mnt/c/Users/<you>/OneDrive/Documents/Claude/S2AFramework ~/abb   # one-time import
cd ~/abb
git remote remove origin                     # drop the OneDrive path; GitHub becomes origin
gh repo create <your-github-user>/s2a-android-bench --private --source . --push
mkdir -p ~/abb-results && echo 'export ABB_RESULTS_DIR=$HOME/abb-results' >> ~/.bashrc
```

If the clone stops with "detected dubious ownership", run
`git config --global --add safe.directory /mnt/c/Users/<you>/OneDrive/Documents/Claude/S2AFramework`
and clone again.

From now on **`~/abb` is the working tree**; the OneDrive folder is the original import. Do not
push into it (a push to a non-bare checked-out branch is refused, and OneDrive syncing a live
`.git/` is a known corruption risk). If you want to read the latest docs on the Windows side,
`git pull` there from GitHub, or just read them on GitHub.

## 5. Decisions to write down before the first session

| Decision | Where |
|---|---|
| Pinned model and its **training-cutoff date** (from the model docs) | `docs/DECISIONS.md` D-001 |
| First two repos (default: AntennaPod, Wikipedia Android) | `docs/DECISIONS.md` D-003 (the agent fills in evidence) |
| Dev budget per trial and total for weeks 1–4 | `benchmark/config/limits.yaml`, `PLAN.md` §6 |
| Whether the Spec Kit arm is in scope now or after the MVP decision (when the first results table exists, target end of week 5) | `PLAN.md` §9 |

## 6. Start

Open a **new** terminal (so `~/.local/bin` is on PATH and `ANTHROPIC_API_KEY` is exported), then:

```bash
cd ~/abb && claude
```

Paste the Phase 0 kickoff prompt from `START-HERE.md`. The agent's first step is to verify
everything above and stop if something is missing.
