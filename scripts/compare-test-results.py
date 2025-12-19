#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

FAIL_STATUSES = {"failed", "failure", "error", "timedout", "timedOut", "broken"}
PASS_STATUSES = {"passed", "ok", "success"}
SKIP_STATUSES = {"skipped", "pending", "todo", "disabled", "ignored"}


def parse_args() -> argparse.Namespace:
    default_thresholds = Path(__file__).resolve().parent / "regression-thresholds.json"
    parser = argparse.ArgumentParser(
        description="Compare baseline/updated test artifacts and emit regression summary."
    )
    parser.add_argument("--baseline", type=Path, default=Path("artifacts/baseline"), help="Path to baseline artifacts directory")
    parser.add_argument("--updated", type=Path, default=Path("artifacts/updated"), help="Path to updated artifacts directory")
    parser.add_argument("--output", type=Path, default=Path("artifacts/comparison"), help="Output directory for summary/report")
    parser.add_argument("--thresholds", type=Path, default=default_thresholds, help="Thresholds JSON path")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_latest_file(base: Path, prefix: str) -> Path:
    candidates = sorted(base.glob(f"{prefix}-*.json"))
    if not candidates:
        raise FileNotFoundError(f"No artifacts found for prefix {prefix} in {base}")
    return candidates[-1]


def parse_timestamp_from_name(path: Path) -> str:
    match = re.search(r"(\d{8}-\d{6})", path.name)
    if not match:
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    raw = match.group(1)
    return datetime.strptime(raw, "%Y%m%d-%H%M%S").isoformat() + "Z"


def _float_or_zero(value: object) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_pytest_results(path: Path) -> dict:
    data = load_json(path)
    summary = data.get("summary", {})
    tests: Dict[str, Dict[str, object]] = {}
    for entry in data.get("tests", []):
        nodeid = entry.get("nodeid")
        if not nodeid:
            continue
        status = entry.get("outcome", "unknown")
        duration = _float_or_zero(entry.get("duration"))
        tests[nodeid] = {"status": status, "duration": duration}

    total = summary.get("total") or len(tests) or (
        summary.get("passed", 0)
        + summary.get("failed", 0)
        + summary.get("skipped", 0)
        + summary.get("xfailed", 0)
        + summary.get("xpassed", 0)
        + summary.get("errors", 0)
    )
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0) + summary.get("errors", 0)
    skipped = summary.get("skipped", 0) + summary.get("xfailed", 0) + summary.get("xpassed", 0)
    duration = _float_or_zero(summary.get("duration")) or sum(t["duration"] for t in tests.values())
    return {"total": total, "passed": passed, "failed": failed, "skipped": skipped, "duration": duration, "tests": tests}


def load_jest_results(path: Path) -> dict:
    data = load_json(path)
    tests: Dict[str, Dict[str, object]] = {}
    for suite in data.get("testResults", []):
        file_name = suite.get("name") or suite.get("testFilePath") or "suite"
        for assertion in suite.get("assertionResults", []):
            title = assertion.get("fullName") or assertion.get("title") or "test"
            status = assertion.get("status", "unknown")
            duration = _float_or_zero(assertion.get("duration"))
            test_id = f"{file_name}::{title}"
            tests[test_id] = {"status": status, "duration": duration}

    total = data.get("numTotalTests") or len(tests)
    passed = data.get("numPassedTests") or len([t for t in tests.values() if t["status"] in PASS_STATUSES])
    failed = data.get("numFailedTests") or len([t for t in tests.values() if t["status"] in FAIL_STATUSES])
    skipped = data.get("numPendingTests") or len([t for t in tests.values() if t["status"] in SKIP_STATUSES])
    duration = sum(_float_or_zero(t["duration"]) for t in tests.values())
    return {"total": total, "passed": passed, "failed": failed, "skipped": skipped, "duration": duration, "tests": tests}


