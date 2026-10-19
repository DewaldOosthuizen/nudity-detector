# Nudity Detector

[![PR Gate](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/pr_gate.yml/badge.svg)](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/pr_gate.yml)
[![Release](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/release.yml/badge.svg)](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/release.yml)

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/paypalme/DewaldOosthuizen1)

AI-based nudity detection for images and videos. Python GTK4/libadwaita desktop application with pluggable detector backends (NudeNet local, Helloz NSFW Docker).

## Documentation

All documentation lives in [docs/](docs/).

| Document | Description |
|----------|-------------|
| [docs/getting-started.md](docs/getting-started.md) | Installation, prerequisites, running, building |
| [docs/configuration.md](docs/configuration.md) | Configuration reference |
| [docs/architecture.md](docs/architecture.md) | Architecture overview |
| [docs/contributing.md](docs/contributing.md) | Contributing guide |
| [docs/development.md](docs/development.md) | Development workflow |
| [docs/releasing.md](docs/releasing.md) | Release process |
| [docs/add/README.md](docs/add/README.md) | Architectural Decision Documents |

## Quick Start

```bash
git clone https://github.com/DewaldOosthuizen/nudity-detector.git
cd nudity-detector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python3 run_gui.py
```

## License

MIT
