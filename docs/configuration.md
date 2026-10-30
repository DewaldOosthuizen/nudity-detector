# Configuration

The Nudity Detector application has a single configuration surface: `config/app_config.json`.

That file is created by the app on first run and is **not tracked in git** — it also holds mutable user state (`theme`, `model`, `last_source_folder`), so tracking it would leave every working tree permanently dirty. The documented defaults live in the immutable fixture `tests/fixtures/app_config.default.json`.

No environment-variable overrides are supported — there is no `python-dotenv` or `os.environ` usage anywhere in the codebase. `.env.example` is a plain-text reference table documenting all `app_config.json` keys, their code-default constants (where applicable), and default values; it is not an env-var template.

---

## Config Keys

All 19 keys in `config/app_config.json`:

| Key | Default | Constant (src/core/constants.py) | Scope |
|-----|---------|----------------------------------|-------|
| `config_version` | `2` | `CONFIG_VERSION` | app-wide |
| `theme` | `"dark"` | `THEME_DARK` | app-wide |
| `model` | `"helloz_nsfw"` | *no constant* | app-wide |
| `threshold_percent` | `60.0` | `DEFAULT_THRESHOLD_PERCENT` | app-wide |
| `last_source_folder` | `""` | *no constant* | app-wide |
| `progress_update_interval` | `100` | `SCAN_PROGRESS_UPDATE_INTERVAL` | app-wide |
| `video_frame_rate` | `5` | `VIDEO_FRAME_RATE` | app-wide |
| `worker_thread_count` | `10` | `WORKER_THREAD_COUNT` | app-wide |
| `worker_thread_timeout_seconds` | `5` | `WORKER_THREAD_TIMEOUT` | app-wide |
| `nudenet_worker_thread_count` | `4` | *no constant*, *dead* — see #104 | app-wide |
| `nudenet_worker_thread_timeout_seconds` | `10` | *no constant*, *dead* — see #104 | app-wide |
| `helloz_nsfw_worker_thread_count` | `20` | *no constant*, *dead* — see #104 | Helloz-NSFW |
| `helloz_nsfw_worker_thread_timeout_seconds` | `35` | *no constant*, *dead* — see #104 | Helloz-NSFW |
| `detect_timeout_seconds` | `60` | `DETECT_TIMEOUT` | app-wide |
| `helloz_nsfw_host` | `"localhost"` | `HELLOZ_NSFW_HOST` | Helloz-NSFW |
| `helloz_nsfw_port` | `6086` | `HELLOZ_NSFW_PORT` | Helloz-NSFW |
| `helloz_nsfw_api_endpoint` | `"/api/upload_check"` | `HELLOZ_NSFW_API_ENDPOINT` | Helloz-NSFW |
| `helloz_nsfw_request_timeout_seconds` | `30` | `HELLOZ_NSFW_REQUEST_TIMEOUT` | Helloz-NSFW |
| `helloz_nsfw_health_check_timeout_seconds` | `5` | `HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT` | Helloz-NSFW |

### Unit convention

Note on units: the `_seconds` suffix is the unit declaration. All timeout values are stored in **seconds**, matching the constants in `src/core/constants.py` and the `threading` API. No value is ever re-interpreted on the strength of its magnitude, so `detect_timeout_seconds: 3600` means one hour, as written.

Every timeout key the app **reads** states its unit in its name — there is no bare `*_timeout` key among them, so the suffix is a reliable marker and not a convention.

### Dead keys

The four *dead* reference entries are the documented exemption: they carry the `_seconds` suffix in the shipped tables below (for consistency with the keys they would replace), but nothing reads them, so the migration deliberately leaves an existing config's bare `nudenet_worker_thread_timeout` / `helloz_nsfw_worker_thread_timeout` spellings alone — there is no value in flight whose unit needs restating. They are **not read by any code** (no `src/` reader) and are retained only as reference entries: `nudenet_worker_thread_count`, `helloz_nsfw_worker_thread_count`, `nudenet_worker_thread_timeout_seconds` and `helloz_nsfw_worker_thread_timeout_seconds`. Their removal is tracked in issue #104, and `constants.DEAD_CONFIG_KEYS` is the single source of that list.