def _collect_playwright_tests(suites: Iterable[dict]) -> Dict[str, Dict[str, object]]:
    collected: Dict[str, Dict[str, object]] = {}
    for suite in suites:
        suite_title = suite.get("title") or "suite"
        for spec in suite.get("specs", []):
            spec_title = spec.get("title") or "spec"
            for test in spec.get("tests", []):
                title = test.get("title") or "test"
                status = test.get("status", "unknown")
                duration = _float_or_zero(test.get("duration") or test.get("duration_ms"))
                test_id = f"{suite_title}/{spec_title}::{title}"
                collected[test_id] = {"status": status, "duration": duration}
        nested = suite.get("suites") or []
        collected.update(_collect_playwright_tests(nested))
    return collected


def load_playwright_results(path: Path) -> dict:
    data = load_json(path)
    tests = _collect_playwright_tests(data.get("suites", []))
    total = len(tests)
    passed = len([t for t in tests.values() if t["status"] in PASS_STATUSES])
    failed = len([t for t in tests.values() if t["status"] in FAIL_STATUSES])
    skipped = len([t for t in tests.values() if t["status"] in SKIP_STATUSES])
    duration = sum(_float_or_zero(t["duration"]) for t in tests.values())
    if not duration and "stats" in data:
        duration = _float_or_zero(data["stats"].get("duration"))
    return {"total": total, "passed": passed, "failed": failed, "skipped": skipped, "duration": duration, "tests": tests}


def merge_results(results: List[dict]) -> Tuple[dict, Dict[str, Dict[str, object]]]:
    aggregated = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "duration": 0.0}
    tests: Dict[str, Dict[str, object]] = {}
    for result in results:
        aggregated["total"] += int(result.get("total", 0))
        aggregated["passed"] += int(result.get("passed", 0))
        aggregated["failed"] += int(result.get("failed", 0))
        aggregated["skipped"] += int(result.get("skipped", 0))
        aggregated["duration"] += _float_or_zero(result.get("duration"))
        tests.update(result.get("tests", {}))
    return aggregated, tests


def _percent_from_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().rstrip("%")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def parse_coverage(path: Path) -> dict:
    data = load_json(path)
    global_candidates = []
    if "totals" in data:
        totals = data["totals"]
        for key in ("percent_covered", "percent_covered_display"):
            pct = _percent_from_value(totals.get(key))
            if pct is not None:
                global_candidates.append(pct)
        if "lines" in totals:
            pct = _percent_from_value(totals["lines"].get("pct"))
            if pct is not None:
                global_candidates.append(pct)
    if "total" in data and isinstance(data["total"], dict):
        totals = data["total"]
        for metric in ("lines", "statements"):
            if metric in totals:
                pct = _percent_from_value(totals[metric].get("pct"))
                if pct is not None:
                    global_candidates.append(pct)

    per_file: Dict[str, float] = {}
    for file_path, file_data in data.get("files", {}).items():
        summary = file_data.get("summary", {})
        pct = _percent_from_value(summary.get("percent_covered") or summary.get("percent_covered_display"))
        if pct is None and "lines" in file_data:
            pct = _percent_from_value(file_data["lines"].get("pct"))
        if pct is not None:
            per_file[file_path] = pct

    for key, value in data.items():
        if key in {"meta", "totals", "total"} or not isinstance(value, dict):
            continue
        if "lines" in value:
            pct = _percent_from_value(value["lines"].get("pct"))
            if pct is not None:
                per_file[key] = pct

    global_coverage = sum(global_candidates) / len(global_candidates) if global_candidates else None
    return {"global": global_coverage, "files": per_file}


def combine_coverages(entries: Iterable[dict]) -> dict:
    globals_: List[float] = []
    files: Dict[str, float] = {}
    for entry in entries:
        if not entry:
            continue
        if entry.get("global") is not None:
            globals_.append(entry["global"])
        files.update(entry.get("files", {}))
    global_average = sum(globals_) / len(globals_) if globals_ else None
    return {"global": global_average, "files": files}


