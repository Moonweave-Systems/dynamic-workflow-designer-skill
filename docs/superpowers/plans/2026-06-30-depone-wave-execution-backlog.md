# Depone Wave Execution Backlog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give future agents a clean, current, wave-by-wave execution backlog for finishing Depone's evidence-first team and adapter layers.

**Architecture:** Keep `docs/v125-direction-check-roadmap.md` as product-direction authority, `docs/depone-next-work-plan.md` as the operator backlog, and this file as the executable agent plan. Each wave is one PR-sized slice with exact files, commands, acceptance evidence, and stop rules.

**Tech Stack:** Python standard library, `unittest`, `git`, `gh` CLI when available, Depone CLI modules under `depone/agent_fabric/` and `depone/cli/`, committed JSON fixtures under `docs/`.

---

## File Structure

- Modify: `docs/depone-next-work-plan.md`
  - Maintains the current operator-facing backlog and wave order.
- Create or modify per future wave:
  - `depone/agent_fabric/team_pr_artifact.py`
  - `depone/cli/team_pr_artifact.py`
  - `tests/test_agent_fabric_team_pr_artifact.py`
  - `tests/test_team_pr_artifact_cli.py`
  - `docs/team-pr-artifact/README.md`
  - `docs/team-pr-artifact/pr-artifact.json`
  - `depone/agent_fabric/team_merge_attempt.py`
  - `depone/cli/team_merge_attempt.py`
  - `tests/test_agent_fabric_team_merge_attempt.py`
  - `tests/test_team_merge_attempt_cli.py`
  - `docs/team-merge-attempt/README.md`
  - `docs/team-merge-attempt/merge-attempt.json`
- Modify when each implementation wave is active:
  - `depone/__main__.py`
  - `scripts/check_contract.py`
  - `docs/command-reference.md`
  - `docs/depone-cloud-team-control.md`

## Wave 0: Repository Hygiene And PR Decision

**Files:**
- Modify: `docs/depone-next-work-plan.md`
- Read-only: GitHub PR #55 and open PR list.

- [ ] **Step 1: Revalidate PR #55 from its remote branch**

Run:

```bash
git fetch -q origin
git switch --detach origin/codex/codex-capability-pass-readiness
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_codex_local_capability tests.test_codex_local_capability_cli -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone codex-local-capability --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dwm.py doctor
```

Expected:

```text
Ran 15 tests
OK
depone codex-local-capability --self-test: pass
contract changed: pass
DWM doctor: ok
```

- [ ] **Step 2: Decide PR #55 state**

Run:

```bash
gh pr view 55 --json number,title,isDraft,mergeable,headRefName,baseRefName,url
```

Expected for ready path:

```json
{"number":55,"isDraft":true,"mergeable":"MERGEABLE"}
```

If verification passed and the PR is not superseded by `origin/main`, run:

```bash
gh pr ready 55
```

If it is superseded, leave a closing comment with the exact command output and close it:

```bash
gh pr close 55 --comment "Closed because origin/main already contains the equivalent capability receipt behavior. Verification evidence: <paste exact command summary>."
```

- [ ] **Step 3: Inventory stale open PRs**

Run:

```bash
gh pr list --state open --limit 40 --json number,title,headRefName,baseRefName,mergeable,isDraft,url > /tmp/depone-open-prs.json
python3 - <<'PY'
import json
prs = json.load(open("/tmp/depone-open-prs.json"))
for pr in prs:
    print(f"#{pr['number']} {pr['mergeable']} {pr['headRefName']} -> {pr['baseRefName']} :: {pr['title']}")
PY
```

Expected:

```text
#55 MERGEABLE codex/codex-capability-pass-readiness -> main :: Add Codex capability readiness probe
```

The old stack PRs may also print. Do not close or merge them in this step.

- [ ] **Step 4: Record PR stack decision table**

Create or update a section in `docs/depone-next-work-plan.md` with this exact shape:

```markdown
## Open PR Cleanup Table

| PR | Decision | Reason | Required action |
| --- | --- | --- | --- |
| #55 | keep | Codex capability readiness hardening is a current Wave 0 candidate. | Revalidate, mark ready, then merge or close with evidence. |
| #9-#27 | audit-before-action | Stacked historical spec PRs may be stale or superseded by main. | Produce a separate inventory PR or close plan; do not merge blindly. |
| #7 | audit-before-action | Old measurement draft may conflict with current evidence discipline. | Re-check scope before any action. |
```

