# Depone
> Workflow designer + cross-platform evidence verifier for multi-agent AI systems.
[![License: MIT](https://img.shields.io/badge/License-MIT-4F46E5.svg)](LICENSE)
[![Agent skill](https://img.shields.io/badge/agent%20skill-Codex-4F46E5.svg)](SKILL.md)
[![Release](https://img.shields.io/github/v/release/Moonweave-Systems/Depone?color=4F46E5)](https://github.com/Moonweave-Systems/Depone/releases)
[![Contract](https://img.shields.io/badge/contract-self--tested-059669.svg)](scripts/check_contract.py)

![Depone hero](assets/dwm-hero.svg)

**Depone** generates safe workflow contracts and verifies agent-session
execution evidence. It does not execute agents - it makes runs from other
frameworks and agent sessions (Codex, Claude, Conductor, LangGraph)
trustworthy.

## Quickstart

```bash
# Installation from source. PyPI publishing is not active yet.
git clone https://github.com/Moonweave-Systems/Depone
cd Depone
python -m pip install --no-deps .

# Check the agent-safe tool surface.
depone doctor --json

# Run the offline design -> compile -> verify demo.
depone demo --json --out depone-quickstart

# Or step by step:
depone design "audit all API routes for authentication" --surface . --out plan.json
depone validate plan.json
depone compile plan.json --target conductor --out workflow.yaml
depone verify plan.json --evidence ./evidence/ --out report.json --operator-view-out operator-view.md

# MCP stdio server for MCP-capable agents: python -m depone mcp
```

To independently smoke-test source installation in a clean virtualenv, run:

```bash
python scripts/install_smoke.py --json
```

The smoke installs Depone from the local source tree with `--no-deps`, runs the
installed `depone doctor`, and re-validates a committed team-ledger artifact.
It does not publish a package or claim PyPI readiness. The latest checked-in
machine artifact is
[`docs/install-readiness/install-smoke.json`](docs/install-readiness/install-smoke.json).

Agent-session evidence loop:

```bash
depone run --runner-sandbox ./runner-worktree \
  --source-fixture depone/fixtures/agent_fabric/reference_adapter_shell.json \
  --out ../observer/evidence-run --allow-touched-file sample.txt \
  --verify-plan plan.json --verify-evidence ./evidence \
  --json -- python -m unittest
```

`depone run` is the small native runner-facing entrypoint for the same
evidence loop as `depone evidence-run`. It does not add a scheduler or execute
agents by itself; it preserves the existing observe -> substrate -> ingest ->
verify boundary.

## What Exists Today
Depone ships the stdlib-only CLI, a strict plan validator, a Conductor YAML
emitter, a generic evidence adapter, and the bounded verification engine.
Run model: a `slice` is one atomic worker task, a `wave` is a gated group of
one or more slices, and a `run` is one or more waves verified by receipts and
evidence gates.

## Command Reference

| Command | Description |
|---|---|
| `depone doctor` | Check package-local readiness for agent-session use |
| `depone design` | Generate a safe workflow contract from a broad objective |
| `depone validate` | Validate a plan.json against the schema v0.5 |
| `depone compile` | Translate a plan into a target framework format (Conductor YAML) |
| `depone verify` | Verify execution evidence against a plan |
| `depone observe` | Capture observer-owned evidence for a runner sandbox |
| `depone evidence-substrate` | Emit in-toto/DSSE and OTel GenAI-shaped evidence |
| `depone evidence-ingest` | Verify external evidence subject digests as untrusted input |
| `depone evidence-chain` | Verify an ordered append-only capture manifest chain |
| `depone evidence-run` | Run the common observe -> substrate -> ingest -> verify loop |
| `depone run` | Native-runner convenience alias for `evidence-run`; not a scheduler |
| `depone team-launch-preflight` | Non-executing gate for planned team lanes |
| `depone next` | Re-validate an evidence-run directory and recommend the next safe action without executing it |
| `depone advance` | Re-validate with `next`, then run exactly one existing evidence-run continuation when unblocked |
| `depone mcp` | Serve the same evidence/verify capabilities over MCP stdio |
| `depone demo` | Run a complete design -> compile -> verify cycle |

Internal compatibility commands remain available for existing automation:
`validate-contracts` and the `agent-fabric-*` command family.

## Normal Loop

Agent sessions perform work in a runner sandbox, then call `depone run --json`.
Depone writes observer-owned evidence such as `observer-capture.json`,
`capture-manifest.json`, `evidence-bundle.json`, `ingest-verdict.json`, and
`verify-report.json`, then returns one JSON verdict.

## Product Thesis

> Depone designs multi-agent workflows and verifies their execution evidence.
> It does not execute agents. It makes runs from other frameworks trustworthy.

`design` makes safe workflow contracts, `compile` emits target artifacts, and
`verify` checks execution evidence against the plan. `run` is the evidence-native
entrypoint for the existing local evidence loop: a compatibility alias over
`evidence-run`, not a general-purpose agent-team scheduler. `next` is the
non-executing revalidation gate. `advance` is the explicit one-step operator
gate: it refuses unless `next` returns `continue` with zero blockers, then runs
exactly one `evidence-run` continuation and writes `advance-decision.json`.

## Safety Model

Depone treats artifacts, not model claims, as the source of truth.
Generated `out/` directories are verification evidence, not source of truth.
Destructive actions, network access, dependency installation, secret access,
production deployment, and history rewrite require explicit gates.

## Roadmap

Depone is moving from agent-safe CLI and evidence substrate toward stronger
session receipt adapters, operator signing policy, and A2 isolation paths. The
next team-runtime bridge is `team-launch-preflight`, a non-executing gate that
checks planned lane launchability without launching agents or creating
worktrees. Its committed fixture directory is
[`docs/team-launch-preflight/`](docs/team-launch-preflight/), with generated JSON
artifacts created from source inputs rather than copied from older fixtures.

## What Is Still Honest
Depone claims **no direct-agent superiority** - it is a design + verification layer, not an agent runtime.
It does not claim upward performance. It is not a public benchmark graph.
public trend promotion requires real release history and measured improvements
over established baselines; it is blocked until release history supports it.
Trend promotion is blocked until release history supports the claim.
The skill is named `depone`.

### Inspection & diagnostics

```bash
python scripts/dwm.py doctor
python scripts/dwm.py commands --kind product
python scripts/check_readme_quality.py README.md
```
Legacy diagnostics: `python scripts/dwm_demo.py run --out out/demo/quickstart`, `python scripts/dwm_demo.py inspect --demo out/demo/quickstart`, `python scripts/dwm.py status --run out/v9/v32-semantic-dogfood`, `python scripts/dwm.py next --run out/v9/v32-semantic-dogfood`, `python scripts/dwm.py commands --kind release`.

## Evidence Graphs

![Dogfood progress](assets/dwm-dogfood-progress.svg)
*Dogfood benchmark progression across attempts.*

![Live benchmark](assets/dwm-live-benchmark.svg)
*Live benchmark history - not a public benchmark graph. Benchmark visuals are source-bound.*

## Quality

Core CLI commands include built-in `--self-test`, including `verify`,
`observe`, `evidence-substrate`, `evidence-ingest`, `run`/`evidence-run`,
`next`/`evidence-next`, `advance`, and `demo`.

```bash
python scripts/install_smoke.py --json
python scripts/check_contract.py --tier changed
```

## Position

Depone is not a prompt-only workflow router and not a clone of any one
runtime. It is a design + verification layer above existing execution engines.
DWM Core keeps agentic work inspectable, reproducible, resumable, and honest
about what has actually been executed.
## Documentation
- [`docs/agent-tool-contract.md`](docs/agent-tool-contract.md): agent-facing CLI and evidence contract.
- [`docs/command-reference.md`](docs/command-reference.md), [`docs/spec.md`](docs/spec.md), and [`docs/release-history.md`](docs/release-history.md): command, product, and release references.
- [`references/workflow-plan-schema.md`](references/workflow-plan-schema.md) and [`SKILL.md`](SKILL.md): plan schema and installed Codex skill.

## License

MIT. See [`LICENSE`](LICENSE).