def collect_artifacts(base_dir: Path) -> dict:
    loaders = [
        ("pytest-results", load_pytest_results),
        ("jest-results", load_jest_results),
        ("playwright-results", load_playwright_results),
    ]
    results: List[dict] = []
    tests: Dict[str, Dict[str, object]] = {}
    timestamp_source: Path | None = None

    for prefix, loader in loaders:
        try:
            path = find_latest_file(base_dir, prefix)
        except FileNotFoundError:
            continue
        timestamp_source = timestamp_source or path
        result = loader(path)
        results.append(result)

    stats, test_map = merge_results(results)
    tests.update(test_map)

    coverage_entries = []
    for prefix in ("coverage-backend", "coverage-frontend"):
        try:
            coverage_path = find_latest_file(base_dir, prefix)
        except FileNotFoundError:
            continue
        coverage_entries.append(parse_coverage(coverage_path))

    coverage = combine_coverages(coverage_entries)
    timestamp = parse_timestamp_from_name(timestamp_source) if timestamp_source else datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return {"stats": stats, "tests": tests, "coverage": coverage, "timestamp": timestamp}


def diff_tests(baseline: Dict[str, Dict[str, object]], updated: Dict[str, Dict[str, object]]) -> Tuple[List[str], List[str], List[str]]:
    new_failures: List[str] = []
    resolved: List[str] = []
    flaky: List[str] = []

    for test_id, base in baseline.items():
        base_status = str(base.get("status", "")).lower()
        updated_status = str(updated.get(test_id, {}).get("status", "")).lower()

        if base_status in FAIL_STATUSES and updated_status not in FAIL_STATUSES:
            resolved.append(test_id)
        if base_status not in FAIL_STATUSES and updated_status in FAIL_STATUSES:
            new_failures.append(test_id)
        if updated_status and base_status and base_status != updated_status:
            flaky.append(test_id)

    for test_id, upd in updated.items():
        if test_id in baseline:
            continue
        if str(upd.get("status", "")).lower() in FAIL_STATUSES:
            new_failures.append(test_id)

    return sorted(set(new_failures)), sorted(set(resolved)), sorted(set(flaky))


def evaluate_coverage(baseline: dict, updated: dict, critical_paths: Iterable[str], critical_threshold: float, global_threshold: float) -> Tuple[float, bool, Dict[str, dict]]:
    baseline_global = baseline.get("global")
    updated_global = updated.get("global")
    delta_percent = (updated_global - baseline_global) if baseline_global is not None and updated_global is not None else 0.0

    critical_details: Dict[str, dict] = {}
    worst_drop = 0.0
    for critical in critical_paths:
        base_candidates = {path: pct for path, pct in baseline.get("files", {}).items() if path.startswith(critical)}
        updated_candidates = {path: pct for path, pct in updated.get("files", {}).items() if path.startswith(critical)}
        for path, base_pct in base_candidates.items():
            if path not in updated_candidates:
                continue
            updated_pct = updated_candidates[path]
            delta = updated_pct - base_pct
            worst_drop = min(worst_drop, delta)
            critical_details[path] = {"baseline": base_pct, "updated": updated_pct, "delta": delta}

    coverage_ok = True
    if baseline_global is not None and updated_global is not None:
        coverage_ok = delta_percent >= -global_threshold
    critical_ok = worst_drop >= -critical_threshold
    return delta_percent, coverage_ok and critical_ok, critical_details


def build_summary(baseline: dict, updated: dict, thresholds: dict) -> dict:
    new_failures, resolved, flaky = diff_tests(baseline["tests"], updated["tests"])
    delta_runtime = 0.0
    if baseline["stats"]["duration"]:
        delta_runtime = ((updated["stats"]["duration"] - baseline["stats"]["duration"]) / baseline["stats"]["duration"]) * 100

    coverage_delta, coverage_ok, critical_details = evaluate_coverage(
        baseline["coverage"],
        updated["coverage"],
        thresholds.get("critical_paths", []),
        float(thresholds.get("coverage_drop_critical", 1.0)),
        float(thresholds.get("coverage_drop_global", 0.5)),
    )

    acceptance = {
        "execution_time_within_threshold": abs(delta_runtime) <= float(thresholds.get("runtime_tolerance_percent", 10.0)),
        "no_new_failures": len(new_failures) <= int(thresholds.get("max_new_failures", 0)),
        "flaky_within_limit": len(flaky) <= int(thresholds.get("max_new_flaky", 3)),
        "coverage_within_threshold": coverage_ok,
    }
    acceptance["overall_pass"] = all(acceptance.values())

    return {
        "baseline_timestamp": baseline["timestamp"],
        "updated_timestamp": updated["timestamp"],
        "total_tests": {"baseline": baseline["stats"]["total"], "updated": updated["stats"]["total"]},
        "passes": {"baseline": baseline["stats"]["passed"], "updated": updated["stats"]["passed"]},
        "failures": {"baseline": baseline["stats"]["failed"], "updated": updated["stats"]["failed"]},
        "skipped": {"baseline": baseline["stats"]["skipped"], "updated": updated["stats"]["skipped"]},
        "new_failures": new_failures,
        "resolved_failures": resolved,
        "flaky_tests": flaky,
        "execution_time": {
            "baseline": baseline["stats"]["duration"],
            "updated": updated["stats"]["duration"],
            "delta_percent": delta_runtime,
        },
        "coverage": {
            "baseline_global": baseline["coverage"].get("global"),
            "updated_global": updated["coverage"].get("global"),
            "delta_percent": coverage_delta,
            "critical": critical_details,
        },
        "acceptance": acceptance,
    }


