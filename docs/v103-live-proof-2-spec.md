# V103 Live Proof 2 Spec

Status: planned comparison-arm gate
Date: 2026-06-20

## Purpose

V102 produced one real `dwm-controlled` live proof (n=1) but left the
`direct-codex` comparison arm a placeholder, so the central product question the
critical review raised -- "does the DWM control-plane add anything over a direct
agent?" -- is still unmeasured. The `dogfood_comparison` field has one real arm
and one null arm.

V103 closes the second arm. It runs the SAME seeded task through a bare
`codex exec` (no DWM packet, no independent review, no gate) and records its
evidence next to the dwm-controlled arm, so both modes have real, non-null
metrics on one task.

V103 is not another meta layer. It adds the missing measurement arm and nothing
else. V94-V101 stay frozen.

## Product Position And The Honest Claim

On a trivial task both arms will reach a green check. V103 therefore does NOT
claim DWM passes more often, runs faster, or costs less. The single recorded,
honest differentiator is evidence and verifiability:

- `direct-codex`: produces an exit code and a transcript. Whether the green is
  legitimate (source fixed vs. test gamed) is unknown from the artifact.
- `dwm-controlled`: produces an exit code, a transcript, an independent
  legitimacy verdict (test-unchanged + source-changed), and a hash-bound
  evidence bundle.

The recorded comparison is about evidence richness, not pass-rate superiority.
Any stronger comparison (speed, cost, success rate, multi-task) requires a real
task corpus and is explicitly out of scope.

## Non-Goals

- Do not claim DWM is faster, cheaper, or more likely to succeed than direct
  Codex. The only claim is "dwm-controlled records an independent legitimacy
  verdict and hash-bound evidence that direct-codex does not."
- Do not extend or re-score the V94-V101 meta chain.
- Do not run either live arm inside the deterministic keep gate.
- Do not execute against DWM repo tracked files. Each arm uses its own isolated,
  throwaway seeded worktree.
- Do not commit, push, merge, delete, install, deploy, access secrets, send
  external messages, or rewrite history.
- Do not add a third task category yet (kept for a later slice).
- Do not fabricate a gaming scenario to make DWM look better; record what the two
  arms actually produce on the same honest task.

## Scope

In scope:

1. A `direct-codex` arm: run the existing seed task with a bare `codex exec` and a
   plain natural-language prompt, with no packet compilation, no independent
   review, and no gate.
2. A comparison record that holds both arms with real, non-null metrics and an
   honest, superiority-free conclusion.
3. A deterministic, Codex-free schema test of the comparison record that joins
   the keep gate.
4. README, decision, spec, roadmap, and release-history reconciliation that
   states the bounded comparison claim.

Out of scope: everything in Non-Goals, plus speed/cost benchmarking, multi-task
corpora, and any relative success-rate statement.

## Architecture

V103 reuses V102; it does not reimplement execution or weaken the V102 gate.

- `dwm-controlled` arm: the existing V102 `run_live` path (packet compile ->
  installed-codex exec -> verify -> independent_review gate -> hash-bound
  bundle). Unchanged.
- `direct-codex` arm: a new, clearly separate path that copies the seed into its
  own isolated worktree, runs:

  ```text
  codex exec --skip-git-repo-check --cd <direct-worktree> --sandbox \
    workspace-write --output-last-message <transcript> -
  ```

  with a plain prompt such as "Make the failing pytest pass." It records exit
  code, transcript, verification before/after, elapsed, and files_touched. It
  deliberately computes NO independent legitimacy review and produces NO gated
  pass/fail verdict, because absence of that verdict is the measured difference.
- Comparison: a thin recorder writes `comparison.json` + `comparison.md` holding
  both arms. It calls the trusted V102 path for the dwm arm and the new bare path
  for the direct arm; it must not duplicate or fork the V102 review logic.

### Path split (unchanged discipline)

| Path | Command | In keep gate? | Backend |
| --- | --- | --- | --- |
| Deterministic schema test | `--self-test`, `--manifest fixtures/v103/manifest.json` | Yes | fixture-command, no Codex |
| Live comparison run | `compare ... --i-approve-live-codex` | No | installed-codex, both arms |

## Comparison Record Schema

`out/live-proofs/<id>/comparison.json` must contain at least:

```text
comparison_id, schema_version, tool
task: { id, seed_path, verification_command }
arms: [
  { mode: "direct-codex",
    worktree, verification: { before, after, returncode, passed },
    files_touched, transcript_path, elapsed_seconds,
    has_independent_review: false, has_hash_bound_bundle: false,
    legitimacy_verdict: null },
  { mode: "dwm-controlled",
    proof_ref: "live-proof.json", decision,
    verification: { before, after, returncode, passed },
    files_touched, transcript_path, elapsed_seconds,
    has_independent_review: true, has_hash_bound_bundle: true,
    legitimacy_verdict: <review.decision + checks> } ]
differentiators: {
  independent_legitimacy_review: "dwm-controlled only",
  hash_bound_evidence_bundle: "dwm-controlled only" }
honest_conclusion: "Both arms reached a green check on this task. Only the
  dwm-controlled arm recorded an independent legitimacy verdict and hash-bound
  evidence. This records evidence richness, not pass-rate, speed, or cost
  superiority."
claim_policy: "comparison on n=1; no direct-agent superiority claim"
repo_tracked_diff_unchanged: true
source_hashes: { ... }
```

