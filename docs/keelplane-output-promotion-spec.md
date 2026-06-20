# Keelplane Output Promotion Stage Spec

Status: planned series stage
Date: 2026-06-20

## Purpose

The autonomous loop currently PROVES it can build a verified feature, then throws
the result away (the worktree is throwaway; only evidence survives). This stage
turns a `verified-complete` run from "a proof" into "a reviewable, gated
deliverable": the loop's built source promoted to a branch/PR for human review,
never auto-merged. This is the step that makes the loop actually do the user's
tool-dev work instead of only demonstrating it.

It is a new STAGE on the shared spine (series-on-spine architecture), not a new
tool and not a reimplementation: it consumes a loop run artifact and reuses the
spine's evidence/hash/worktree/git primitives.

## The One Rule

> Only DECLARED, VERIFIED target files are promoted, bound to the run's evidence
> chain; promotion produces a reviewable branch/PR and NEVER auto-merges to main.
> Promotion is a risk gate whose safe default is "produce the reviewable artifact
> and stop."

## Architecture (new stage, artifact contract)

- Input artifact: a `verified-complete` loop run (`out/keelplane-loop/<id>/`:
  journal + chained evidence + the worktree with the verified target files and
  per-phase checkpoint commits).
- Output artifact: a promotion bundle = (a) a hash-bound `promotion.json` record
  listing exactly the declared target files, their hashes, and the
  `evidence_chain_head` they came from; (b) a git branch `keelplane-loop/<id>`
  built from the worktree's verified checkpoint, optionally pushed with a draft
  PR via `gh`.
- Reuses spine: worktree/git, hashing, ownership sentinel, gate conventions.

## Non-Goals

- Do NOT auto-merge or push to main/master. Human reviews and merges the PR.
- Do NOT promote anything outside the declared target_files (no test edits, no
  stray files, no loop-owned verification files unless explicitly declared
  shippable).
- Do NOT promote a run that is not `verified-complete`.
- Do NOT change the loop's verification/gating logic or V94-V101.
- No direct-agent superiority or autonomy claim.

## Design Decisions

1. Commit durability (corrected by demo): the verified checkpoint commits already
   PERSIST in the repo's shared object store (git worktrees share the object
   database), and their SHAs are recorded in the run journal. So no worktree
   preservation is needed — only a `refs/keelplane/<id>` ref stamped on
   verified-complete to protect the commit from gc. Verified empirically: the live
   run's checkpoint commits still resolve, and `base..checkpoint` is exactly the
   declared target file (`scripts/keelplane_run_summary.py`, +36), nothing else.
2. Promoted scope = declared target_files only. The promotion bundle re-derives
   the diff between source HEAD and the verified checkpoint and asserts it touches
   ONLY declared target files; any extra path fails promotion.
3. Tests: the loop-owned immutable tests are the acceptance contract. The
   promotion declares whether they ship WITH the feature (recommended: yes, as the
   feature's tests) or stay as fixtures. This is per-run explicit, not implicit.
4. Delivery = feature branch + draft PR (the push guard blocks main, not feature
   branches). Safe default stops at "branch + PR created"; merge is the human's.
5. Honesty: `promotion.json` links to the run's `evidence_chain_head` and
   `status_hash`, so a reviewer can trace "this code came from an autonomous run
   that passed these immutable tests" — provenance, not a correctness claim.

## Execution Model

1. Refuse unless the input run is `verified-complete` and owned.
2. Re-derive the bounded diff `run_base..verified_checkpoint` and assert it touches
   ONLY declared target files (else `ERR_KEELPLANE_PROMOTE_SCOPE`).
3. Write `promotion.json` (declared files + hashes + evidence links).
4. Create branch `keelplane-loop/<id>` off CURRENT `main` and APPLY the bounded
   target diff onto it (NOT a branch from the stale checkpoint). Demo finding: a
   branch straight from the checkpoint carries the run-time base, so against an
   advanced main it would also REVERT every commit landed since the run; applying
   the bounded patch onto current main yields a PR of the feature only. If the
   patch does not apply cleanly onto current main, stop with
   `ERR_KEELPLANE_PROMOTE_CONFLICT` and ask for a rebase.
5. Risk gate: push the branch + open a draft PR ONLY with explicit approval
   (`--i-approve-branch-push`); safe default emits the bundle + a local branch and
   stops. NEVER touches main. (The push guard blocks main/master, not feature
   branches.)

## Path Split (deterministic vs live)

| Path | In keep gate? | Backend |
| --- | --- | --- |
| Promotion logic (diff bounding, record, branch from a fixture run) | Yes | fixture run, no codex, no remote |
| Branch push + draft PR | No | git/gh, opt-in `--i-approve-branch-push` |

The keep gate deterministically proves: scope bounding (extra file -> fail),
record integrity, branch built only from verified target diff, and refusal on a
non-`verified-complete` input — all with no network and no codex.

## Safety And Verification Gates

- Never push to main; only a feature branch, opt-in.
- The promoted diff must equal exactly the declared target-file changes; a
  verifier re-checks bounding independently.
- `promotion.json` is hash-bound and links the run evidence chain.
- A deterministic self-test/fixture suite joins the keep gate; the live branch
  push/PR stays opt-in.

## Evaluation Fixtures

- A fixture `verified-complete` run (reuse the loop's fixture executor) whose
  worktree has a known target diff -> promotion bundles exactly that file.
- A scope-violation fixture (worktree also changed a non-target file) -> promotion
  fails `ERR_KEELPLANE_PROMOTE_SCOPE`.
- A non-`verified-complete` run -> promotion refuses.

## Milestone

Promote the clean run's `scripts/keelplane_run_summary.py` to a reviewable
branch + draft PR, so the loop actually DELIVERS the feature under human review.
Verify: the branch contains only the verified target change, `promotion.json`
links the run's evidence chain, and main is untouched.

## Release / Implementation Plan

1. Worktree/checkpoint durability for `verified-complete` runs.
2. `promotion.json` + diff-bounding logic + deterministic keep-gate suite.
3. Branch-create (local) + opt-in push/PR behind `--i-approve-branch-push`.
4. Live milestone: promote the run-summary feature to a draft PR; human merges.

## Open Questions

- Whether promotion should run as a final loop phase automatically (on
  verified-complete) or as a separate explicit command.
- Whether the loop-owned tests ship with the feature by default.
- Whether multiple verified runs can stack onto one branch.
