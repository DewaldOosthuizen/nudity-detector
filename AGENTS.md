# DewaldOosthuizen/nudity-detector

Python-based application for detecting nudity in images and videos using AI backends.
Provides a GTK4 + libadwaita GUI as well as CLI entry points.
Suitable for content moderation, safety filters, and compliance checks.

Two detector backends:
- NudeNet — local detection via the `nudenet` library (no server required)
- Helloz NSFW — remote detection via a `helloz/nsfw` Docker AI server (http://localhost:6086)

---

## Entry Points

| File | Purpose |
|---|---|
| `run_gui.py` | Launch the GTK4 libadwaita GUI (recommended) |
| `run_nudenet.py` | CLI scan using NudeNet backend |
| `run_helloz_nsfw.py` | CLI scan using Helloz NSFW backend |

---

## Key Directories

| Path | Contents |
|---|---|
| `config/app_config.json` | Runtime config — Helloz host/port/endpoint |
| `.env.example` | Available env overrides with defaults |
| `reports/` | Generated Excel reports (`nudity_report.xlsx`) |
| `scripts/` | Linux build script + PyInstaller spec |
| `tests/` | Pytest test suite |
| `docker-compose.yml` | Helloz NSFW Docker AI server |

---

## Development Quick-Start

```bash
# Install runtime + dev dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run tests
pytest tests/

# Run tests with coverage
pytest --cov tests/

# Audit dependencies for vulnerabilities
pip-audit -r requirements.txt
```

GTK4 system bindings must be exposed to the venv — see README.md installation steps 4-5.

---

## Running the Helloz NSFW Backend

```bash
docker-compose up --build
# Verify server
curl -X POST -F file=@test.jpg 'http://localhost:6086/api/upload_check'
```

---

## Building a Linux Package

```bash
bash scripts/build_linux.sh
# Outputs: dist/nudity-detector/ (PyInstaller) and dist/NudityDetector-x86_64.AppImage
```

---

<!-- graph-tools-start -->

## graphify

graphify-out/ not yet generated for this repo.

## understand-anything

.understand-anything/knowledge-graph.json is present.
Use it for layered architecture questions (layers, communities, entry points).

```bash
# Launch the interactive dashboard
cd ~/.understand-anything-plugin/packages/dashboard
GRAPH_DIR=$(pwd) npx vite --host 127.0.0.1
```

For prose questions load the skill:
```
skill: understand-chat
```

## codegraph

.codegraph/ is present. Use it FIRST for any symbol lookup,
call tracing, or targeted context gathering before opening source files.

```bash
codegraph context "<task description>" -p .   # focused file+symbol context
codegraph query "<ClassName or function>" -p . # where is X defined / used
codegraph affected <changed-files> -p .        # which tests are affected
codegraph sync .                               # after any code change
```

Decision order for code tasks:
  1. codegraph context  — which symbols matter?
  2. graphify query     — which files are involved?
  3. understand-anything — where in the architecture does this live?
  4. Read raw source    — only the 1-2 files that actually matter.

<!-- graph-tools-end -->
