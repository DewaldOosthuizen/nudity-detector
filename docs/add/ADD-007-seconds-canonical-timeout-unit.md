# ADD-007 — Seconds as the Canonical Timeout Unit

| Field      | Value                          |
|------------|--------------------------------|
| Status     | Accepted                       |
| Date       | 2026-10-02 17:37               |
| Revised    | 2026-10-05 09:40               |
| Author     | Dewald Oosthuizen              |
| Relates to | ADD-005, ADD-006               |

---

## Context

`config/app_config.json` stored `worker_thread_timeout` and `detect_timeout` as
millisecond-scale values (`250`), while `src/core/constants.py` defined the
corresponding defaults in seconds (`WORKER_THREAD_TIMEOUT = 5`,
`DETECT_TIMEOUT = 60`). `src/gui/app.py` read the config values with
`int(cfg.get(...))` and no unit conversion, then passed them straight to
`threading.Thread.join(timeout=...)` (`src/core/utils.py`) and
`detect_with_timeout(..., timeout_seconds=...)` (`src/core/utils.py`), both of
which take seconds.

A user relying on the shipped config therefore received a 250-second worker join
timeout (4+ minutes) and a 250-second per-file detection timeout instead of a
fast failure — a stuck detection froze the scan rather than being skipped. No
unit was named or validated anywhere in the read path, so the mismatch was
invisible to the type system and to the tests (which mocked the accessors).

---

## Decision

**Seconds is the single canonical timeout unit end to end, and the unit is
*stated*, never guessed.** Two mechanisms carry that:

### 1. Explicit units in the key names

