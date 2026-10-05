# ADD-007 — Seconds as the Canonical Timeout Unit

| Field      | Value                          |
|------------|--------------------------------|
| Status     | Accepted                       |
| Date       | 2026-10-02 17:37               |
| Revised    | 2026-10-05 14:20               |
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

**Every timeout key a reader touches is migrated, not just the two that were in
milliseconds.** Two keys — `helloz_nsfw_request_timeout` and
`helloz_nsfw_health_check_timeout` — already held seconds but carried no suffix.
Renaming them in the same versioned migration keeps the premise of this ADD true for
every key the app actually consumes: the `_seconds` suffix is a reliable unit marker,
not a convention honoured by some keys. Their values are **not** converted — only the
key name changes, so a `helloz_nsfw_request_timeout: 300` stays 300 s rather than
becoming 0.3 s. The first revision of this ADD left them unsuffixed; that was the
"half-renamed schema" that made the central claim only half true.

`nudenet_worker_thread_timeout` and `helloz_nsfw_worker_thread_timeout` were in that
list in the second revision and are now **excluded**: this PR's own tests classify both
as dead (no `src/` reader). Renaming a key exists to make the unit of a value the app
uses unambiguous; a key nothing reads has no such value, and no code path ever
established its pre-rename unit, so the justification was unfalsifiable. Issue #104
deletes them.

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
`normalize_positive_int`'s `max_value` clamps anything beyond it, logging the
key, the configured value and the applied maximum.
`constants.log_timeout_truncations` produces that note for the activity log at
startup. A value beyond the documented maximum is therefore clamped *visibly*; a value
within it is never truncated.

The bound is passed **explicitly at every call site**
(`max_seconds=constants.<KEY>_MAX_SECONDS`), never inferred from the `name` argument.
The earlier revision inferred it from the name by looking the key up in
`TIMEOUT_MAX_SECONDS`, which is wrong in a way no test could see: the four widget
accessors pass a *widget* name (`detect_timeout_spin`), never a config key, so the
lookup never matched and the clamp was inert on `_save_config` — precisely the path
where a bound is supposed to be enforced. A renamed widget or a typo in a log label
would have removed it silently. `normalize_timeout_seconds` now logs a WARNING when
called without a bound, so a missing bound is loud rather than invisible.

`MAX_PORT` does the same for `helloz_nsfw_port` (`1..65535`), replacing the inline
literal in the adjustment and the silent range check in the accessor.

### 5b. One read path for the config file, and keys the GUI does not own

`_load_helloz_config()` was a second, uncoerced reader of the same file: it took the
host, port, endpoint and scheme with bare `cfg.get()` and the raw constant defaults,
so a hand-edited or legacy port such as `"abc"` or JSON `true` was interpolated
straight into the request URL (`http://localhost:True:6086/...`) with no warning
anywhere. It now routes through the same helpers as the GUI read path —
`normalize_positive_int(..., min_value=1, max_value=MAX_PORT)` for the port and a
shared `_normalize_config_text` guard for the string keys — so there is one read
policy rather than two. `resolve_scheme()` is likewise the single scheme rule, shared
by the detection getters and the GUI URL builders; the GUI helpers previously
hardcoded `http://`, bypassing `_validate_scheme` entirely and contacting a remote host
over plaintext regardless of the configured scheme.

`_save_config()` likewise wrote the file from a literal whitelist of fifteen keys, so
every other key was deleted on the next save — and that save runs on quit *and* on
every theme change. The erased set included `helloz_nsfw_scheme`, the user's own
escape hatch for forcing HTTPS against a remote deployment, so a remote user's
`https` was reverted the moment they touched the theme dropdown. The write now starts
from the config loaded at startup and overwrites only the keys that have a widget;
unknown and future keys survive.

### 5c. One writer for the config file

`config_migration.write_config()` is the single atomic writer, used by both the startup
migration and `NudityDetectorWindow._save_config()`. `_save_config` previously opened
the file with `open(path, 'w')` — truncating the user's only config file on an
interrupted write — and swallowed `OSError`/`IOError` with a bare `pass`, so a full
disk or a permission change discarded every pending setting change with no log line
and no activity-log entry. It now writes through `write_config` and, on failure, logs
at WARNING naming the path and exception and surfaces the failure in the activity log
via the existing `log_message` mechanism.

### 5d. Review follow-ups: one rule per concern, and no silent forward path

Four defects found in review of this PR's own additions are closed here, all of the
same shape — a rule that exists in two places, or nowhere:

**The scheme rule had two copies.** `resolve_scheme()` was introduced as the single
scheme rule and then `_load_helloz_config` inlined the same
http-for-loopback / https-for-remote default expression twice in a row, so the
security-relevant half of the rule was duplicated inside one file and only one copy
was canonical. `_load_helloz_config` now ends with
`resolve_scheme(host, cfg.get('helloz_nsfw_scheme'))`; a test asserts the default
expression occurs exactly once in `constants.py`.

