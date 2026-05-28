"""Run k6 security flood evaluation and persist summarized artifacts.

This script is intentionally separate from pytest. It requires `k6` to be
installed on the host and a running backend API.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCRIPT = BACKEND_DIR / "load_tests" / "auth_chat_flood_test.js"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "data" / "security_eval"


def _metric_value(summary: dict, metric_name: str, field: str, default=0):
    metric = summary.get("metrics", {}).get(metric_name, {})
    if field in metric:
        return metric.get(field, default)
    values = metric.get("values", {})
    return values.get(field, default)


def _check_result(summary: dict, check_name: str, field: str) -> int:
    check = summary.get("root_group", {}).get("checks", {}).get(check_name, {})
    return int(check.get(field, 0))


def _verdict(report: dict) -> str:
    if report["error_status_count"] > 0 or report["checks_failed"] > 0:
        return "NEEDS_ATTENTION"
    if report["dropped_iterations"] > 0:
        return "DEGRADED"
    return "PASS"


def _write_report(summary_path: Path, report_path: Path) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary_source": str(summary_path),
        "qps": _metric_value(summary, "http_reqs", "rate"),
        "total_requests": _metric_value(summary, "http_reqs", "count"),
        "avg_latency_ms": _metric_value(summary, "http_req_duration", "avg"),
        "p95_latency_ms": _metric_value(summary, "http_req_duration", "p(95)"),
        "status_429_count": _metric_value(summary, "status_429_count", "count"),
        "error_status_count": _metric_value(summary, "error_status_count", "count"),
        "http_req_failed_rate": _metric_value(summary, "http_req_failed", "rate"),
        "http_req_failed_value": _metric_value(summary, "http_req_failed", "value"),
        "auth_rate_limited_rate": _metric_value(summary, "auth_rate_limited", "rate"),
        "auth_rate_limited_value": _metric_value(summary, "auth_rate_limited", "value"),
        "chat_rejected_or_limited_rate": _metric_value(summary, "chat_rejected_or_limited", "rate"),
        "chat_rejected_or_limited_value": _metric_value(summary, "chat_rejected_or_limited", "value"),
        "normal_login_success_rate": _metric_value(summary, "normal_login_succeeded", "rate"),
        "normal_login_success_value": _metric_value(summary, "normal_login_succeeded", "value"),
        "brute_force_rejected_rate": _metric_value(summary, "brute_force_rejected", "rate"),
        "brute_force_rejected_value": _metric_value(summary, "brute_force_rejected", "value"),
        "authorized_chat_handled_rate": _metric_value(summary, "authorized_chat_handled", "rate"),
        "authorized_chat_handled_value": _metric_value(summary, "authorized_chat_handled", "value"),
        "unauthorized_chat_rejected_rate": _metric_value(summary, "unauthorized_chat_rejected", "rate"),
        "unauthorized_chat_rejected_value": _metric_value(summary, "unauthorized_chat_rejected", "value"),
        "dropped_iterations": _metric_value(summary, "dropped_iterations", "count"),
        "checks_passed": _metric_value(summary, "checks", "passes"),
        "checks_failed": _metric_value(summary, "checks", "fails"),
        "failed_login_check_passes": _check_result(summary, "failed login is rejected or rate-limited", "passes"),
        "failed_login_check_fails": _check_result(summary, "failed login is rejected or rate-limited", "fails"),
        "chat_protection_check_passes": _check_result(summary, "chat request is handled according to auth/rate-limit policy", "passes"),
        "chat_protection_check_fails": _check_result(summary, "chat request is handled according to auth/rate-limit policy", "fails"),
    }
    report["overall_verdict"] = _verdict(report)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run k6 OWASP API security flood evaluation")
    parser.add_argument("--script", default=str(DEFAULT_SCRIPT), help="Path to k6 script")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for artifacts")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary_path = output_dir / f"k6_security_summary_{timestamp}.json"
    report_path = output_dir / f"k6_security_report_{timestamp}.json"

    command = [
        "k6",
        "run",
        "--summary-export",
        str(summary_path),
        "-e",
        f"BASE_URL={args.base_url}",
        args.script,
    ]
    result = subprocess.run(command, cwd=BACKEND_DIR, check=False)
    if summary_path.exists():
        _write_report(summary_path, report_path)
        print(f"k6 summary written to: {summary_path}")
        print(f"security metrics report written to: {report_path}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
