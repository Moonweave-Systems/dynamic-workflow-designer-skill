# V4 Parallel Scheduler Decision

Decision: keep

Command used to verify the V4 scheduler:

```bash
python scripts/orchestrate_workflow.py --self-test
```

Dogfood commands:

```bash
python scripts/orchestrate_workflow.py --start out/v3/v32-semantic-dogfood --out out/v4/v32-semantic-dogfood
python scripts/orchestrate_workflow.py --resume out/v4/v32-semantic-dogfood
```

Generated dogfood values:

- `run_id`: `v32-semantic-dogfood`
- `status`: `scheduled`
- `resume_state`: `resumable`
- `ready_phase_ids`: `evidence_review`
- `selected_phase_ids`: `evidence_review`
- `concurrency_cap`: 2
- `packet`: `packets/0001.evidence_review.packet.json`

This decision covers deterministic parallel-frontier scheduling only. It does
not claim worker execution, subagent spawning, worktree merging, commits,
pushes, dependency installation, production deployment, external messaging,
secret access, or autonomous workflow completion.
