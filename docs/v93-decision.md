# V93 Decision

Decision: keep.

Commands used to verify workflow narrative and Control Deck rendering:

- `python scripts/dwm_workflow_narrative.py --self-test`
- `python scripts/dwm_workflow_narrative.py --manifest fixtures/v93/manifest.json --out out/workflow-narratives/v93-final`

Fixture evidence:

- `suite_id`: `v93-workflow-narrative`
- `fixture_count`: 4
- `required_passed`: 4
- `decision`: `keep`

Covered blockers:

- Stale roadmap version blocks.
- Activation source-hash drift blocks.
- Blocked oracle evidence blocks.

V93 may render Chart, Gate, Oracle, and Next move labels, but those labels are
status rendering only. Artifacts and source hashes remain the source of truth.
