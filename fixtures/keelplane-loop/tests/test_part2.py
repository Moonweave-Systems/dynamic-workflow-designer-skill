import hashlib
import json
import subprocess
import sys
from pathlib import Path


def test_summary_reports_artifact_count_and_source_hash(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source = run_dir / "source.txt"
    source.write_text("keelplane\n", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"decision": "verified-complete", "valid": True}),
        encoding="utf-8",
    )
    (run_dir / "ledger.json").write_text("[]\n", encoding="utf-8")
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
    assert summary["artifact_count"] == 3
    assert summary["source_hash"] == hashlib.sha256(b"keelplane\n").hexdigest()