- [ ] **Step 5: Verify docs-only change**

Run:

```bash
git diff --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_release_text.py .
```

Expected:

```text
release text check: pass
```

Commit:

```bash
git add docs/depone-next-work-plan.md
git commit -m "Refresh Depone wave backlog"
```

## Wave 1: Team PR Artifact Producer

**Files:**
- Create: `depone/agent_fabric/team_pr_artifact.py`
- Create: `depone/cli/team_pr_artifact.py`
- Create: `tests/test_agent_fabric_team_pr_artifact.py`
- Create: `tests/test_team_pr_artifact_cli.py`
- Create: `docs/team-pr-artifact/README.md`
- Create: `docs/team-pr-artifact/pr-artifact.json`
- Modify: `depone/__main__.py`
- Modify: `scripts/check_contract.py`
- Modify: `docs/command-reference.md`

- [ ] **Step 1: Write failing core tests**

Add tests for:

```python
def test_pr_artifact_passes_with_matching_head_sha_and_checks() -> None: ...
def test_pr_artifact_blocks_head_sha_mismatch() -> None: ...
def test_pr_artifact_blocks_failed_checks() -> None: ...
def test_pr_artifact_blocks_stale_artifact() -> None: ...
def test_pr_artifact_blocks_malformed_input() -> None: ...
```

Run:

```bash
python3 -m unittest tests.test_agent_fabric_team_pr_artifact -v
```

Expected: import failure for `depone.agent_fabric.team_pr_artifact`.

- [ ] **Step 2: Implement core validation**

Implement `build_team_pr_artifact(...)`, `validate_team_pr_artifact(...)`, and
`write_team_pr_artifact(...)` in `depone/agent_fabric/team_pr_artifact.py`.

Required artifact fields:

```json
{
  "kind": "depone-team-ledger-pr-artifact",
  "schema_version": "0.1",
  "provider": "github",
  "pr_number": 55,
  "pr_url": "https://github.com/Moonweave-Systems/Depone/pull/55",
  "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "head_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "state": "OPEN",
  "merge_state_status": "CLEAN",
  "check_summary": {
    "status": "pass",
    "total_count": 0,
    "failed_count": 0,
    "pending_count": 0
  },
  "stale": false,
  "captured_at": "2026-06-30T00:00:00Z"
}
```

- [ ] **Step 3: Add CLI**

Register:

```bash
python3 -m depone team-pr-artifact --help
```

The CLI must accept either saved JSON input or live `gh` output:

```bash
python3 -m depone team-pr-artifact --input /tmp/pr.json --out docs/team-pr-artifact/pr-artifact.json --json
```

Live `gh` execution is optional. The committed fixture path must work without network.

- [ ] **Step 4: Wire contract validation**

Update `scripts/check_contract.py` so `--tier changed` validates:

```text
docs/team-pr-artifact/pr-artifact.json
```

Expected validation failure examples:

```text
team-pr-artifact head_sha does not match lane end_commit
team-pr-artifact check_summary.status must be pass
team-pr-artifact stale must be false
```

- [ ] **Step 5: Verify Wave 1**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_team_pr_artifact tests.test_team_pr_artifact_cli -v
python3 -m depone team-pr-artifact --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected: all pass.

Commit:

```bash
git add depone/agent_fabric/team_pr_artifact.py depone/cli/team_pr_artifact.py depone/__main__.py tests/test_agent_fabric_team_pr_artifact.py tests/test_team_pr_artifact_cli.py docs/team-pr-artifact/ docs/command-reference.md scripts/check_contract.py
git commit -m "Add team PR artifact receipt"
```

## Wave 2: Git Merge Attempt Receipt

**Files:**
- Create: `depone/agent_fabric/team_merge_attempt.py`
- Create: `depone/cli/team_merge_attempt.py`
- Create: `tests/test_agent_fabric_team_merge_attempt.py`
- Create: `tests/test_team_merge_attempt_cli.py`
- Create: `docs/team-merge-attempt/README.md`
- Create: `docs/team-merge-attempt/merge-attempt.json`
- Modify: `depone/__main__.py`
- Modify: `scripts/check_contract.py`
- Modify: `docs/command-reference.md`

