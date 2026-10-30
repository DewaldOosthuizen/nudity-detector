# ADD-010 — Helloz NSFW scheme validation and connection-testing GUI controls

| Field      | Value                                 |
|------------|---------------------------------------|
| Status     | Accepted                              |
| Date       | 2026-10-30                            |
| Author     | Dewald Oosthuizen                     |
| Relates to | ADD-001, ADD-002, ADD-006, ADD-007  |

---

## Context

The Helloz NSFW endpoint settings (host, port, API endpoint, and the two
Helloz timeouts) are shipped as a read-only manual-JSON configuration, and the
GUI settings tab exposes most of them but omits two things: the
`helloz_nsfw_scheme` selector and a way to validate connectivity without
persisting.

`helloz_nsfw_scheme` is the user's only escape hatch that forces HTTPS on a
remote deployment. A hand-edited config, or a transient server outage, can
silently leave the endpoint unreachable. The existing read-only-JSON config also
meant the scheme could not be changed through the GUI at all.

At the same time, the GUI settings tab already exposes most of the Helloz
connection fields, so a connection-testing control should be independent of
saving — a full scan must never be required just to check reachability.

---

## Decision

The scheme rule is single-sourced in `src/core/constants.py`:

- `_validate_scheme(scheme, host)` raises `ValueError` when the scheme is `http`
  and the host is not a loopback address (`localhost`, `127.0.0.1`, `::1`).
- `resolve_scheme(host, scheme=None)` honours an explicit override and calls
  `_validate_scheme`, so the loopback guard is enforced at every site that
  builds a Helloz URL — the detection read path (`_load_helloz_config`) and
  the GUI URL builders.

The GUI exposes the scheme through a **Scheme** dropdown (with `http`/`https`
strings) placed directly below the Host entry in the Helloz NSFW frame of the
Settings tab. The dropdown's `notify::selected` signal writes the selected
value into the in-memory config, and `_get_helloz_nsfw_scheme` reads it back
for every URL build.

`_save_config` now validates the fully resolved Helloz URL (via
`_get_helloz_nsfw_url`) before writing anything. On `ValueError` it shows an
actionable `_show_error` dialog naming the problem and returns without writing,
so an insecure resolved configuration is rejected and `config/app_config.json`
is untouched.

The **Test Connection** button probes the health-check URL with `requests` on
a worker thread using the health-check timeout, and marshals the result back
to the main thread with `GLib.idle_add` (see ADD-006 for the thread-safety
rationale). `_do_helloz_test` catches any `requests.RequestException` and
reports only through the activity log and dialogs — it never calls
`_save_config` and never writes `config/app_config.json`.

---

## Consequences

### Positive

- A remote (`non-loopback`) host can only be used with `https`, enforced in
  one place — the loopback guard cannot be bypassed through the GUI getter
  paths or the URL builders.
- Users can change the scheme and test connectivity without saving, so a
  transient server outage or a wrong scheme choice cannot silently discard
  valid settings.
- All Helloz URL construction (detection backend and GUI) routes through the
  same `resolve_scheme`/`_validate_scheme` rule, eliminating divergent
  behaviour between the two paths.

### Negative

- The scheme rule is now a hard constraint: any future code that builds a
  Helloz URL must route through `resolve_scheme` or the loopback guard may
  silently diverge.
- The test-connection control is asynchronous and reports only through the
  GUI (log and dialog), so programmatic callers that need the probe result
  must either poll the activity log or call the connection-check URL
  directly.

### Bias to the status quo

- No new dependencies are introduced. The test probe uses `requests` (already
  a dependency) and `threading` + `GLib.idle_add` (already used elsewhere in
  the GUI for scan progress).
- The config file schema is unchanged for the persisted keys; `helloz_nsfw_scheme`
  is written explicitly by `_save_config` and preserved verbatim for keys the
  GUI does not own.
