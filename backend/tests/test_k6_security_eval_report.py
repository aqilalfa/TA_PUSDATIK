import json
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.run_k6_security_eval import _write_report


def test_write_report_reads_k6_direct_metric_fields(tmp_path):
    summary_path = tmp_path / "summary.json"
    report_path = tmp_path / "report.json"
    summary_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "http_reqs": {"count": 672, "rate": 8.477490087675793},
                    "http_req_duration": {"avg": 12912.5122, "p(95)": 25420.4271},
                    "status_429_count": {"count": 164, "rate": 2.0689},
                    "error_status_count": {"count": 186, "rate": 2.3464},
                    "http_req_failed": {"value": 1},
                    "auth_rate_limited": {"value": 0.4456521739},
                    "chat_rejected_or_limited": {"value": 1},
                    "dropped_iterations": {"count": 1128},
                    "checks": {"passes": 854, "fails": 186, "value": 0.8211538461},
                },
                "root_group": {
                    "checks": {
                        "failed login is rejected or rate-limited": {"passes": 182, "fails": 186},
                        "unauthorized chat request is rejected or rate-limited": {"passes": 304, "fails": 0},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    _write_report(summary_path, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["qps"] == 8.477490087675793
    assert report["p95_latency_ms"] == 25420.4271
    assert report["status_429_count"] == 164
    assert report["error_status_count"] == 186
    assert report["dropped_iterations"] == 1128
    assert report["checks_failed"] == 186
    assert report["overall_verdict"] == "NEEDS_ATTENTION"
