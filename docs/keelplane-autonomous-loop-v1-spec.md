# Keelplane Autonomous Loop v1 Spec (v2)

Status: planned autonomous-loop gate
Date: 2026-06-20

## Purpose

Keelplane has proven exactly ONE verified slice (V102) but has never run a
multi-phase task to completion on its own. This is Keelplane's answer to OMO's
`ulw-loop`: take a bounded multi-phase plan and drive it to a verified result
with no human between phases -- OMO-grade autonomy on Keelplane-grade evidence.

Descriptive name, not a `V<n>`, to stay out of the V94-V101 meta/reconciliation
chain. This is spec v2; it closes the 13 holes found reviewing v1.

## The One Rule That Makes It Keelplane, Not An OMO Clone

> The loop cannot advance a phase or claim done without verified, hash-bound
> evidence for that phase, and the loop OWNS the verification so the worker
> cannot game it. On unverifiable work it stops with an honest terminal state.

OMO optimizes "finish fast." Keelplane optimizes "if it says verified, the
declared checks really passed." Every decision below serves that.

## Verification Ownership (the core fix: H5/H6/H7)

Verification is loop-owned and immutable to the worker:

- The plan declares, per phase, the verification files (e.g. `pytest` files) and
  command. These files and command are hashed.
- Before EVERY verify, the loop restores the FULL union of verification files in
  scope (the current phase's subset plus all prior verified phases', for the
  regression guard) to their pristine hashed state, then runs the declared
  command with cache/bytecode hygiene (reuse V102 `run_process` env:
  `PYTHONDONTWRITEBYTECODE`, `-p no:cacheprovider`). If the worker modified or
  deleted a verification file, the loop overwrites it with the original. Gaming
  the test by editing it is therefore structurally impossible, not detected after
  the fact.
