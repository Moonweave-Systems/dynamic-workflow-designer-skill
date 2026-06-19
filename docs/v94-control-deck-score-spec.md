# V94 Control Deck Score Spec

Status: implemented operator-readiness scoring in
`scripts/dwm_control_deck_score.py`.

## Research and Prior Art

V93 made the workflow legible with a Control Deck. V94 adds a deterministic
readiness score so the operator can see whether the deck is complete without
turning the score into a public benchmark claim.

## Product Position and Non-Goals

V94 is an operator-status score. It is not a model-quality score, benchmark
score, or upward trend graph.

Non-goals:

- do not claim benchmark success,
- do not claim upward performance,
- do not score model quality,
- do not execute commands,
- do not create worktrees or sessions,
- do not replace artifact and source-hash checks with narrative confidence.

## Workflow Architecture

`scripts/dwm_control_deck_score.py` reads:

- V93 workflow narrative,
- V88 roadmap reconciliation,
- V89 command safety,
- V90 workflow activation,
- V92 evidence oracle.

It emits:

- `control-deck-score.json`,
- `control-deck-score.md`,
- `status.json`.

The score covers six axes, each worth two points:

- Chart,
- Gate,
- Activation,
- Oracle,
- Source Integrity,
- Voice Policy.

The output includes `claim_policy` with `is_public_benchmark: false` and
`is_upward_trend_claim: false`.

## Execution Model

Run fixture coverage:

```bash
python scripts/dwm_control_deck_score.py --self-test
python scripts/dwm_control_deck_score.py --manifest fixtures/v94/manifest.json --out out/control-deck-scores/v94-final
```

Run canonical score:

```bash
python scripts/dwm_control_deck_score.py score --narrative out/workflow-narratives/v93-canonical/workflow-narrative.json --roadmap out/roadmap-reconciliations/v88-canonical/roadmap-reconciliation.json --command-safety out/command-safety/v89-final/summary.json --activation out/workflow-activations/v90-canonical/workflow-activation.json --oracle out/evidence-oracles/v92-canonical/evidence-oracle.json --out out/control-deck-scores/v94-canonical
```

## Safety and Verification Gates

V94 blocks when narrative readiness is blocked, source hashes drift, voice
policy overclaims, or execution policy is not read-only.

## Evaluation Fixtures

`fixtures/v94/manifest.json` covers:

- ready score at 100 percent,
- blocked narrative state,
- source-hash drift,
- unsafe voice policy.

## Release Plan

V94 adds Control Deck score generation to the changed-surface contract tier and
keeps score promotion separate from public benchmark graph promotion.
