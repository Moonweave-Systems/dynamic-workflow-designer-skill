# V100 Promotion Evidence Spec

Status: implemented promotion evidence ledger in
`scripts/dwm_promotion_evidence.py`.

## Research And Prior Art

V97 records internal benchmark readiness, V98 selects the next source-only
wave, and V99 verifies that the dogfood evidence wave has usable acquisition
evidence. The remaining gap is not a public graph renderer. The gap is a
source-bound ledger that says whether the current evidence can even enter
human review for README graph publication.

## Product Position And Non-Goals

V100 keeps Keelplane honest: it connects `wave-receipt.json` and
`benchmark-readiness.json` without treating either artifact as a public
benchmark.

Non-goals:

- do not execute commands,
- do not publish README assets,
- do not create or edit tracked benchmark graphs,
- do not bypass human review for README benchmark publication,
- do not claim upward benchmark progress.

## Workflow Architecture

`scripts/dwm_promotion_evidence.py` reads:

- V99 `wave-receipt.json`,
- V97 `benchmark-readiness.json`.

It writes:

- `promotion-evidence.json`,
- `promotion-evidence.md`,
- `status.json`.

The ledger decision is `promotion_evidence_recorded` when source evidence is
valid. Canonical V100 is expected to record internal evidence while keeping
public graph promotion blocked, because current readiness still lacks public
benchmark promotion evidence.

The claim policy includes `promotion_evidence_is_public_benchmark`: false.

## Execution Model

Canonical command:

```bash
python scripts/dwm_promotion_evidence.py record --receipt out/wave-receipts/v99-canonical/wave-receipt.json --readiness out/benchmark-readiness/v97-canonical/benchmark-readiness.json --out out/promotion-evidence/v100-canonical
```

The V100 promotion evidence ledger does not execute commands, create worktrees,
use the network, or publish assets. README graph publication remains blocked until promotion evidence passes and a human approves publication.

## Safety And Verification Gates

The ledger blocks if:

- the receipt was not produced by V99,
- the receipt is not `wave_receipt_ready`,
- the selected wave is not `dogfood-evidence-wave`,
- the receipt overclaims public benchmark status,
- readiness was not produced by V97,
- readiness was not recorded.

Even when `promotion_ready_for_human_review` is true,
`public_benchmark_publish_allowed` remains false until explicit human review.

## Evaluation Fixtures

`fixtures/v100/manifest.json` covers:

- internal evidence recorded while public graph promotion remains blocked,
- promotion-ready evidence still requiring human review,
- blocked receipt blocking the ledger,
- overclaim receipt blocking the ledger.

## Release Plan

Add V100 to the release command corpus, command reference, roadmap,
release history, and contract checks. The next workflow should use this ledger
to decide whether to continue dogfood evidence acquisition or stop at a human
publication gate.
