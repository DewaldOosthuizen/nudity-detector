# ADD-003 — Pluggable Detector Backends

| Field      | Value                  |
|------------|------------------------|
| Status     | Accepted               |
| Date       | 2024-02-01             |
| Author     | Dewald Oosthuizen      |
| Relates to | ADD-001                |

---

## Context

Two detection engines are supported:

- **NudeNet** — a local Python library that runs entirely in-process.
- **Helloz NSFW** — a Docker-hosted HTTP AI service accessed via `curl` / HTTP POST.

Early versions hard-coded NudeNet throughout the GUI and CLI runners, making
it impossible to swap backends without forking code. Adding a third detector
in the future would require further surgery across all layers.

The detectors also differ fundamentally in their failure modes: NudeNet fails
with a Python exception; Helloz NSFW fails with an HTTP error or connection
timeout. The coordinator (`src/core/utils.py`) must handle both uniformly.

---

## Decision

Isolate each detector in its own module under `src/detectors/`:

```
src/detectors/
├── nudenet.py       ← local NudeNet invocation
└── helloz_nsfw.py   ← HTTP POST to Docker service
```

Both detectors expose the same calling convention: accept a file path and
threshold, return a `(confidence: float, detected_classes: list)` tuple.
`src/core/utils.py` selects the detector at runtime based on `ScanConfig.model_name`
(a string constant from `src/core/constants.py`: `MODEL_NUDENET` or
`MODEL_HELLOZ_NSFW`).

Model selection is surfaced in `config/app_config.json` and the GUI dropdown —
no detector-specific logic lives above the coordinator layer.

---

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| Hard-coded NudeNet in GUI | Zero abstraction — already existed | Rejected |
| Detector Protocol / ABC | Formal interface ensures contract is enforced at type-check time | Considered but deferred — would require PyGObject stub stubs to type-check; benefit is low with two concrete backends |
| Plugin registry (entry_points) | Extensible to third-party detectors | Deferred — over-engineering for current scope |
| Module-level strategy (current) | Simple, explicit, testable — each detector is an isolated module | **Accepted** |

---

## Consequences

**Positive:**
- Adding a third detector requires only a new file in `src/detectors/` and a
  new `MODEL_*` constant — the GUI and CLI runners need no changes.
- Each detector module is independently unit-testable with mocks.
- Helloz NSFW health-check retry logic (`HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT`,
  `HELLOZ_NSFW_RETRIES`) is encapsulated in `helloz_nsfw.py` and does not
  leak into the coordinator.

**Negative / Trade-offs:**
- There is no enforced interface contract between detectors — a new detector
  that returns a different shape will fail at runtime, not at import time.
  A formal `Protocol` type should be added if a third detector is introduced.
- The Helloz NSFW detector depends on Docker being running — the application
  degrades silently if the service is unreachable unless the health check is
  explicitly invoked before starting a scan.
