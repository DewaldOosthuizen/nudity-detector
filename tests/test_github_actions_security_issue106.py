"""Regression tests for issue #106 GitHub Actions security policy."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATHS = (
    ROOT / ".github/workflows/pr_gate.yml",
    ROOT / ".github/workflows/release.yml",
)
EXPECTED_ACTIONS = {
    "actions/checkout": ("11d5960a326750d5838078e36cf38b85af677262", "v4.4.0", 8),
    "actions/setup-python": ("a26af69be951a213d495a4c3e4e4022e16d87065", "v5.6.0", 7),
    "actions/upload-artifact": ("ea165f8d65b6e75b540449e92b4886f43607fa02", "v4.6.2", 1),
    "actions/download-artifact": ("d3f86a106a0bac45b974a628896c90dbdf5c8093", "v4.3.0", 1),
    "softprops/action-gh-release": ("3bb12739c298aeb8a4eeaf626c5b8d85266b0e65", "v2.6.2", 1),
}


def test_all_workflow_actions_use_verified_sha_and_release_comment():
    """Require every workflow action reference to match its verified release pin."""
    action_lines = [
        line.strip()
        for workflow_path in WORKFLOW_PATHS
        for line in workflow_path.read_text(encoding="utf-8").splitlines()
        if re.search(r"\buses:\s*", line)
    ]

    assert len(action_lines) == sum(expected[2] for expected in EXPECTED_ACTIONS.values())
    for action, (sha, version, expected_count) in EXPECTED_ACTIONS.items():
        matching_lines = [line for line in action_lines if f"uses: {action}@" in line]
        assert len(matching_lines) == expected_count
        assert all(f"uses: {action}@{sha} # {version}" in line for line in matching_lines)

    assert all(re.search(r"uses:\s+[^@\s]+@[0-9a-f]{40}\s+#\s+v\d", line) for line in action_lines)


def test_release_write_permission_is_limited_to_publishing_job():
    """Keep write access off workflow scope and grant it only to release publishing."""
    release_workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert re.search(r"(?m)^permissions:\n  contents: read$", release_workflow)
    assert re.search(r"(?m)^  version-tag-release:\n(?:.*\n)*?    permissions:\n      contents: write$", release_workflow)
    assert release_workflow.count("contents: write") == 1


def test_dependabot_configures_monthly_github_actions_updates():
    """Retain pip updates while enabling monthly GitHub Actions proposals."""
    dependabot = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")

    assert "- package-ecosystem: pip\n    directory: /\n    schedule:\n      interval: monthly" in dependabot
    assert "- package-ecosystem: github-actions\n    directory: /\n    schedule:\n      interval: monthly" in dependabot


def test_ci_documentation_defines_action_pin_review_policy():
    """Document exact-tag SHA verification, review gates, and permission scope."""
    documentation = (ROOT / "docs/index.md").read_text(encoding="utf-8")
    required_phrases = (
        "### GitHub Actions pinning and updates",
        "verified full commit SHA",
        "specific release tag",
        "monthly GitHub Actions updates",
        "version-to-SHA mapping",
        "repository PR validation gates",
        "Only the release-publishing job receives `contents: write`.",
    )

    assert all(phrase in documentation for phrase in required_phrases)