- Verification side-channel defense (R2): the worker could try to subvert the
  gate WITHOUT editing a declared test -- via an unanticipated `conftest.py`,
  `pytest.ini`, `setup.cfg`, `sitecustomize.py`, plugin, or env file. Therefore
  the loop runs verification with plugin autoload disabled
  (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`) and treats any worker-created file matching
  a verification-affecting pattern as subversion -> the phase FAILS (not merely
  flagged).
- The worker (codex) may only modify declared TARGET files; it never authors the
  gate. Files the worker creates outside the declared target/verification sets
  are flagged by review; verification-affecting ones fail the phase (above).
- Each phase verifies its declared verification subset AND all
  previously-verified phases' subsets (regression guard): a later phase may not
  silently break an earlier verified phase.

Trust bottoms out at the human-authored immutable verification files. The loop
cannot verify the verifier; that is the human's responsibility and is stated
honestly, not hidden.

## Non-Goals (v1)

- No auto-planning. The loop consumes a GIVEN plan; objective-to-plan is later.
- No worker-authored tests as the gate. The worker writes SOURCE only; the loop
  owns the tests.
- No non-mechanical phases. Every phase must declare a deterministic verification
  command (no network/clock dependence). Research/design phases are out of scope.
- No parallel agents; one worker per phase, bounded.
- No unbounded keep-going. Hard caps on repairs, per-call timeout, and total
  budget.
- Do not modify the V94-V101 meta layer. Do not mass-rename `dwm_*` files.
- No direct-agent superiority claim.

## Scope (In)

1. A new thin driver `keelplane_loop.py` that runs a multi-phase plan.
2. Loop-owned immutable verification (above).
3. One persistent worktree with per-phase checkpoints and resume.
4. Honest terminal states and stop conditions.
5. First milestone: autonomously build one small feature in this repo across
   phases, worker writing source only.

## Architecture (Reuse V102; New Driver Only)

Reuse, do NOT reimplement (the V102 lesson):

- `compile_workflow.py` for plan-to-packet per phase.
- the V102 installed-codex execute path (sandboxed worktree).
- the V102 evidence bundle, hashing, and ownership sentinel.
- the V3 journal scaffolding for durability.

New code is only `keelplane_loop.py` (NOT an extension of `run_workflow.py`,
whose V3 contract is "does not execute later packets" and whose fixtures assert
it). The driver imports and calls the trusted execute+verify functions.

The execute step goes through an EXECUTOR ADAPTER seam (R1) with two modes,
mirroring V102: `fixture` (a deterministic stub that applies a recorded source
change or a recorded failure, used by the keep-gate state-machine tests with no
codex binary) and `installed-codex` (the live opt-in run). The loop's control
logic -- phase progression, immutable-verification restore, regression guard,
stop conditions, checkpoint/resume -- is identical in both modes, so the keep
gate deterministically exercises the real state machine.

## Worktree Lifecycle (H2/H8/N2)

- ONE persistent worktree for the whole run; phases accumulate (phase 2 sees
  phase 1's source).
- The loop OWNS git in the worktree. After each verified phase it makes a
  checkpoint commit. The worker is prompted not to run git; the loop normalizes
  worktree git state each phase regardless.
- `--resume` resets the worktree to the last checkpoint commit (`git reset
  --hard`, safe because the worktree is throwaway) and re-runs the unfinished
  phase.

## Loop Contract

```text
for phase in plan.phases:
    restore_immutable_verification_files(phase)   # loop-owned
    packet   = compile(phase)                      # target files only
    evidence = execute(packet)                     # installed-codex, worktree
    restore_immutable_verification_files(phase)    # in case worker touched them
    result   = verify(phase.subset + prior.subsets)  # regression guard
    if not result.verified:
        evidence = repair(packet, result)          # at most once
        restore_immutable_verification_files(phase)
        result   = verify(...)
    if result.verified:
        journal.append(phase, evidence)            # hash CHAINED to prior phase
        checkpoint_commit(worktree)
        continue                                    # autonomous advance, no human
    else:
        STOP -> terminal "failed"                   # never claim done
when all phases verified:
    terminal "verified-complete" with full chained evidence
```

Caps: `max_repairs_per_phase = 1`, per-codex `timeout_seconds`, and a REQUIRED
total budget hard cap (codex-call count and/or wall-time); exceeding it ends
`blocked`.

## Terminal States (Honest)

- `verified-complete`: every phase's declared verifications passed. This means
  the declared checks passed, NOT that the feature is correct in unchecked ways.
- `blocked`: a risk gate, missing prerequisite, or budget cap; safe default is
  stop, preserve, ask. Autonomy holds only for non-risky phases; the
  workspace-write sandbox is the first risk bound (no network/install).
- `failed`: a phase could not be verified after one repair; the loop stops and
  does NOT claim completion.

Each terminal state is hash-bound to the full per-phase evidence chain.

## First Milestone (Falsifiable, Redesigned: N1)

The loop autonomously builds one small feature across phases, worker writing
SOURCE only, verified by loop-owned immutable tests, zero human steps between
phases.

Example: `scripts/keelplane_run_summary.py` -- summarize an `out/<run>` dir.
- Phase 1: implement the status summary (decision/valid). Loop-owned
  `test_part1.py` must pass.
- Phase 2: add the evidence summary (artifact_count/source_hash). Loop-owned
  `test_part2.py` must pass AND `test_part1.py` still passes (regression).

The milestone passes only if BOTH hold:

- a clean run advances all phases on verified evidence with no human steps and
  ends `verified-complete` with a chained evidence ledger; AND
- a fault-injected run, where a phase's loop-owned test is one no legitimate
  source change can satisfy, ends `failed`/`blocked` and NEVER
  `verified-complete` (the worker cannot game it because the test is immutable).

Scope honesty: the milestone proves the loop's CONTROL is correct
(advance-on-verified / stop-on-unverified / no-gaming), NOT that codex reliably
succeeds (codex is non-deterministic; one clean completion proves the mechanism,
not reliability).

## Journal / Resume

Append-only journal; phase N's evidence hash is CHAINED to phase N-1's (tamper-
evident across the whole run). `--resume` recomputes integrity of the journaled
chain (it does not re-derive non-deterministic codex output), resets the worktree
to the last checkpoint, and continues. Stale/tampered evidence invalidates
resume (reuse V3 rules).

## Acceptance Criteria

- A real multi-phase task runs autonomously with per-phase verified, chained,
  hash-bound evidence (no null metrics) and ends `verified-complete`.
- A fault-injected run ends `failed`/`blocked`, never `verified-complete`, even
  with a repair attempt (proving the immutable gate).
- `--resume` from a mid-run journal continues from the last verified phase;
  tampered/stale evidence invalidates resume.
- The driver reuses the V102 execute+verify path (no reimplementation) and does
  not alter `run_workflow.py`'s V3 contract.
- A deterministic self-test/fixture suite for the loop STATE MACHINE (phase
  progression, immutable-verification restore, regression guard, stop conditions,
  checkpoint/resume) passes with no codex binary on PATH and joins the keep gate;
  the live autonomous run stays opt-in.
- V94-V101 and unrelated tracked files are unchanged; `python
  scripts/check_contract.py` stays green; no superiority/autonomy/benchmark claim.

## Decision Output

Record in `docs/keelplane-autonomous-loop-v1-decision.md`: the exact run command,
the chained evidence ledger, the fault-injected terminal state, the resume
result, and a restatement that this proves a bounded autonomous loop, not
unrestricted autonomy.

## Open Questions

- Whether v2-of-the-product adds objective-to-plan auto-generation (the SKILL.md
  planner run as an agent) so the loop can start from a bare objective like OMO.
- Whether independent phases may later run in parallel with deterministic fan-in.
- Whether a phase may legitimately need to change a verification contract
  (interface change); v1 forbids it (tests are fixed), which constrains tasks to
  contract-fixed shape.
