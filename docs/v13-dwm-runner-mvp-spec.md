# V13 DWM Runner MVP Spec

Status: implemented in `scripts/dwm_runner.py`.

## Research And Prior Art

OMX proves that Codex CLI orchestration is useful when process launch, team
state, and hooks are packaged. DWM should not copy that full surface first. The
MVP runner should execute exactly one DWM-approved packet and return evidence
to DWM Core.

## Product Position And Non-Goals

V13 introduces DWM Runner as the first native execution layer. It is still not
a multi-agent runtime, and it may execute only read-only packets or packets
whose caller has already placed execution inside an isolated worktree.

Non-goals:

- do not run parallel workers,
- do not manage long-lived teams,
- do not provide a dashboard,
- do not support arbitrary shell commands,
- do not bypass DWM gates.
- do not create worktrees or attach durable sessions before V14.

## Workflow Architecture

Add a runner entry:

```bash
python scripts/dwm_runner.py run --run out/v1/<run_id> --out out/v13/<run_id>
```

Runner output should include:

- `runner.json`,
- `attempt.json`,
- `stdout.txt`,
- `stderr.txt`,
- `transcript.md` when available,
- `git-status-before.txt`,
- `git-status-after.txt`,
- `hashes.json`,
- `status.json`.

## Execution Model

The MVP runner calls V12 command planning before any backend action. It may run
only dry-run evidence preparation or allowlisted Codex fixture commands. It
must capture outputs before DWM Core decides whether the run is trusted.
Write-mode execution remains blocked in V13 unless a later slice adds an
explicit pre-isolated worktree contract.

## Safety And Verification Gates

The runner refuses packets without trusted DWM Core status. Write-mode packets
require an isolated worktree or explicit read-only mode. Secret access, network
access, dependency installation, production deploy, database migration, history
rewrite, deletion, and external messaging require human gates.

## Evaluation Fixtures

- positive: dry-run read-only packet records evidence,
- positive: Codex auth failure records blocked evidence,
- negative: stale packet refuses execution,
- negative: write-risk packet refuses execution.

## Release Plan

1. Add `scripts/dwm_runner.py` with dry-run and Codex-fixture modes.
2. Add manifest fixtures under `fixtures/v13/`.
3. Add `docs/v13-decision.md` from generated summary.
4. Keep live Codex execution, worktree creation, and session attachment out of
   V13.