The two timeout keys are renamed to `worker_thread_timeout_seconds` and
`detect_timeout_seconds`. The `_seconds` suffix is a machine-readable unit
declaration in a JSON file, which is exactly where a magnitude heuristic does not
belong. `normalize_timeout_seconds(value, default_seconds, name=None)` coerces a
value that is already known to be in seconds; it makes no attempt to infer a unit.
It returns whole seconds, always `>= 1` (the fallback is clamped too, so the
guarantee is enforced by the code rather than by today's constant values), falls
back to `default_seconds` on `None`/`TypeError`/`ValueError`/`OverflowError` (the
last covers non-finite floats such as `float('inf')`, which `int()` rejects), and
rejects `bool` explicitly — a JSON `true` in a timeout key is a user error, not
the value 1.

### 2. A one-time deterministic migration, gated on `config_version`

The config carries a `config_version` field (`CONFIG_VERSION = 2`). A config
without one, or below 2, predates the seconds contract and is converted **once**
by `src/core/config_migration.py`:

- a legacy millisecond value `>= 1000` converts ms → s, round-half-up
  (`2500` → `3`);
- a legacy value below one second — **including the shipped `250`** — becomes the
  key's constant default (`5` s / `60` s). The whole `0–999` ms band is treated
  this way, not only the values that round to 0 s: `700` would otherwise round to a
  1-second timeout, which times out on essentially every file — the exact failure
  the fallback exists to prevent;
- the file is rewritten with the `_seconds` key names and `config_version: 2`, so the
  conversion never runs twice; the migration is idempotent.

**Every timeout key is migrated, not just the two that were in milliseconds.** Four
keys — `helloz_nsfw_request_timeout`, `helloz_nsfw_health_check_timeout`,
`nudenet_worker_thread_timeout`, `helloz_nsfw_worker_thread_timeout` — already held
seconds but carried no suffix. Renaming them in the same versioned migration keeps the
premise of this ADD true: the `_seconds` suffix is a reliable unit marker, not a
convention honoured by some keys. Their values are **not** converted — only the key
name changes, so a `helloz_nsfw_request_timeout: 300` stays 300 s rather than becoming
0.3 s. The first revision of this ADD left them unsuffixed; that was the "half-renamed
schema" that made the central claim only half true.

**An existing `*_seconds` value always wins.** A partially applied upgrade or a restored
backup can hold both spellings of a key. The suffixed key is the one that states its
unit, so the migration drops the legacy key and keeps the explicit value, emitting a
change note that says so. Overwriting a user's hand-edited `detect_timeout_seconds: 120`
with a converted legacy value was the one irreversible data path in the PR, and the
direction of that loss was not recoverable from the log.

**The rewrite is persisted at startup, atomically.** `migrate_config_file()` is called
from `NudityDetectorWindow.__init__`, so the on-disk file carries the migrated key names
and the version stamp immediately — the guarantee is the upgrade, not an unrelated
`_save_config` the user may never trigger. The write goes to a sibling temp file and is
moved over the target with `os.replace`: the config file is the user's only copy of
their theme, model and last source folder as well as their timeouts, so it must never
be left as a partial JSON document by a crash or a full disk. The written file ends with
a newline.

`250` is the crux of issue #91, so it deserves the reasoning stated plainly. The
first revision of this ADD deliberately excluded it as "ambiguous", on the grounds
that 250 is both the former millisecond default and a legal seconds value. That
reasoning was wrong on the merits: `250` is the value *this project shipped*, and
the entire issue is that shipping it produced a 250-second freeze. Excluding the
one value every affected user actually has, in favour of protecting a 250-second
worker join timeout that nobody plausibly configured, fixes nobody. In a config
whose declared version says the values are milliseconds there is no ambiguity to
preserve — the version *is* the answer. Resolving `250` by its version rather than
its magnitude is exactly what makes the conversion deterministic.

The sub-second fallback is likewise principled, not a fudge: 250 ms is 0.25 s,
which no whole-second timeout can express, and a 0.25 s detection timeout would
time out on essentially every file. `WORKER_THREAD_TIMEOUT` / `DETECT_TIMEOUT` are
the correct destination for a value that cannot be honoured.

### 3. Rewrites are visible in the GUI, not only in the log

A unit rewrite the user never sees is a rewrite they cannot correct. Every
migration and every coercion failure is logged at WARNING level naming the key,
and the migration notes are additionally written to the on-screen activity log
(`NudityDetectorWindow._announce_config_migration`). The GUI user reads the
activity log, not the Python logger.

### 4. Config and constants agree on the shipped default, and divergence is visible

Normalizing the *type* of a value does nothing about a value that is the right unit and
the wrong magnitude. `helloz_nsfw_request_timeout: 300` shipped against a 30 s constant
and `video_frame_rate: 10` against a 5 s one; both were accepted silently, so "the
mismatch cannot silently recur" was only true for units. Two changes close that:

- the shipped defaults (`.env.example` and `tests/fixtures/app_config.default.json`) now
  equal their constants, so config and code agree on day one; and
- `constants.log_config_default_divergences` logs a WARNING naming any key whose
  configured value differs from its constant default and returns that description for
  the activity log. The value is **never** rewritten — a hand-tuned timeout is
  legitimate — but the user is told, per section 3.

`CONFIG_DEFAULT_ALIGNMENT` enumerates the aligned keys, so the fixture test
`test_shipped_defaults_equal_constants` fails on any future drift.

### 5. One coercion implementation, one logging policy

`constants.normalize_positive_int(value, default, name=None, min_value=1,
max_value=None, quiet=False)` is the single implementation of "config scalar → safe
positive int". Every numeric config read — `worker_thread_count`,
`video_frame_rate`, `progress_update_interval`, `helloz_nsfw_port`, and all four
timeouts — routes through it, in both `__init__` and every widget accessor. This
includes `_get_progress_interval()`, `_get_video_frame_rate()` and
`_get_worker_thread_count()`, which previously hand-rolled
`max(1, int(spin.get_value()))`, and `_get_helloz_nsfw_port()`, which substituted the
constant default for an out-of-range value without logging. Previously the same
coercion was hand-rolled in six places, some of which logged and some of which did
not. The policy is now uniform: absent → DEBUG (a missing key is normal on a fresh
install, not a defect); unparseable, boolean, below-minimum, or above-maximum →
WARNING naming the key.

`quiet=True` exists for the divergence pass (§4): it wants the coerced *value* only
and delegates value-coercion reporting to the single read path, so an invalid value
yields one WARNING naming the key rather than two that read as separate problems.

### 5a. Bounded ranges, and no silent truncation by the widget

A documented "no value is ever re-interpreted" guarantee is worthless if the GUI
silently rewrites a legal value: the spin buttons were built with `upper=600`
(detect), `300` (worker, Helloz request) and `60` (Helloz health), so a configured
`detect_timeout_seconds: 3600` survived exactly one launch and was then persisted as
600 by the next save — the same irrecoverable, invisible loss this ADD rejects for the
both-spellings-present case.

`constants.TIMEOUT_MAX_SECONDS` declares the supported range per key (86400 s for the
two general timeouts, 3600 s for the two Helloz timeouts) and is used as the spin
buttons' `upper`, so the widget represents every value the config path accepts.
`normalize_timeout_seconds` derives the bound from `TIMEOUT_MAX_SECONDS` by key name,
and `normalize_positive_int`'s new `max_value` clamps anything beyond it, logging the
key, the configured value and the applied maximum.
`constants.log_timeout_truncations` produces that note for the activity log at
startup. A value beyond the documented maximum is therefore clamped *visibly*; a value
within it is never truncated.

`MAX_PORT` does the same for `helloz_nsfw_port` (`1..65535`), replacing the inline
literal in the adjustment and the silent range check in the accessor.

### 5b. One writer for the config file

`config_migration.write_config()` is the single atomic writer, used by both the startup
migration and `NudityDetectorWindow._save_config()`. `_save_config` previously opened
the file with `open(path, 'w')` — truncating the user's only config file on an
interrupted write — and swallowed `OSError`/`IOError` with a bare `pass`, so a full
disk or a permission change discarded every pending setting change with no log line
and no activity-log entry. It now writes through `write_config` and, on failure, logs
at WARNING naming the path and exception and surfaces the failure in the activity log
via the existing `log_message` mechanism.

### 6. The runtime config is not committed

`config/app_config.json` carries mutable user state (`theme`, `model`,
`last_source_folder`), so tracking it would leave every user's working tree
permanently dirty and create a merge hotspot. It is removed from the index and
covered by the existing `config/` entry in `.gitignore`. The documented defaults
are asserted against the immutable fixture `tests/fixtures/app_config.default.json`,
which is parametrised against `constants.py` so every constant-backed key — not
just the two timeout keys — fails on drift.

The GUI accessors `_get_worker_thread_timeout()` and `_get_detect_timeout()` in
`src/gui/app.py` remain the **documented unit boundary**: every configured or
spin-button value passes through `normalize_timeout_seconds()` before it reaches
the threading API. The spin-button labels already read `Thread Timeout (s)` /
`Detect Timeout (s)`, so the accessors make that "s" true by construction.

The `tests/fixtures/app_config.default.json` reference file, the `.env.example`
reference table, and the `README.md` config table were corrected to the seconds
defaults and the new key names.

**Dead keys.** `nudenet_worker_thread_count` and `helloz_nsfw_worker_thread_count` are
*also* unread: the only worker-count key any code reads is `worker_thread_count`. The
earlier README claimed otherwise, and since #104's scope is derived from this
documentation, a wrong live/dead classification is a real defect rather than a typo.
`constants.DEAD_CONFIG_KEYS` is now the single source of that list, and a test greps
`src/` for every shipped fixture key: a key documented as live without a reader under
`src/` fails, so the classification cannot drift in either direction.

---

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| **Explicit units + one-time versioned migration** (current) | Matches the `threading` API and the existing `constants` defaults; the unit is declared, not inferred; existing installs are repaired deterministically, `250` included; no value can be silently reinterpreted | **Accepted** |
| Per-read magnitude heuristic (`>= 1000` means ms) | No schema change — but it cannot repair `250` (the value actually shipped) and it silently rewrites legitimate large seconds values: `detect_timeout: 3600` became `4`, so a working config starts failing fast. A heuristic is the wrong mechanism for a machine-read file | Rejected |
| Keep milliseconds, convert in GUI | Preserves the old ms contract — but the GUI must display milliseconds (worse UX), two units coexist, and a 1 s-minimum spin button cannot represent `250 ms` anyway | Rejected |
| Type-safe wrapper (`timedelta` / `NewType`) | Removes ambiguity entirely — but adds ceremony to a small codebase and does not fit the plain-int config surface | Rejected |

A 250 ms value (0.25 s) cannot even be represented by a 1 s-minimum spin
button, and a 0.25 s detection timeout would skip almost every file — so the
millisecond values were themselves part of the defect, not the intended
behaviour.

---

## Consequences

**Positive:**
- One unit (seconds) across config, constants, GUI, and the `threading` API — the
  mismatch cannot silently recur.
- The unit is declared in the key name and the config version, so no code path
  guesses a unit from a value's magnitude. `detect_timeout_seconds: 3600` means
  one hour.
- **Existing installations are repaired.** A config still holding the shipped
  `worker_thread_timeout: 250` / `detect_timeout: 250` migrates to 5 s / 60 s on
  first launch and is rewritten on disk — the remedy is the upgrade, not a README
  footnote.
- One coercion implementation with one logging policy, so no numeric config read
  can fail silently.
- **Every** timeout key states its unit in its name; there is no bare `*_timeout` key,
  so the suffix can be relied on by the next reader.
- Covered by unit and migration tests (`tests/core/test_timeout_units_issue91.py`)
  and by GUI-boundary regression tests that drive the real `__init__` config path
  (`tests/gui/test_scanning_mixin.py::TestTimeoutUnits`), including the on-disk rewrite
  at startup.

**Negative / Trade-offs:**
- The two timeout keys are renamed. Any tooling or hand-edit referencing
  `worker_thread_timeout` / `detect_timeout` must be updated; the automatic
  migration covers the app's own config file, not external scripts.
- `normalize_positive_int` / `normalize_timeout_seconds` accept a plain int; they
  do not carry the unit in the type. The `_seconds` key suffix and the docstrings
  are the guard.
- The operator must still review their timeout values once after upgrading; the
  migration reports every rewrite rather than assuming intent.
- A configured value that differs from its constant default now produces a WARNING on
  every launch. That is intentional — silence was the defect — but a deliberately
  hand-tuned timeout will be reported each time rather than once.
- `_save_config` writes only the keys the GUI owns, so a hand-added key in
  `config/app_config.json` is dropped on the next save. This predates ADD-007.

**Follow-up (out of scope here):** `nudenet_worker_thread_timeout_seconds` and
`helloz_nsfw_worker_thread_timeout_seconds` are renamed by the migration for
consistency but are still not read by any code (no `src/` references). Their removal
is a separate cleanup, tracked as **issue #104** ("Remove dead timeout config keys").
The keys are retained here so this PR stays scoped to the unit mismatch.