**A valid JSON document of the wrong shape was fatal.** The `try/except` in
`_load_helloz_config` covered only `open()`/`json.load()`, so a config containing
`[1, 2]`, `"dark"` or `null` parsed successfully and then `cfg.get(...)` raised
`AttributeError`/`TypeError` out of the detection backend on every call. The shape is
now checked after the load and the built-in defaults are returned with a WARNING
naming the file and the JSON type found.

**The millisecond conversion was float arithmetic outside its own guard.** The
round-half-up step used `int(ms / 1000 + 0.5)`, which is inexact, and sat outside the
`OverflowError` guard the comment above it reasoned about — so a hand-edited
multi-hundred-digit JSON integer raised straight out of `migrate_config`, and therefore
out of the window constructor. It is now exact integer arithmetic,
`(ms + 500) // 1000`, inside a guarded block. Separately, the threshold it compares
against is now `SUBSECOND_MILLISECOND_CEILING`, distinct from the
`MILLISECONDS_PER_SECOND` conversion factor, so the two cannot be changed together
and a future reader cannot mistake the factor for a unit-detection bound.

**A downgrade was silently accepted.** `config_version: 3` — the user ran a later
build, then came back to this one — took the no-migration branch with no log line, so
every key the newer schema renamed was silently ignored and the affected settings fell
back to constants. `needs_migration` now logs a WARNING naming both versions, and
`downgrade_note` returns the same information as a note so it reaches the activity log.
The config is still not rewritten: this build cannot know what the newer schema means.

Two documentation defects are closed at the same time. The activity-log promise in
`.env.example` and `README.md` was scoped to migration notes; the coercion warnings
raised on the detection read path are WARNING-level logger records only, and both
documents now say so. And the normative migration rules — the conversion, the
sub-second fallback, the both-spellings rule, the rename set — are stated **here** and
only summarised in `README.md` and `.env.example`, each of which links back to this
file. Three hand-maintained copies of a rule set is how the sub-second rule and the
dead-key rename needed correcting in three documents in one pass.

`DEAD_CONFIG_KEYS` stays in `src/core/constants.py`: it is classification data, no
code branches on it, and the documentation needs one discoverable authoritative
source. The drift that choice risks against the shipped fixture is pinned by
`test_dead_config_keys_agree_with_the_shipped_fixture`, which requires the dead set
plus the three genuinely non-constant live keys to be exactly the fixture's
constant-less entries.

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
`constants.DEAD_CONFIG_KEYS` is now the single source of that list, and a test walks
every module under `src/` looking for a *mapping read* of each shipped fixture key —
`cfg.get('key')` or `cfg['key']`, which is what a reader looks like. Merely naming a
key (in `DEAD_CONFIG_KEYS` itself, in the migration's rename tables, or in a
docstring) is not a reader, which is what stops the declaration — it necessarily
names its own four entries, and it lives under `src/` — from making the check
self-fulfilling. Both directions are pinned: an entry in `DEAD_CONFIG_KEYS` must have
no mapping read anywhere under `src/`, and a shipped fixture key *not* in that set must
have at least one. So the classification cannot drift in either direction, and a
substring-based rewrite of the matcher fails loudly instead of inverting the split.

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
- **Every** timeout key the app *reads* states its unit in its name, so the suffix can
  be relied on by the next reader. The four dead reference entries are the documented
  exemption: nothing reads them, so the migration leaves an existing config's bare
  `*_worker_thread_timeout` spellings alone and issue #104 deletes them.
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

The float config key `threshold_percent` is coerced by
`constants.normalize_threshold_percent`, the float sibling of `normalize_positive_int`.
It was previously a raw `float(cfg.get('threshold_percent', ...))` in the window
constructor, so a hand-edited `"abc"`, `true` or `{}` raised out of
`NudityDetectorWindow.__init__` and the application never started: the one config error
ADD-007's coercion policy was supposed to eliminate was fatal rather than merely silent.
A right hand-edited value is legitimate — but it is never applied silently, because
every rewrite is named in a log record.

The write also preserves the target file's permissions. `tempfile.mkstemp` creates
0600, so installing the temp file with `os.replace` would otherwise quietly narrow a
pre-existing group- or world-readable config to owner-only — a change to the file's
*mode* that this write has no mandate to make. An existing mode is carried across; a
new file gets the process umask, which is what the previous `open(path, 'w')` writer
produced.

**Follow-up (out of scope here):** `nudenet_worker_thread_timeout_seconds` and
`helloz_nsfw_worker_thread_timeout_seconds` ship in the reference tables but are read
by no code, so the migration does **not** rename them. Their earlier `*_seconds` names
were introduced by this PR; renaming a key forward would spend a schema-version bump and
a user-facing change note to rewrite a value nothing consumes, on the premise that the
old key's unit "was always seconds" — a premise no code path can establish, because
nothing ever read it. They are deleted by **issue #104** ("Remove dead timeout config
keys") rather than migrated.

Note also that `_save_config` writes only the 15 live keys, so those reference entries
exist in `.env.example` and `tests/fixtures/app_config.default.json` but are dropped
from a user's own `config/app_config.json` on its first save.