Honesty rules:

- If either arm's `codex exec` auth-fails or the binary is missing, record the
  blocked state honestly; never synthesize a green.
- The `direct-codex` arm records exactly what a bare run yields. It must not
  borrow the dwm arm's review verdict.
- `repo_tracked_diff_unchanged` must hold after both arms.

## Execution Model

The live comparison, in order:

1. Refuse unless `--i-approve-live-codex` is present and `codex` is on PATH.
2. Run the `direct-codex` arm in its own isolated seed worktree (separate from
   the dwm arm's worktree), red check before, bare `codex exec`, green check
   after.
3. Run the `dwm-controlled` arm via the existing V102 `run_live`.
4. Write `comparison.json` / `comparison.md`, assert
   `repo_tracked_diff_unchanged: true`, and stop.

Bounds: each arm is a single attempt with the V102 timeout bounds; no retry loop;
no third arm.

### Human gates

- HUMAN GATE 1: after this spec, seed/prompt design, and slice plan are written,
  stop for review before implementing the comparison recorder.
- HUMAN GATE 2: after the deterministic recorder and schema test pass, stop for
  explicit approval before the first live two-arm run.

## Safety And Verification Gates

- Each arm writes only inside its own seeded worktree under `out/live-proofs/`.
- All risky actions stay blocked by existing gates with safe defaults.
- `repo_tracked_diff_unchanged: true` after the run; the V103 manifest smoke
  verifies it.
- The deterministic schema test passes with no Codex binary present.
- The V102 review hard-gate and recorder logic are not modified.

## Evaluation Fixtures

- Reuse `fixtures/live-proof/seed/` and the V102 plan for the dwm arm.
- `fixtures/v103/manifest.json`: deterministic comparison-record fixtures covering
  a both-green comparison, a direct-arm-blocked comparison, a dwm-arm-failed
  comparison, and a tampered/malformed record that must be rejected. These run as
  `fixture-command`, never invoking Codex.

## Command Contract

```bash
# Deterministic, keep-gate (no Codex binary required)
python scripts/dwm_live_proof.py --self-test
python scripts/dwm_live_proof.py --manifest fixtures/v103/manifest.json --out out/v103/final

# Opt-in live two-arm comparison (requires codex on PATH and explicit approval)
python scripts/dwm_live_proof.py compare \
  --seed fixtures/live-proof/seed \
  --plan fixtures/live-proof/live-proof-1.workflow.plan.json \
  --out out/live-proofs/live-proof-2 \
  --i-approve-live-codex
python scripts/dwm_live_proof.py inspect --proof out/live-proofs/live-proof-2
```

Public manifest execution is limited to `fixtures/v103/manifest.json`.

## Acceptance Criteria

V103 is `keep` only if all of these hold:

- both arms ran a real `codex exec` on the same seeded task, recorded with real
  before/after verification output (no nulls);
- `out/live-proofs/live-proof-2/comparison.json` records both arms with
  populated metrics, the `differentiators` block, and an `honest_conclusion`
  containing no superiority/speed/cost claim;
- the `direct-codex` arm records `has_independent_review: false` and
  `legitimacy_verdict: null`; the `dwm-controlled` arm records the real review
  verdict and `has_hash_bound_bundle: true`;
- `repo_tracked_diff_unchanged: true`;
- `--self-test` and `fixtures/v103/manifest.json` pass with no Codex binary on
  PATH; the live comparison is opt-in and did not destabilize the keep gate;
- the V102 review hard-gate still passes unchanged
  (`--manifest fixtures/v102/manifest.json` keep);
- V94-V101 and all DWM repo tracked files are unchanged by the live run;
- README states only the bounded comparison claim and passes
  `scripts/check_readme_quality.py` (<=190 lines);
- the V88 roadmap reconciliation stays green: when registering V103 in
  `docs/spec.md` and `docs/automation-roadmap.md`, preserve the existing
  canonical version-descriptor terms (including "V102 deterministic live-proof
  recorder") and add the V103 descriptor consistently, then confirm
  `python scripts/check_contract.py` returns green.

The decision is `adjust` if the comparison runs but a metric is null, the
conclusion drifts toward superiority, or the direct arm borrows the dwm verdict.

The decision is `defer` if a safe two-arm live run cannot be closed within the
seeded worktrees and gates.

## Decision Output

Record the outcome in `docs/v103-decision.md` after implementation: the exact
compare command, both arms' verification returncodes, the differentiators, the
comparison.json sha256, and a restatement that this is an n=1 evidence-richness
comparison with no direct-agent superiority claim. Persist the non-reproducible
result in tracked `docs/releases/v103-live-proof-2.md`.

## Open Questions

- Whether a later slice adds a second task category (small refactor) before any
  multi-task comparison.
- Whether a deliberately tempting "game the test" task should be added to show
  the legitimacy review catching a direct-arm false green -- only if it can be
  done without fabricating an unrealistic scenario.
- Whether speed/cost should ever be recorded, given it would invite a
  superiority reading the evidence cannot yet support.
