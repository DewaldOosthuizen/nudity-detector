# Development Workflow

## Running Checks Locally

Run these commands before pushing. CI runs the same checks and a failing PR will not be reviewed.

```bash
pytest tests/
pytest --cov=src --cov-report=term-missing --cov-fail-under=80 tests/
pip-audit -r requirements.txt
```

```bash
ruff check src/ tests/
```

If you changed dependencies, regenerate pinned requirements from `requirements.in`, then rerun the tests.

After any code change, keep the repository graph current:

```bash
codegraph sync .
```

All commands must exit with code `0` before opening a PR.

---

## Dependency Management

This project uses a pip-tools two-file workflow to keep dependencies fully pinned and reproducible:

- `requirements.in` — human-edited abstract file with version ranges (source of truth)
- `requirements.txt` — auto-generated lock file produced by pip-compile (do NOT edit by hand)

### Upgrading or adding a dependency

1. Edit `requirements.in` (add a package or widen/tighten a version range).
2. Regenerate the lock file: `pip-compile requirements.in -o requirements.txt`
3. Install from the lock file: `pip install -r requirements.txt`
4. Run the test suite to confirm no regressions: `pytest tests/`
5. Commit both files together: `git add requirements.in requirements.txt && git commit`

Important: never use `pip freeze > requirements.txt`. Always regenerate via pip-compile.

### CPU-only onnxruntime

The project intentionally uses only the CPU-only `onnxruntime` variant. The `vnudenet` package and its `onnxruntime-gpu` transitive dependency are excluded from `requirements.in` because they are unused by this codebase and would add approximately 500 MB of CUDA/cuDNN artifacts to CPU-only installations. The rationale is also documented in a comment above the `nudenet` line in `requirements.in`.