- [ ] **Step 1: Write failing merge receipt tests**

Add tests for:

```python
def test_clean_merge_attempt_passes_in_disposable_worktree() -> None: ...
def test_conflicting_merge_attempt_blocks_with_conflict_files() -> None: ...
def test_dirty_target_worktree_blocks_without_disposable_mode() -> None: ...
def test_missing_base_commit_blocks() -> None: ...
def test_receipt_validation_rejects_missing_cleanup_state() -> None: ...
```

Run:

```bash
python3 -m unittest tests.test_agent_fabric_team_merge_attempt -v
```

Expected: import failure for `depone.agent_fabric.team_merge_attempt`.

- [ ] **Step 2: Implement receipt shape**

The receipt must include:

```json
{
  "kind": "depone-team-merge-attempt",
  "schema_version": "0.1",
  "decision": "pass",
  "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "head_commits": ["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
  "attempt_worktree": "/tmp/depone-merge-attempt",
  "dirty_target_refused": false,
  "exit_code": 0,
  "merged_files": ["depone/agent_fabric/team_ledger.py"],
  "conflict_files": [],
  "cleanup": {"attempt_worktree_removed": true}
}
```

- [ ] **Step 3: Add CLI**

Run:

```bash
python3 -m depone team-merge-attempt --base <base_sha> --head <head_sha> --repo . --out docs/team-merge-attempt/merge-attempt.json --json
```

The first implementation should prefer a disposable worktree and refuse dirty
target state unless the command can prove it will not mutate the caller's tree.

- [ ] **Step 4: Connect Team Ledger**

Teach Team Ledger to accept `depone-team-merge-attempt` as the merge receipt
source when passed lanes overlap. Preserve the existing simple
`team-ledger-merge-receipt` path for compatibility.

- [ ] **Step 5: Verify Wave 2**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_team_merge_attempt tests.test_team_merge_attempt_cli tests.test_agent_fabric_team_ledger -v
python3 -m depone team-merge-attempt --self-test
python3 -m depone team-ledger --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected: all pass.

Commit:

```bash
git add depone/agent_fabric/team_merge_attempt.py depone/cli/team_merge_attempt.py depone/__main__.py tests/test_agent_fabric_team_merge_attempt.py tests/test_team_merge_attempt_cli.py tests/test_agent_fabric_team_ledger.py docs/team-merge-attempt/ docs/command-reference.md scripts/check_contract.py
git commit -m "Add team merge attempt receipt"
```

## Wave 3: Minimal Local Team Loop

**Files:**
- Create: `depone/agent_fabric/team_local.py`
- Create: `depone/cli/team_local.py`
- Create: `tests/test_agent_fabric_team_local.py`
- Create: `tests/test_team_local_cli.py`
- Create: `docs/team-local/README.md`
- Create: `docs/team-local/team-run-ledger.json`
- Modify: `depone/__main__.py`
- Modify: `scripts/check_contract.py`
- Modify: `docs/command-reference.md`

- [ ] **Step 1: Write failing orchestration tests**

Add tests for:

```python
def test_team_local_stops_on_blocked_preflight() -> None: ...
def test_team_local_runs_one_allowlisted_shell_lane() -> None: ...
def test_team_local_requires_evidence_next_for_passed_lane() -> None: ...
def test_team_local_does_not_launch_live_model() -> None: ...
```

Run:

```bash
python3 -m unittest tests.test_agent_fabric_team_local -v
```

Expected: import failure for `depone.agent_fabric.team_local`.

- [ ] **Step 2: Implement orchestration over existing commands**

The first `team-local` implementation must sequence only existing safe pieces:

```text
team-dry-run -> team-launch-preflight -> team-worktree-prep -> team-shell-lane-launch -> evidence-next -> team-ledger
```

It must not call Codex, Claude Code, OpenCode, OMX worker launch, or a live
model API.

- [ ] **Step 3: Emit `team-run-ledger.json`**

The ledger must include:

```json
{
  "kind": "depone-team-local-run",
  "schema_version": "0.1",
  "decision": "blocked",
  "lanes": [],
  "artifacts": {},
  "boundary": {
    "launches_live_model": false,
    "launches_external_team_runtime": false,
    "raises_assurance": false
  }
}
```

