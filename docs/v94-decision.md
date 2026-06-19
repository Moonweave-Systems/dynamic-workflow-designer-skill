# V94 Decision

Decision: keep.

Commands used to verify Control Deck scoring:

- `python scripts/dwm_control_deck_score.py --self-test`
- `python scripts/dwm_control_deck_score.py --manifest fixtures/v94/manifest.json --out out/control-deck-scores/v94-final`

Fixture evidence:

- `suite_id`: `v94-control-deck-score`
- `fixture_count`: 4
- `required_passed`: 4
- `decision`: `keep`

Covered blockers:

- Blocked narrative state blocks.
- Source-hash drift blocks.
- Unsafe voice policy blocks.

The V94 score is an operator-readiness score. It is not a public benchmark score
and does not claim upward trend performance.
