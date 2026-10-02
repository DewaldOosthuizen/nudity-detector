# ADD-007 — Seconds as the Canonical Timeout Unit

| Field      | Value                          |
|------------|--------------------------------|
| Status     | Accepted                       |
| Date       | 2026-10-02 17:37               |
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

**Seconds is the single canonical timeout unit end to end.** The unit boundary
lives in the core layer, in `src/core/constants.py`:

```python
MILLISECONDS_PER_SECOND = 1000
LEGACY_TIMEOUT_MS_THRESHOLD = 1000

def milliseconds_to_seconds(milliseconds): ...
def normalize_timeout_seconds(value, default_seconds): ...
```

`normalize_timeout_seconds(value, default_seconds)` returns whole seconds,
always `>= 1`; it falls back to `default_seconds` on `None`/`TypeError`/
`ValueError`, and converts any value `>= LEGACY_TIMEOUT_MS_THRESHOLD` as a
legacy millisecond value. `WORKER_THREAD_TIMEOUT = 5` and `DETECT_TIMEOUT = 60`
remain the single source of truth for the defaults, in seconds.

The GUI accessors `_get_worker_thread_timeout()` and `_get_detect_timeout()` in
`src/gui/app.py` are the **documented, single unit boundary**: every configured
or spin-button value passes through `normalize_timeout_seconds()` before it
reaches the threading API. The spin-button labels already read
`Thread Timeout (s)` / `Detect Timeout (s)`, so the accessors make that "s" true
by construction.

The shipped `config/app_config.json`, the `.env.example` reference table, and
the `README.md` config table were corrected to the seconds defaults.

**Migration is manual for the ambiguous value `250`.** Runtime auto-migration is
deliberately *not* applied to `250`, because `250` is both the former
millisecond default and a legal seconds value (the worker spin button accepts up
to 300 s); converting it automatically would silently change a legitimate
250-second configuration. Only unambiguously millisecond-scale values
(`>= 1000`, which the GUI cannot produce) are auto-converted.

---

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| **Seconds everywhere** (current) | Matches the `threading` API and the existing `constants` defaults; one unit end to end; whole seconds fit the GUI spin buttons (1 s minimum) | **Accepted** |
| Keep milliseconds, convert in GUI | Preserves the old ms contract — but the GUI must display milliseconds (worse UX), two units coexist, and a 1 s-minimum spin button cannot represent `250 ms` anyway | Rejected |
| Type-safe wrapper (`timedelta` / `NewType`) | Removes ambiguity entirely — but adds ceremony to a small codebase and does not fit the plain-int config surface | Rejected |

A 250 ms value (0.25 s) cannot even be represented by a 1 s-minimum spin
button, and a 0.25 s detection timeout would skip almost every file — so the
millisecond values were themselves part of the defect, not the intended
behaviour.

---

## Consequences

**Positive:**
- One unit (seconds) across config, constants, GUI, and the `threading` API —
  the mismatch cannot silently recur.
- The unit boundary is explicit, named, documented, and covered by unit tests
  (`tests/core/test_timeout_units_issue91.py`) plus GUI-boundary regression
  tests (`tests/gui/test_scanning_mixin.py::TestTimeoutUnits`).
- Legacy millisecond configs (`>= 1000`) are auto-normalized, so a config set to
  e.g. `2500` yields `3` seconds rather than a 2500-second freeze.

**Negative / Trade-offs:**
- A user who customised `worker_thread_timeout: 250` or `detect_timeout: 250`
  must update those values to `5` and `60` manually; `250` is ambiguous and is
  therefore not auto-migrated. This is documented in `README.md` and
  `.env.example`.
- `normalize_timeout_seconds()` accepts a plain int; it does not carry the unit
  in the type. The naming (`*_seconds`) and the docstrings are the guard.

**Follow-up (out of scope here):** `nudenet_worker_thread_timeout` and
`helloz_nsfw_worker_thread_timeout` are not read by any code (no `src/`
references). Their documentation unit was corrected for consistency but their
removal is a separate cleanup.