- [ ] **Step 4: Verify Wave 3**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_team_local tests.test_team_local_cli -v
python3 -m depone team-local --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected: all pass.

Commit:

```bash
git add depone/agent_fabric/team_local.py depone/cli/team_local.py depone/__main__.py tests/test_agent_fabric_team_local.py tests/test_team_local_cli.py docs/team-local/ docs/command-reference.md scripts/check_contract.py
git commit -m "Add minimal local team loop"
```

## Wave 4: Coding Adapter Launch Receipt

**Files:**
- Modify or create after PR #55 is merged:
  - `depone/agent_fabric/codex_local_capability.py`
  - `depone/cli/codex_local_capability.py`
  - `depone/agent_fabric/codex_lane_launch.py`
  - `depone/cli/codex_lane_launch.py`
  - `tests/test_agent_fabric_codex_lane_launch.py`
  - `tests/test_codex_lane_launch_cli.py`
  - `docs/codex-lane-launch/README.md`
  - `docs/codex-lane-launch/receipt.json`

- [ ] **Step 1: Confirm capability readiness landed**

Run:

```bash
git fetch -q origin
git branch --contains origin/codex/codex-capability-pass-readiness || true
python3 -m depone codex-local-capability --self-test
```

Expected:

```text
depone codex-local-capability --self-test: pass
```

- [ ] **Step 2: Write launch receipt tests**

Add tests for:

```python
def test_codex_launch_blocks_when_capability_decision_blocked() -> None: ...
def test_codex_launch_records_argv_without_secret_values() -> None: ...
def test_codex_launch_writes_transcript_and_exit_code() -> None: ...
def test_codex_launch_refuses_unallowlisted_command() -> None: ...
```

- [ ] **Step 3: Implement Codex-only launch receipt**

The first adapter launch receipt must include:

```json
{
  "kind": "depone-codex-lane-launch",
  "schema_version": "0.1",
  "decision": "blocked",
  "capability_receipt": "docs/codex-local-capability/capability.json",
  "argv": ["codex", "exec", "--sandbox", "workspace-write"],
  "exit_code": null,
  "transcript": null,
  "boundary": {
    "reads_auth_files": false,
    "records_secret_values": false,
    "raises_assurance": false
  }
}
```

- [ ] **Step 4: Verify Wave 4**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_codex_lane_launch tests.test_codex_lane_launch_cli -v
python3 -m depone codex-lane-launch --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected: all pass.

## Wave 5: Cloud Adapter Receipt

**Files:**
- Create: `depone/agent_fabric/cloud_lane_receipt.py`
- Create: `depone/cli/cloud_lane_receipt.py`
- Create: `tests/test_agent_fabric_cloud_lane_receipt.py`
- Create: `tests/test_cloud_lane_receipt_cli.py`
- Create: `docs/cloud-lane-receipt/README.md`
- Create: `docs/cloud-lane-receipt/cloud-lane-receipt.json`
- Modify: `depone/__main__.py`
- Modify: `scripts/check_contract.py`
- Modify: `docs/command-reference.md`

- [ ] **Step 1: Write cloud receipt tests**

Add tests for:

```python
def test_cloud_receipt_validates_observed_external_facts() -> None: ...
def test_cloud_receipt_blocks_runtime_attestation_claim() -> None: ...
def test_cloud_receipt_blocks_evidence_hash_mismatch() -> None: ...
def test_cloud_receipt_blocks_missing_external_run_id() -> None: ...
```

- [ ] **Step 2: Implement provider-neutral receipt**

The first receipt must use saved JSON input only. Do not add provider SDKs.

- [ ] **Step 3: Verify Wave 5**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_cloud_lane_receipt tests.test_cloud_lane_receipt_cli tests.test_agent_fabric_team_ledger -v
python3 -m depone cloud-lane-receipt --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected: all pass.

## Wave 6: A3 Signing Ergonomics

**Files:**
- Modify: `depone/agent_fabric/sign.py`
- Modify: `depone/cli/agent_fabric_sign.py`
- Modify: `depone/cli/agent_fabric_verify_signature.py`
- Modify: `tests/test_agent_fabric_sign.py`
- Modify: `tests/test_evidence_run_signing.py`
- Modify: `docs/evidence-run-signing/README.md` if absent, create it.
- Modify: `docs/command-reference.md`

