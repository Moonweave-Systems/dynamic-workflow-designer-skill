import json
import subprocess
import sys
from pathlib import Path


def test_summary_reports_decision_and_valid(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "status.json").write_text(
        json.dumps({"decision": "verified-complete", "valid": True}),
        encoding="utf-8",
    )
    out_path = tmp_path / "summary.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/keelplane_run_summary.py",
            "--run",
            str(run_dir),
            "--out",
            str(out_path),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(out_path.read_text(encoding="utf-8"))
    assert summary["decision"] == "verified-complete"
    assert summary["valid"] is True