How "dead" is established: a test walks every module under `src/` and looks for a *mapping read* of each key — `cfg.get('key')` or `cfg['key']`. Merely naming a key (in `DEAD_CONFIG_KEYS`, in the migration's rename tables, or in a docstring) is not a reader, so the fact that `DEAD_CONFIG_KEYS` lives in `src/core/constants.py` and therefore names its own entries does not make the classification self-fulfilling. Both directions are pinned: every entry in `DEAD_CONFIG_KEYS` must have **no** mapping read anywhere under `src/`, and every shipped fixture key **not** in `DEAD_CONFIG_KEYS` must have at least one. So a key cannot be documented as live without a reader, and cannot be quietly promoted to live either.

The "retained as reference" state describes the *shipped defaults* in `.env.example` and `tests/fixtures/app_config.default.json` only. A config written by the GUI (`_save_config`, run on quit and on every theme change) starts from the config loaded at startup and overwrites only the keys the GUI has a widget for, so anything else in your own `config/app_config.json` survives: the four dead entries, `helloz_nsfw_scheme` (the user's escape hatch for forcing HTTPS against a remote host), and any key a future version adds. The shipped tables are the reference, not a promise about the file on disk.

Only `worker_thread_count` is read for the worker pool; the per-detector counts above are inert.

### helloz_nsfw_scheme (special key)

One key is deliberately *not* in the table above, because it is not shipped with a default: `helloz_nsfw_scheme`. When present it forces the scheme used for the Helloz NSFW endpoint (`constants.resolve_scheme`); when absent the rule is `http` for a loopback host and `https` for any remote host, and `constants._validate_scheme` rejects an explicit `http` paired with a non-loopback host.

The **Scheme** dropdown in the **Helloz NSFW** frame of the **Settings** tab owns this key: `http` for loopback hosts, `https` for any remote host. The resolved scheme is validated before any save, so a remote user cannot persist an insecure `http` configuration. The selector writes this key explicitly via `_save_config`; every other key the GUI does not own is preserved verbatim.

The **Test Connection** button in the same frame probes the Helloz health-check URL without saving anything. A connection test never writes to `config/app_config.json` — it only reports the result in the activity log and via a dialog.

---

## Automatic migration (issue #91)

The config carries a `config_version`. Before version 2 the two timeout keys were named `worker_thread_timeout` / `detect_timeout` and held **milliseconds** — which is what produced the reported 250-second hangs on the values the project shipped.

On startup, `src/core/config_migration.py` converts any pre-version-2 config once, deterministically and atomically (sibling temp file plus `os.replace`, so an interrupted rewrite cannot truncate the user's only config file), then stamps it `config_version: 2` so the conversion never runs twice. The normative rules — the millisecond conversion and its sub-second fallback, which spelling wins when both are present, and the keys that are renamed without conversion — are stated once, in [`docs/add/ADD-007`](../add/ADD-007-seconds-canonical-timeout-unit.md), and are not restated here.

Migration notes — every rewrite, and every failure to read or rewrite the file — are logged at WARNING level **and** written to the on-screen activity log, naming the key and both the old and new value. (Coercion warnings raised later on the detection read path are WARNING-level logger records only and are *not* shown in the activity log.) Re-check your timeout values once after upgrading; the log tells you exactly what changed.

Exactly one config entry has no corresponding constant in `src/core/constants.py` and is read directly from `config/app_config.json` at runtime: `last_source_folder`. The four entries listed above as dead have no constant *and* no reader. A test enumerates both sets (`FIXTURE_NON_CONSTANT_KEYS` / `constants.DEAD_CONFIG_KEYS`) so the classification cannot drift.

---

## Validation and coercion

Every numeric config value is coerced by `constants.normalize_positive_int` / `constants.normalize_timeout_seconds`, and the one float key (`threshold_percent`) by `constants.normalize_threshold_percent` — in `__init__`, in every widget accessor, and on the detection backend's own read of the file (`_load_helloz_config`, which coerces the port with the same `1..MAX_PORT` bound and guards the host, endpoint and scheme strings): an unparseable, boolean, or out-of-range value falls back to the constant default (or is clamped to the documented bound) and is logged at WARNING level, so no config error is applied silently — and none of them can abort startup.

Supported ranges: `helloz_nsfw_port` is clamped to `1..65535`, and the timeout keys to their `TIMEOUT_MAX_SECONDS` bound (`worker_thread_timeout_seconds` and `detect_timeout_seconds`: 86400 s; the two Helloz timeouts: 3600 s). Every call site passes that bound **explicitly** — `normalize_timeout_seconds` never infers it from the `name` it is given, because the widget accessors name a widget (`detect_timeout_spin`), not a config key, and the inference silently dropped the clamp on the save path. The GUI spin buttons use the same bounds, so a value inside the supported range is never truncated by the widget. A value *beyond* it is clamped, and `constants.log_timeout_truncations` reports the truncation at WARNING with the key, the configured value and the applied maximum — the note reaches the activity log, so a clamped value is visible rather than silently rewritten on the next save.

A value that is the right unit but the wrong magnitude relative to its constant (e.g. a hand-tuned `helloz_nsfw_request_timeout_seconds: 300` against the 30 s code default) is legitimate and is honoured as written — but `constants.log_config_default_divergences` reports it at WARNING on startup and the note reaches the activity log, so the shipped defaults agree with `constants.py` on day one and any later divergence is visible.

Startup validation: if `config/app_config.json` is missing or contains invalid JSON, `_load_helloz_config` in `src/core/constants.py` logs a `WARNING` and falls back to the built-in defaults from `constants.py`. See the `logger.warning` call in that function for the exact message.
