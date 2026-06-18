# V76 Large Workflow Queue Bridge Spec

Status: implemented V75-to-V46 queue bridge in
`scripts/dwm_large_workflow_queue_bridge.py`.

## Research and Prior Art

Current agent tooling is moving toward longer-running agent tasks, resumable
local execution, hooks, handoffs, guardrails, tracing, and human review. DWM's
position is compatible with that direction, but the product should not depend
on any single harness or market story. The source of truth remains local,
deterministic artifacts.

V75 selected the next large-workflow action from dogfood control evidence. V76
turns that selected action into a queue packet and, when requested, feeds it
into the existing V46 long-run workflow queue.

## Product Position and Non-Goals

V76 is a bridge, not an executor. It proves that a `command_ready` V75 selection
can become a V46 queue packet while preserving evidence paths, risk codes, and
source hashes.

Non-goals:

- do not execute the selected command,
- do not bypass V75 blockers or human gates,
- do not treat generated queue artifacts as public benchmark proof,
- do not claim market superiority,
- do not promote write, network, deploy, secret, or external-message work
  without a separate human gate.

This bridge does not execute the selected command.

## Workflow Architecture

`scripts/dwm_large_workflow_queue_bridge.py` reads
`large-workflow-next.json`, validates that the selection is
`next-workflow-ready` with `command_ready`, materializes one queue packet, and
writes:

- `queue-bridge.json`,
- `queue-packets.json`,
- `queue-bridge.md`,
- `status.json`,
- manifest `summary.json`.

If `--queue-out` is provided, the bridge calls the V46 queue builder and writes
a real `queue.json` / `next-action.md` queue under `out/workflow-queues/`.

## Execution Model

Bridge the canonical V75 selection into a queue packet and queue:

```bash
python scripts/dwm_large_workflow_queue_bridge.py bridge --selection out/large-workflow-next/v75-canonical/large-workflow-next.json --out out/large-workflow-queue-bridge/<bridge_id> --queue-out out/workflow-queues/<queue_id>
```

Run fixture coverage:

```bash
python scripts/dwm_large_workflow_queue_bridge.py --manifest fixtures/v76/manifest.json --out out/large-workflow-queue-bridge/v76-final
```

## Safety and Verification Gates

The bridge blocks if:

- the V75 selection is not `next-workflow-ready`,
- the V75 decision is not `command_ready`,
- the V75 selection carries blockers or gates,
- the selected command or candidate is missing,
- the selected candidate carries write, delete, network, deploy, secret, or external-message risk,
- the expected selection hash mismatches,
- required evidence paths are missing,
- the V46 queue builder does not return a ready next action.

Safe default: preserve the bridge receipt and do not emit a runnable queue
command.

## Evaluation Fixtures

`fixtures/v76/manifest.json` covers:

- ready V75 selection creating one queue packet and a ready V46 queue,
- blocked V75 selection blocking queue materialization,
- human-gated V75 selection blocking queue materialization,
- selection hash drift blocking queue materialization.

## Release Plan

V76 adds the queue bridge to the release command corpus. The next slice can use
the queued packet as the input to a bounded execution preflight, but execution
remains separate from selection and queue materialization.
