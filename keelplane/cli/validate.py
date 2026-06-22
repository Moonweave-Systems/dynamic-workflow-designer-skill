"""keelplane validate — validate a plan.json against the schema."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from keelplane.core.plan_schema import load_plan, validate_plan, validate_plan_strict, format_errors


def run(args: argparse.Namespace) -> None:
    if args.self_test:
        _self_test()
        return

    plan_path = args.plan
    if not plan_path:
        print("Usage: keelplane validate <plan.json>")
        sys.exit(1)

    path = Path(plan_path)
    if not path.exists():
        print(f"Error: file not found: {path}")
        sys.exit(1)

    try:
        plan = load_plan(str(path))
    except Exception as e:
        print(f"Error: cannot load plan: {e}")
        sys.exit(1)

    errors = validate_plan_strict(plan)
    print(format_errors(errors))
    sys.exit(1 if errors else 0)


def _self_test() -> None:
    """Run a basic self-test."""
    import sys
    print("keelplane validate --self-test")
    tests = 0
    passed = 0

    # Test 1: lightweight check accepts minimal plan
    tests += 1
    valid_plan = {
        "schema_version": "0.5",
        "plan_id": "self-test",
        "created_by": "keelplane",
        "source_prompt": "self-test",
        "activation": {"decision": "activate", "matched_thresholds": ["downstream-consumer", "human-gates"], "downgrade_target": None, "reason": "test"},
        "objective": "self-test objective",
        "surfaces": [{"id": "test", "kind": "repo", "locator": ".", "access_mode": "read-only"}],
        "assumptions": [],
        "patterns": ["Sequential"],
        "phases": [],
        "workers": [],
        "handoffs": [],
        "parallelism": {"shape": "none", "concurrency_cap": 1, "barriers": [], "fan_in_rule": "all"},
        "verification": [],
        "risk_gates": [],
        "budget": {"max_agents": 1, "max_rounds": 1, "max_retries": 0, "time_box": "5m", "file_touch_limit": "3"},
        "resume": {"cacheable_outputs": [], "invalidators": [], "restart_points": []},
        "execution_path": {"mode": "direct-codex", "first_slice": {"instruction": "do it", "inputs": ["task"], "expected_output": "done", "completion_check": "check", "forbidden_actions": ["write"]}, "consumer": "human"},
    }
    errs = validate_plan(valid_plan)
    if not errs:
        passed += 1
        print(f"  [PASS] Test {tests}: lightweight check passes")
    else:
        print(f"  [FAIL] Test {tests}: lightweight check rejected: {errs}")

    # Test 2: missing required field
    tests += 1
    errs = validate_plan({})
    if errs:
        passed += 1
        print(f"  [PASS] Test {tests}: empty plan rejected ({len(errs)} errors)")
    else:
        print(f"  [FAIL] Test {tests}: empty plan incorrectly accepted")

    # Test 3: bad schema version
    tests += 1
    bad_version = dict(valid_plan)
    bad_version["schema_version"] = "9.9"
    errs = validate_plan(bad_version)
    if any("schema_version" in e for e in errs):
        passed += 1
        print(f"  [PASS] Test {tests}: bad schema version rejected")
    else:
        print(f"  [FAIL] Test {tests}: bad schema version accepted")

    print(f"\nSelf-test: {passed}/{tests} passed")
    if passed == tests:
        # also run the existing evaluate_plan self-test
        print("\nRunning evaluate_plan.py --self-test...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "evaluate_plan", "--self-test"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("  evaluate_plan --self-test: PASS")
        else:
            print(f"  evaluate_plan --self-test: FAIL (exit {result.returncode})")
            if result.stdout:
                print(result.stdout[-500:])
    sys.exit(0 if passed == tests else 1)
