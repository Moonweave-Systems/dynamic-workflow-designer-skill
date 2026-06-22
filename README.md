# Keelplane

> Workflow designer + cross-platform evidence verifier for multi-agent AI systems.

[![License: MIT](https://img.shields.io/badge/License-MIT-4F46E5.svg)](LICENSE)
[![Agent skill](https://img.shields.io/badge/agent%20skill-Codex-4F46E5.svg)](SKILL.md)
[![Release](https://img.shields.io/github/v/release/Moonweave-Systems/keelplane?color=4F46E5)](https://github.com/Moonweave-Systems/keelplane/releases)
[![Contract](https://img.shields.io/badge/contract-self--tested-059669.svg)](scripts/check_contract.py)

![Keelplane hero](assets/dwm-hero.svg)

**Keelplane** designs multi-agent workflows and verifies their execution
evidence. It does not execute agents — it makes runs from other frameworks
(Conductor, LangGraph) trustworthy.

## Quickstart

```bash
# Installation (pip install coming in V104.1)
git clone https://github.com/Moonweave-Systems/keelplane
cd keelplane

# Run the full design → compile → verify cycle
python -m keelplane demo

# Or step by step:
python -m keelplane design "audit all API routes for authentication" --surface . --out plan.json
python -m keelplane validate plan.json
python -m keelplane compile plan.json --target conductor --out workflow.yaml
python -m keelplane verify plan.json --evidence ./evidence/ --out report.json
```

## Installation

```bash
pip install keelplane
```

No external dependencies required — the core uses Python stdlib only.
Optional compile targets (`keelplane[conductor]`) add framework-specific
emitters.
> **Note:** `pip install keelplane` is not yet available on PyPI.
> Clone from GitHub and use `python -m keelplane` for now (V104.1 target).

## CLI Commands

| Command | Description |
|---|---|
| `keelplane design` | Decompose a broad objective into a structured workflow plan |
| `keelplane validate` | Validate a plan.json against the schema v0.5 |
| `keelplane compile` | Translate a plan into a target framework format (Conductor YAML) |
| `keelplane verify` | Verify execution evidence against a plan (4-check engine) |
| `keelplane demo` | Run a complete design → compile → verify cycle |

### Verify: 4-Check Engine

1. **Gate Compliance** — Were declared risk_gates respected? (write, network, approval gates)
2. **Handoff Integrity** — Do declared handoff artifacts exist with matching SHA-256 hashes?
3. **Adversarial Check** — Can claims be refuted against ground truth?
4. **Budget Adherence** — Did execution stay within max_agents, max_rounds, and budget limits?

## Pipeline

```
keelplane design "audit all API routes" --out plan.json
       │
       ▼  compile --target conductor
    workflow.yaml
       │
       ▼  conductor run workflow.yaml     ← NOT Keelplane (execution)
    ./run-output/
       │
       ▼  verify plan.json --evidence ./run-output/
    verification-report.json              ← Keelplane (evidence)
```

## Product Thesis

> Keelplane designs multi-agent workflows and verifies their execution evidence.
> It does not execute agents. It makes runs from other frameworks trustworthy.

- **design**: decompose broad objectives into the workflow plan schema (phases,
  workers, handoffs, gates, budgets).
- **compile**: translate plans into target framework formats (Conductor YAML
  first; LangGraph Python later).
- **verify**: consume raw execution evidence from any framework, check it
  against the plan, produce hash-signed verification reports.

## Safety Model

Keelplane treats artifacts, not model claims, as the source of truth. A
workflow is trusted only when the relevant plan, packet, prompt, evidence,
review, approval, and status artifacts match their hash ledgers.

Generated `out/` directories are verification evidence, not source of truth.
They are never hand-edited; artifacts and source hashes are the source of truth.

Keelplane does not claim unrestricted autonomous execution. Destructive actions,
network access, dependency installation, secret access, external messaging,
database migration, production deployment, and history rewrite require explicit
gates with a safe default.

## Evidence Model & Verification Commands

Keelplane claims **no direct-agent superiority** — it is a design + verification
layer, not an agent runtime. It is **not a public benchmark graph**; public trend promotion requires real release history and measured improvements over established baselines.

### Inspection & diagnostics

```bash
# Quickstart demo evidence
python scripts/dwm_demo.py run --out out/demo/quickstart
python scripts/dwm_demo.py inspect --demo out/demo/quickstart

# Operator-state inspection
python scripts/dwm.py status --run out/v9/v32-semantic-dogfood
python scripts/dwm.py next --run out/v9/v32-semantic-dogfood

# Available commands
python scripts/dwm.py commands --kind product
python scripts/dwm.py commands --kind release

# README quality gate
python scripts/check_readme_quality.py readme.md
```

### Benchmark graphs & progression

![Dogfood progress](assets/dwm-dogfood-progress.svg)
*Dogfood benchmark progression across attempts.*

![Live benchmark](assets/dwm-live-benchmark.svg)
*Live benchmark history — not a public benchmark graph.*

## Quality

All CLI commands include built-in `--self-test`:

```bash
python -m keelplane design --self-test    # 4/4 passed
python -m keelplane compile --self-test   # 4/4 passed
python -m keelplane validate --self-test  # 3/3 passed
python -m keelplane verify --self-test    # 3/3 passed
python -m keelplane demo --self-test      # full cycle passed
```

Run the release contract before publishing changes:

```bash
python scripts/check_contract.py --tier changed
```

## Position

Keelplane is not a prompt-only workflow router and not a clone of any one
runtime. It is a design + verification layer above existing execution engines.
DWM Core keeps agentic work inspectable, reproducible, resumable, and honest
about what has actually been executed.

## Documentation

- [`docs/v104-product-direction-spec.md`](docs/v104-product-direction-spec.md): V104 product direction and CLI spec.
- [`docs/spec.md`](docs/spec.md): product spec and release criteria.
- [`docs/command-reference.md`](docs/command-reference.md): full command and artifact reference.
- [`docs/release-history.md`](docs/release-history.md): versioned implementation history.
- [`references/workflow-plan-schema.md`](references/workflow-plan-schema.md): plan schema v0.5 reference.
- [`references/workflow-patterns.md`](references/workflow-patterns.md): canonical workflow patterns.
- [`SKILL.md`](SKILL.md): installed agent skill for Codex environments.

## License

MIT. See [`LICENSE`](LICENSE).
