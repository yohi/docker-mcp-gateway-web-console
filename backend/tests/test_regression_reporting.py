from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_fake_docker_for_capture(path: Path, exec_log: Path, cp_log: Path) -> None:
    content = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail

        echo "$@" >> "{exec_log}"

        if [ "${{1:-}}" != "compose" ]; then
          exit 0
        fi

        shift
        while [ "${{1:-}}" = "-f" ]; do
          shift 2 || break
        done

        action="${{1:-}}"
        shift || true

        if [ "$action" = "ps" ]; then
          echo "backend"
          echo "frontend"
          exit 0
        fi

        if [ "$action" = "exec" ]; then
          if [ "${{1:-}}" = "-T" ]; then
            shift
          fi
          service="${{1:-}}"
          shift || true
          echo "exec:${{service}}:${{*}}" >> "{exec_log}"
          exit 0
        fi

        if [ "$action" = "cp" ]; then
          src="${{1:-}}"
          dest="${{2:-}}"
          mkdir -p "$(dirname "$dest")"
          echo '{{"copied_from":"'"$src"'"}}' > "$dest"
          echo "cp:${{src}}:${{dest}}" >> "{cp_log}"
          exit 0
        fi

        exit 0
        """
    )
    _write_executable(path, content)


def _write_sample_results(base_dir: Path, *, prefix: str) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)

    (base_dir / f"pytest-results-{prefix}.json").write_text(
        json.dumps(
            {
                "summary": {"passed": 2, "failed": 1, "skipped": 0, "duration": 3.0},
                "tests": [
                    {"nodeid": "tests/test_api.py::test_ok", "outcome": "passed", "duration": 1.1},
                    {"nodeid": "tests/test_api.py::test_other", "outcome": "passed", "duration": 1.2},
                    {"nodeid": "tests/test_api.py::test_flaky", "outcome": "failed", "duration": 0.7},
                ],
            }
        ),
        encoding="utf-8",
    )

    (base_dir / f"coverage-backend-{prefix}.json").write_text(
        json.dumps(
            {
                "totals": {"percent_covered": 85.0},
                "files": {
                    "backend/app/core/service.py": {"summary": {"percent_covered": 90.0}},
                    "backend/app/services/worker.py": {"summary": {"percent_covered": 80.0}},
                },
            }
        ),
        encoding="utf-8",
    )

    (base_dir / f"jest-results-{prefix}.json").write_text(
        json.dumps(
            {
                "numTotalTests": 2,
                "numPassedTests": 1,
                "numFailedTests": 1,
                "numPendingTests": 0,
                "testResults": [
                    {
                        "name": "app.test.tsx",
                        "assertionResults": [
                            {"fullName": "renders ok", "status": "passed", "duration": 0.2},
                            {"fullName": "handles error", "status": "failed", "duration": 0.3},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    (base_dir / f"coverage-frontend-{prefix}.json").write_text(
        json.dumps(
            {
                "total": {"lines": {"pct": 82.0}},
                "frontend/src/components/Widget.tsx": {"lines": {"pct": 88.0}},
            }
        ),
        encoding="utf-8",
    )

    (base_dir / f"playwright-results-{prefix}.json").write_text(
        json.dumps(
            {
                "suites": [
                    {
                        "title": "suite",
                        "specs": [
                            {
                                "title": "spec",
                                "tests": [
                                    {"title": "flows", "status": "passed", "duration": 1.0},
                                    {"title": "slow", "status": "failed", "duration": 1.5},
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_updated_results(base_dir: Path, *, prefix: str) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)

    (base_dir / f"pytest-results-{prefix}.json").write_text(
        json.dumps(
            {
                "summary": {"passed": 3, "failed": 0, "skipped": 0, "duration": 3.2},
                "tests": [
                    {"nodeid": "tests/test_api.py::test_ok", "outcome": "passed", "duration": 1.1},
                    {"nodeid": "tests/test_api.py::test_other", "outcome": "passed", "duration": 1.1},
                    {"nodeid": "tests/test_api.py::test_flaky", "outcome": "passed", "duration": 1.0},
                ],
            }
        ),
        encoding="utf-8",
    )

    (base_dir / f"coverage-backend-{prefix}.json").write_text(
        json.dumps(
            {
                "totals": {"percent_covered": 84.8},
                "files": {
                    "backend/app/core/service.py": {"summary": {"percent_covered": 89.5}},
                    "backend/app/services/worker.py": {"summary": {"percent_covered": 80.2}},
                },
            }
        ),
        encoding="utf-8",
    )

    (base_dir / f"jest-results-{prefix}.json").write_text(
        json.dumps(
            {
                "numTotalTests": 2,
                "numPassedTests": 2,
                "numFailedTests": 0,
                "numPendingTests": 0,
                "testResults": [
                    {
                        "name": "app.test.tsx",
                        "assertionResults": [
                            {"fullName": "renders ok", "status": "passed", "duration": 0.18},
                            {"fullName": "handles error", "status": "passed", "duration": 0.25},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    (base_dir / f"coverage-frontend-{prefix}.json").write_text(
        json.dumps(
            {
                "total": {"lines": {"pct": 81.7}},
                "frontend/src/components/Widget.tsx": {"lines": {"pct": 87.4}},
            }
        ),
        encoding="utf-8",
    )

    (base_dir / f"playwright-results-{prefix}.json").write_text(
        json.dumps(
            {
                "suites": [
                    {
                        "title": "suite",
                        "specs": [
                            {
                                "title": "spec",
                                "tests": [
                                    {"title": "flows", "status": "passed", "duration": 0.9},
                                    {"title": "slow", "status": "passed", "duration": 1.2},
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_thresholds(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "runtime_tolerance_percent": 10.0,
                "coverage_drop_global": 0.5,
                "coverage_drop_critical": 1.0,
                "max_new_failures": 0,
                "max_new_flaky": 3,
                "critical_paths": ["backend/app/core", "frontend/src/components"],
            }
        ),
        encoding="utf-8",
    )


def test_capture_baseline_script_runs_and_copies_artifacts(tmp_path: Path) -> None:
    repo_root = _repo_root()
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("version: '3.8'\nservices:\n  backend:\n  frontend:\n", encoding="utf-8")

    exec_log = tmp_path / "docker.log"
    cp_log = tmp_path / "docker-cp.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker_for_capture(fake_bin / "docker", exec_log, cp_log)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["COMPOSE_FILE"] = str(compose_file)
    env["CI"] = "true"
    env["REGRESSION_TIMESTAMP"] = "20250119-101500"

    script_under_test = repo_root / "scripts" / "capture-baseline.sh"
    result = subprocess.run(
        ["bash", str(script_under_test), "baseline"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, textwrap.dedent(
        f"""
        Expected success but got exit code {result.returncode}
        --- stdout ---
        {result.stdout}
        --- stderr ---
        {result.stderr}
        """
    )

    artifacts = tmp_path / "artifacts" / "baseline"
    expected_names = [
        "pytest-results-20250119-101500.json",
        "coverage-backend-20250119-101500.json",
        "jest-results-20250119-101500.json",
        "coverage-frontend-20250119-101500.json",
        "playwright-results-20250119-101500.json",
    ]
    for name in expected_names:
        assert (artifacts / name).exists(), f"Missing artifact: {name}"

    exec_lines = exec_log.read_text(encoding="utf-8").splitlines()
    assert any("exec:backend:pytest" in line for line in exec_lines), "pytest should be executed in backend"
    assert any("exec:frontend:npm test -- --json" in line for line in exec_lines), "frontend jest should run"
    assert any("exec:frontend:npm run test:e2e" in line for line in exec_lines), "playwright should run"
    assert any("-T" in line for line in exec_lines), "-T flag expected in CI mode"

    cp_lines = cp_log.read_text(encoding="utf-8").splitlines()
    assert any("pytest-baseline" in line or "pytest-results" in line for line in cp_lines), "pytest results not copied"
    assert any("jest-results" in line for line in cp_lines), "jest results not copied"
    assert any("playwright-results" in line for line in cp_lines), "playwright results not copied"


def test_compare_script_emits_summary_and_report(tmp_path: Path) -> None:
    repo_root = _repo_root()
    baseline_dir = tmp_path / "artifacts" / "baseline"
    updated_dir = tmp_path / "artifacts" / "updated"
    comparison_dir = tmp_path / "artifacts" / "comparison"
    thresholds_path = tmp_path / "scripts" / "regression-thresholds.json"

    _write_sample_results(baseline_dir, prefix="20250118-143000")
    _write_updated_results(updated_dir, prefix="20250119-101500")
    _write_thresholds(thresholds_path)

    script_under_test = repo_root / "scripts" / "compare-test-results.py"
    result = subprocess.run(
        [sys.executable, str(script_under_test), "--baseline", str(baseline_dir), "--updated", str(updated_dir), "--output", str(comparison_dir), "--thresholds", str(thresholds_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, textwrap.dedent(
        f"""
        Expected success but got exit code {result.returncode}
        --- stdout ---
        {result.stdout}
        --- stderr ---
        {result.stderr}
        """
    )

    summary_path = comparison_dir / "regression-summary.json"
    report_path = comparison_dir / "regression-report.md"
    assert summary_path.exists(), "Summary JSON not created"
    assert report_path.exists(), "Markdown report not created"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["total_tests"]["baseline"] == 7
    assert summary["total_tests"]["updated"] == 7
    assert "tests/test_api.py::test_flaky" in summary["resolved_failures"]
    assert summary["acceptance"]["overall_pass"] is True
    assert summary["coverage"]["delta_percent"] >= -0.5

    report_text = report_path.read_text(encoding="utf-8")
    assert "回帰" in report_text or "regression" in report_text.lower()
    assert "flaky" in report_text.lower()


def test_compare_script_fails_on_new_regressions(tmp_path: Path) -> None:
    repo_root = _repo_root()
    baseline_dir = tmp_path / "artifacts" / "baseline"
    updated_dir = tmp_path / "artifacts" / "updated"
    comparison_dir = tmp_path / "artifacts" / "comparison"
    thresholds_path = tmp_path / "scripts" / "regression-thresholds.json"
    _write_thresholds(thresholds_path)

    _write_sample_results(baseline_dir, prefix="20250118-143000")
    _write_sample_results(updated_dir, prefix="20250119-101500")

    updated_pytest = json.loads((updated_dir / "pytest-results-20250119-101500.json").read_text(encoding="utf-8"))
    updated_pytest["tests"][0]["outcome"] = "failed"
    updated_pytest["summary"]["failed"] = 2
    updated_pytest["summary"]["passed"] = 1
    (updated_dir / "pytest-results-20250119-101500.json").write_text(json.dumps(updated_pytest), encoding="utf-8")

    script_under_test = repo_root / "scripts" / "compare-test-results.py"
    result = subprocess.run(
        [sys.executable, str(script_under_test), "--baseline", str(baseline_dir), "--updated", str(updated_dir), "--output", str(comparison_dir), "--thresholds", str(thresholds_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0, "Regression should produce non-zero exit code"

    summary_path = comparison_dir / "regression-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["acceptance"]["overall_pass"] is False
    assert any("test_api.py::test_ok" in failure for failure in summary["new_failures"]), "new failure should be recorded"
