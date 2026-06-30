# Depone Native Team Runtime Wave Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development, OMX `$team`, or an equivalent
> supervised multi-lane workflow. Each lane owns the listed files only, reports
> exact verification output, and stops on shared-file conflicts.

**Goal:** Implement the next Depone-native team rung in small, independently
reviewable waves, starting with non-executing team launch preflight.

**Architecture:** Keep Team Ledger as the fan-in authority. Add one
non-executing preflight surface that validates planned lane launch boundaries
before any worker or worktree mutation exists. Later waves may add launch
receipts and fan-in wrappers only after preflight artifacts are revalidatable.

**Tech Stack:** stdlib-only Python, existing `depone.agent_fabric` modules,
existing CLI registration pattern in `depone/__main__.py`, `unittest`, committed
JSON artifacts under `docs/`, and `scripts/check_contract.py --tier changed`.

---

## Operating Rules

- One PR per wave unless a wave explicitly says it may split.
- No third-party Python dependencies.
- No worker launch in Wave 1.
- No destructive git operations.
- No cloud provisioning.
- No branch deletion.
- No merge automation.
- No assurance upgrade from preflight.
- Machine JSON is authoritative; Markdown only explains it.
- Every code lane must use TDD: write the failing test, watch it fail, implement,
  rerun.
- A lane that touches a file outside its ownership table stops and reports the
  conflict.

## Current Baseline

Existing surfaces to reuse:

- `depone/agent_fabric/team_dry_run.py`
- `depone/agent_fabric/team_ledger.py`
- `depone/agent_fabric/worktree_receipt.py`
- `depone/cli/team_dry_run.py`
- `depone/cli/agent_fabric_team_ledger.py`
- `docs/team-dry-run/`
- `docs/worktree-lane-receipt/`
- `docs/cloud-lane-artifact/`

Do not reimplement these. The next command should consume their artifacts.

## Wave 0: Spec Lock And Review

Purpose: make this plan reviewable before implementation.

Files:

- Create: `docs/depone-native-team-runtime-spec.md`
- Create: `docs/depone-native-team-runtime-wave-plan.md`
- Modify: `docs/depone-next-work-plan.md`

Acceptance:

- The spec states what is implemented and not implemented.
- The plan gives file ownership per lane.
- The first wave is non-executing and fail-closed.
- `python3 scripts/check_release_text.py .` passes.
- `python3 scripts/check_contract.py --tier changed` passes.
- `python3 scripts/dwm.py doctor` passes.

Review checklist:

- No paragraph claims Depone already launches workers.
- No paragraph claims cloud runtime isolation.
- No lane can pass from prose.
- The first code wave can be implemented in one PR.

## Wave 1: Team Launch Preflight

Purpose: bridge `team-dry-run` to future launch without launching anything.

Expected PR title:

```text
Add team launch preflight
```

### Lane 1A: Core Preflight Validator

Role: `worker`

Owned files:

- Create: `depone/agent_fabric/team_launch_preflight.py`
- Create: `tests/test_agent_fabric_team_launch_preflight.py`

Do not touch:

- `depone/__main__.py`
- `depone/cli/`
- `docs/`
- `scripts/check_contract.py`

Implementation contract:

- Export `build_team_launch_preflight(team_dry_run: dict[str, object], *, repo_root: Path, base_commit: str, adapter_availability: dict[str, object] | None = None) -> dict[str, object]`.
- Accept `launch_intent` with exactly two values: `plan-only` and
  `launch-ready`.
- Export `validate_team_launch_preflight(payload: dict[str, object]) -> list[dict[str, str]]`.
- Export `_self_test() -> None`.
- Use constants:
  - `TEAM_LAUNCH_PREFLIGHT_KIND = "depone-team-launch-preflight"`
  - `TEAM_LAUNCH_PREFLIGHT_SCHEMA_VERSION = "0.1"`
- Use structured error codes beginning with `ERR_TEAM_LAUNCH_PREFLIGHT_`.

Required positive test:

```python
def test_build_team_launch_preflight_passes_for_team_dry_run_fixture(self) -> None:
    team_dry_run = json.loads(Path("docs/team-dry-run/team-dry-run.json").read_text())
    base_commit = team_dry_run["base_commit"]

    payload = build_team_launch_preflight(
        team_dry_run,
        repo_root=Path("."),
        base_commit=base_commit,
        launch_intent="plan-only",
        adapter_availability={"codex": {"available": False, "source": "declared-unavailable"}},
    )

    self.assertEqual(payload["decision"], "pass")
    self.assertEqual(payload["launch_intent"], "plan-only")
    self.assertFalse(payload["boundary"]["launches_agents"])
    self.assertFalse(payload["boundary"]["creates_worktrees"])
```

Required negative tests:

- missing `kind` in input blocks;
- mismatched `base_commit` blocks;
- absolute `planned_worktree` blocks;
- `..` path traversal in `planned_worktree` blocks;
- duplicate lane ids block;
- missing lane evidence path blocks;
- missing adapter availability blocks when `launch_intent="launch-ready"`;
- unavailable adapter blocks when `launch_intent="launch-ready"`;
- unavailable adapter does not block when `launch_intent="plan-only"` and the
  lane records `availability_required: false`.

Verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_team_launch_preflight -v
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from depone.agent_fabric import team_launch_preflight as p
p._self_test()
print("team-launch-preflight self-test: pass")
PY
```

### Lane 1B: CLI Binding

Role: `worker`

Owned files:

- Create: `depone/cli/team_launch_preflight.py`
- Modify: `depone/__main__.py`
- Modify: `docs/command-reference.md`
- Create: `tests/test_team_launch_preflight_cli.py`

Do not touch:

- `depone/agent_fabric/team_ledger.py`
- `depone/agent_fabric/team_dry_run.py`
- `scripts/check_contract.py`

CLI contract:

```bash
python3 -m depone team-launch-preflight \
  --team-dry-run docs/team-dry-run/team-dry-run.json \
  --repo . \
  --base-commit <base_commit> \
  --launch-intent plan-only \
  --out docs/team-launch-preflight/team-launch-preflight.json \
  --team-ledger-out docs/team-launch-preflight/team-ledger.json \
  --json
```

Flags:

- `--team-dry-run PATH` required.
- `--repo PATH` defaults to `.`.
- `--base-commit REV` optional; default comes from the dry-run artifact.
- `--launch-intent plan-only|launch-ready` defaults to `plan-only`.
- `--adapter-availability PATH` optional JSON.
- `--out PATH` optional.
- `--team-ledger-out PATH` optional, but required for the committed fixture.
- `--json` prints JSON.
- `--self-test` runs the module self-test.

Exit behavior:

- `0` for `decision: pass`.
- `1` for valid JSON with `decision: blocked`.
- `3` for unreadable input or invalid JSON.

Required tests:

- self-test exits 0;
- valid fixture emits JSON with `kind`;
- invalid input exits 3 and emits structured error JSON.

Verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m depone team-launch-preflight --self-test
PYTHONDONTWRITEBYTECODE=1 python3 -m depone team-launch-preflight --team-dry-run docs/team-dry-run/team-dry-run.json --json
```

### Lane 1C: Fixtures, Contract, And Docs

Role: `worker`

Owned files:

- Create: `docs/team-launch-preflight/README.md`
- Create: `docs/team-launch-preflight/team-launch-preflight.json`
- Create: `docs/team-launch-preflight/team-ledger.json`
- Create: `docs/team-launch-preflight/team-ledger-verdict.json`
- Modify: `scripts/check_contract.py`
- Modify: `README.md`
- Modify: `docs/depone-next-work-plan.md`

Do not touch:

- `depone/agent_fabric/team_launch_preflight.py`
- `depone/cli/team_launch_preflight.py`
- tests owned by Lane 1A/1B except to update exact command names after review.

Artifact generation commands:

```bash
BASE_COMMIT=$(python3 - <<'PY'
import json
print(json.load(open("docs/team-dry-run/team-dry-run.json"))["base_commit"])
PY
)
python3 -m depone team-launch-preflight \
  --team-dry-run docs/team-dry-run/team-dry-run.json \
  --repo . \
  --base-commit "$BASE_COMMIT" \
  --launch-intent plan-only \
  --out docs/team-launch-preflight/team-launch-preflight.json \
  --team-ledger-out docs/team-launch-preflight/team-ledger.json \
  --json
python3 -m depone team-ledger \
  --ledger docs/team-launch-preflight/team-ledger.json \
  --out docs/team-launch-preflight/team-ledger-verdict.json \
  --json
```

Contract hook:

- Add `python3 -m depone team-launch-preflight --self-test` to the
  agent-facing CLI contract section or a new focused changed-tier step.
- Update the `check_contract.py --self-test` expected step list if a new step is
  added.

Docs must state:

- preflight does not launch agents;
- preflight does not create worktrees;
- preflight does not prove task completion;
- planned lanes remain blocked until evidence exists.
- `team-ledger.json` under `docs/team-launch-preflight/` is generated from the
  preflight command, not copied from the older dry-run fixture.
- The preflight and ledger artifacts must match on lane ids, evidence dirs,
  planned worktrees, and worktree receipt paths.

Verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_release_text.py .
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dwm.py doctor
git diff --check
```

### Lane 1D: Independent Review

Role: `reviewer`

Owned files:

- No edits by default.

Review scope:

- `depone/agent_fabric/team_launch_preflight.py`
- `depone/cli/team_launch_preflight.py`
- `tests/test_agent_fabric_team_launch_preflight.py`
- `docs/team-launch-preflight/`
- `scripts/check_contract.py`

Findings-first checklist:

- Can any malformed dry-run artifact produce `decision: pass`?
- Can an absolute path or `..` path escape the repo?
- Can `launch-ready` pass with missing or unavailable adapter availability?
- Does the CLI ever launch a process other than read-only git/query/self-test?
- Does any text claim worker execution?
- Does changed-tier verify the new command?
- Are artifacts generated by the command rather than hand-written prose?
- Does the generated Team Ledger skeleton match the preflight artifact instead
  of merely copying `docs/team-dry-run/team-ledger.json`?

Stop condition:

- If high or medium findings exist, create a repair packet.
- If no findings, report "no blocking findings" with exact verification gaps.

## Wave 2: Local Worktree Creation Receipt

Purpose: create or select local worktrees with provenance, but still do not run
worker agents.

This wave starts only after Wave 1 is merged.

Planned lanes:

- `launcher-core`: add a command that can create/select worktrees and write a
  launch-preparation receipt.
- `launcher-cli`: expose the command and document safe flags.
- `launcher-review`: verify no branch deletion, reset, clean, or worker launch.

Hard boundaries:

- May run `git worktree add` only with an explicit `--create-worktree` flag.
- Must never run `git reset`, `git clean`, `git checkout --`, or branch delete.
- Must write a receipt before any future worker launch.
- Must leave every lane blocked in Team Ledger.

Acceptance:

- committed machine fixture under `docs/team-worktree-prep/`;
- changed-tier contract passes;
- DWM doctor passes;
- no auto-launch.

## Wave 3: Single-Lane Shell Adapter Launch

Purpose: prove launch provenance with the simplest adapter before Codex/Claude.

This wave starts only after Wave 2 is merged.

Allowed adapter:

- `shell` only.

Hard boundaries:

- command allowlist must be explicit in the input plan;
- no arbitrary shell string concatenation;
- command receipt must include cwd, argv, exit code, stdout/stderr hashes, and
  transcript path;
- evidence is A1 unless isolation facts justify A2.

Acceptance:

- one real lane fixture that runs a harmless command;
- lane remains blocked unless evidence-next validates;
- changed-tier contract passes.

## Wave 4: Codex/Claude/OpenCode Adapter Launch

Purpose: integrate real coding adapters only after shell launch provenance is
boring.

This wave starts only after Wave 3 is merged and reviewed.

Adapter order:

1. Codex local adapter.
2. Claude Code local adapter.
3. OpenCode local adapter.
4. OMX/LazyCodex observed team adapter.

Rules:

- One adapter per PR.
- Every adapter must expose capability detection before launch.
- Missing binary, missing auth, or missing config returns blocked.
- Adapter output must be captured as an artifact, not summarized from memory.
- No provider superiority claim.

## Wave 5: PR Fan-In And Merge Evidence

Purpose: make a multi-lane team result reviewable as PR/check/merge evidence.

This wave starts only after at least one real local adapter lane exists.

Planned lanes:

- derive merge receipt from real git merge/rebase/conflict evidence;
- ingest GitHub PR/check status as local JSON;
- connect Team Ledger fan-in to `evidence-next` and `advance`.

Hard boundaries:

- no automatic PR merge in the first slice;
- no branch deletion;
- failed or pending checks block;
- merge conflicts block.

## Global Verification Set

Every wave reports:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest <focused tests> -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone <new-command> --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dwm.py doctor
git diff --check
git show --stat HEAD
```

If a command cannot run, the report must say why and name the next-best
evidence. Do not mark a wave complete from partial verification.

## Team Execution Packet For Wave 1

Use this objective for a team run:

```text
Implement Wave 1 from docs/depone-native-team-runtime-wave-plan.md.
Keep the slice non-executing. Build team-launch-preflight over existing
team-dry-run artifacts, add CLI/self-test/fixtures, wire changed-tier contract,
and stop before any worker launch or worktree creation. Preserve stdlib-only
Python and fail-closed validation.
```

Suggested lane assignment:

- worker-1: Lane 1A core validator and tests.
- worker-2: Lane 1B CLI binding and command tests.
- worker-3: Lane 1C docs, fixtures, contract integration.
- reviewer: Lane 1D findings-first review after workers report complete.

Coordinator merge order:

1. Merge Lane 1A first.
2. Rebase/apply Lane 1B on top of Lane 1A.
3. Generate Lane 1C artifacts from the merged command, not before.
4. Run Lane 1D review.
5. Apply repair packet if needed.
6. Run the global verification set.
7. Open a draft PR with the machine artifact output pasted in the body.

## Stop Conditions

Stop and report blocked if any of these happen:

- a lane needs secrets, API keys, or provider login;
- a lane needs destructive git commands;
- a lane would launch Codex/Claude/OpenCode/OMX before Wave 4;
- changed-tier contract fails for unrelated missing artifacts that cannot be
  regenerated from committed inputs;
- two workers need to edit the same owned file and cannot sequence cleanly;
- a reviewer finds a fail-open path that can produce `decision: pass` without
  machine evidence.