def write_summary(summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "regression-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


def write_report(summary: dict, output_dir: Path) -> None:
    lines: List[str] = []
    lines.append("# 回帰レポート / Regression Report")
    lines.append("")
    lines.append("## サマリー")
    lines.append(f"- ベースライン: {summary['baseline_timestamp']}")
    lines.append(f"- 比較対象: {summary['updated_timestamp']}")
    lines.append(f"- 合計テスト: {summary['total_tests']['baseline']} → {summary['total_tests']['updated']}")
    lines.append(
        f"- 実行時間: {summary['execution_time']['baseline']:.2f}s → {summary['execution_time']['updated']:.2f}s "
        f"(Δ {summary['execution_time']['delta_percent']:.2f}%)"
    )
    if summary["coverage"]["baseline_global"] is not None and summary["coverage"]["updated_global"] is not None:
        lines.append(
            f"- カバレッジ: {summary['coverage']['baseline_global']:.2f}% → {summary['coverage']['updated_global']:.2f}% "
            f"(Δ {summary['coverage']['delta_percent']:.2f}%)"
        )
    lines.append(f"- 判定: {'PASS' if summary['acceptance']['overall_pass'] else 'FAIL'}")
    lines.append("")

    lines.append("## リグレッション (新規失敗)")
    if summary["new_failures"]:
        for item in summary["new_failures"]:
            lines.append(f"- {item}")
    else:
        lines.append("- なし")
    lines.append("")

    lines.append("## 解消された失敗")
    if summary["resolved_failures"]:
        for item in summary["resolved_failures"]:
            lines.append(f"- {item}")
    else:
        lines.append("- なし")
    lines.append("")

    lines.append("## Flaky Tests")
    if summary["flaky_tests"]:
        for item in summary["flaky_tests"]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## しきい値判定")
    lines.append(f"- 実行時間しきい値: {summary['acceptance']['execution_time_within_threshold']}")
    lines.append(f"- 新規失敗: {summary['acceptance']['no_new_failures']}")
    lines.append(f"- Flaky 許容: {summary['acceptance']['flaky_within_limit']}")
    lines.append(f"- カバレッジ低下: {summary['acceptance']['coverage_within_threshold']}")

    report_path = output_dir / "regression-report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    baseline_dir = args.baseline
    updated_dir = args.updated
    output_dir = args.output

    if not baseline_dir.exists() or not updated_dir.exists():
        print(f"ERROR: Baseline or updated directory missing ({baseline_dir}, {updated_dir})", file=sys.stderr)
        return 2

    try:
        thresholds = load_json(args.thresholds) if args.thresholds.exists() else {}
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Failed to load thresholds: {exc}", file=sys.stderr)
        return 2

    baseline = collect_artifacts(baseline_dir)
    updated = collect_artifacts(updated_dir)
    summary = build_summary(baseline, updated, thresholds)
    write_summary(summary, output_dir)
    write_report(summary, output_dir)

    if summary["acceptance"]["overall_pass"]:
        print("Regression check PASS")
        return 0

    print("Regression check FAIL", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