- [ ] **Step 1: Revalidate current signing fixture**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_sign tests.test_evidence_run_signing -v
python3 -m depone agent-fabric-sign --self-test
python3 -m depone agent-fabric-verify-signature --self-test
```

Expected: all pass.

- [ ] **Step 2: Add operator-facing verify command or docs**

If the existing commands are sufficient, add only a README with exact
verification commands for `docs/evidence-run-signing/signed-evidence-bundle.json`.
If friction remains high, add an alias that calls the existing verifier.

- [ ] **Step 3: Verify Wave 6**

Run:

```bash
python3 -m unittest tests.test_agent_fabric_sign tests.test_evidence_run_signing -v
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected: all pass.

## Wave 7: Bounded Loop

**Files:**
- Create: `depone/agent_fabric/evidence_loop.py`
- Create: `depone/cli/evidence_loop.py`
- Create: `tests/test_evidence_loop.py`
- Modify: `depone/__main__.py`
- Modify: `docs/agent-tool-contract.md`
- Modify: `docs/command-reference.md`

- [ ] **Step 1: Write loop tests**

Add tests for:

```python
def test_loop_requires_max_steps() -> None: ...
def test_loop_stops_before_execution_when_next_blocks() -> None: ...
def test_loop_validates_prev_capture_hash_before_each_step() -> None: ...
def test_loop_resume_refuses_missing_intermediate_step() -> None: ...
```

- [ ] **Step 2: Implement budgeted loop**

The loop must call the existing `advance` behavior one step at a time and write:

```json
{
  "kind": "depone-evidence-loop-ledger",
  "schema_version": "0.1",
  "decision": "blocked",
  "max_steps": 3,
  "completed_steps": 0,
  "chain_head": null,
  "blocking_reasons": []
}
```

- [ ] **Step 3: Verify Wave 7**

Run:

```bash
python3 -m unittest tests.test_evidence_loop tests.test_evidence_advance tests.test_evidence_next -v
python3 -m depone loop --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected: all pass.

## Wave 8: Benchmark Harness

**Files:**
- Create: `depone/agent_fabric/benchmark_harness.py`
- Create: `depone/cli/benchmark_harness.py`
- Create: `tests/test_benchmark_harness.py`
- Create: `docs/benchmark-harness/README.md`
- Create: `docs/benchmark-harness/task-corpus.json`
- Create: `docs/benchmark-harness/report.json`
- Modify: `depone/__main__.py`
- Modify: `docs/command-reference.md`

- [ ] **Step 1: Define corpus tests**

Add tests for six task classes:

```python
def test_corpus_requires_doc_only_task() -> None: ...
def test_corpus_requires_single_file_bug_task() -> None: ...
def test_corpus_requires_multi_file_cli_task() -> None: ...
def test_corpus_requires_artifact_regeneration_task() -> None: ...
def test_corpus_requires_review_only_task() -> None: ...
def test_corpus_requires_pr_finalization_task() -> None: ...
```

- [ ] **Step 2: Implement report validator**

The report must separate:

```json
{
  "deterministic": {"passed": 0, "failed": 0, "blocked": 0},
  "advisory_review": {"findings": []},
  "public_claim": {"allowed": false, "reason": "sample threshold not met"}
}
```

- [ ] **Step 3: Verify Wave 8**

Run:

```bash
python3 -m unittest tests.test_benchmark_harness -v
python3 -m depone benchmark-harness --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
git diff --check
```

Expected: all pass.

## Stop Rules For Every Wave

- Stop before destructive git operations.
- Stop before reading secrets or private auth files.
- Stop before live cloud provisioning.
- Stop before claiming assurance from prose.
- Stop if committed machine artifacts fail revalidation.
- Stop if the change expands into more than one wave slice.

## Final Verification Bundle For Any Wave PR

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest <changed-tests> -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone <changed-command> --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dwm.py doctor
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_release_text.py .
git diff --check origin/main..HEAD
git show --stat --oneline HEAD
```

Open a draft PR with the exact verification output and keep it draft until the
committed artifacts can be revalidated from a clean checkout.
