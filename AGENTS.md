# DewaldOosthuizen/nudity-detector

Python-based application for detecting nudity in images and videos using AI backends.
Provides a GTK4 + libadwaita GUI as well as CLI entry points.
Suitable for content moderation, safety filters, and compliance checks.

Two detector backends:
- NudeNet — local detection via the `nudenet` library (no server required); processes videos by
  extracting frames and analysing them as images.
- Helloz NSFW — remote detection via a `helloz/nsfw` Docker AI server (http://localhost:6086)

---

## Entry Points

| File | Purpose |
|---|---|
| `run_gui.py` | Launch the GTK4 libadwaita GUI (recommended) |
| `run_nudenet.py` | CLI scan using NudeNet backend |
| `run_helloz_nsfw.py` | CLI scan using Helloz NSFW backend |

## Key Directories

| Path | Contents |
|---|---|
| `config/app_config.json` | Runtime config — Helloz host/port/endpoint |
| `.env.example` | Config-key reference table — all `app_config.json` keys, their code-default constants, and default values |
| `reports/` | Generated Excel reports (`nudity_report.xlsx`) |
| `scripts/` | Linux build script + PyInstaller spec |
| `tests/` | Pytest test suite |
| `docker-compose.yml` | Helloz NSFW Docker AI server |

## Supported File Formats

Images: PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF
Videos: MP4, AVI, MKV, MOV, VOB, WMV, FLV, 3GP, WEBM

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

## Running the Helloz NSFW Backend

```bash
docker-compose up --build
# Verify server
curl -X POST -F file=@test.jpg 'http://localhost:6086/api/upload_check'
```

The endpoint is configurable via `config/app_config.json` keys:
`helloz_nsfw_host`, `helloz_nsfw_port`, `helloz_nsfw_api_endpoint`.

## Output

Reports are written to `reports/nudity_report.xlsx`. The Excel report includes:
- File path, media type, model used, threshold and confidence percentages

## CI / CD

Documentation for the CI/CD pipeline lives in [docs/index.md](docs/index.md).
Authoritative rules (verification, review, conventions) live in
[openspec/config.yaml](openspec/config.yaml).

## Architecture

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — architecture overview
- [docs/releasing.md](docs/releasing.md) — release and packaging notes
