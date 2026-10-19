# ADD-009 — Restartable Inference Workers

| Field      | Value                  |
|------------|------------------------|
| Status     | Accepted               |
| Date       | 2026-10-16 16:24       |
| Author     | Codex                  |
| Relates to | ADD-003, ADD-007       |

---

## Context

The GUI wrapped NudeNet inference in daemon threads and returned after a join
timeout. Python cannot safely stop a running thread, so the inference continued
after its frame was skipped. Repeated timeouts could leave native runtime work
using CPU and memory after the scan had moved on.

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| Keep thread timeout | Returns to the scan while native inference continues | Rejected: does not cancel work or release its resources |
| Start one process per image | A timed-out process can be terminated | Rejected: reloads the ONNX model for every image/frame |
| Reusable restartable process workers | Load one detector per worker; terminate only the timed-out worker and restore its slot | **Accepted** |
| In-process ONNX cancellation | Delegate cancellation to the runtime | Rejected: the current NudeNet API exposes no supported cancellation operation |

## Decision

Run each GUI NudeNet worker slot in a child process. A child loads one detector
and handles requests serially. On timeout, the parent terminates and joins that
child before returning the slot; the next request starts a fresh process. Scan
teardown stops all remaining child processes, including work still active after
the file-worker join deadline.

## Consequences

**Positive:**
- A timed-out inference cannot continue after its caller returns.
- A worker slot is not reused until its previous process is terminated.
- Successful detections reuse the loaded model within the child process.
- Process lifecycle is covered by deterministic tests without downloading model
  weights or requiring a GPU.

**Negative / Trade-offs:**
- Each configured worker loads its own model, increasing memory use compared
  with sharing one in-process detector.
- A timeout discards the worker's model, so the next request pays model startup
  cost.
- Child-process exceptions cross the boundary as a typed message and are
  reported as `RemoteDetectionError` in the parent.
