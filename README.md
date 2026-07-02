# Depone

> Non-executing verifier and evidence-contract source of truth for agent evidence.

[![License: MIT](https://img.shields.io/badge/License-MIT-4F46E5.svg)](LICENSE)
[![Agent skill](https://img.shields.io/badge/agent%20skill-Codex-4F46E5.svg)](SKILL.md)
[![Release](https://img.shields.io/github/v/release/Moonweave-Systems/Depone?color=4F46E5)](https://github.com/Moonweave-Systems/Depone/releases)
[![Contract](https://img.shields.io/badge/contract-self--tested-059669.svg)](scripts/check_contract.py)

![Depone hero](assets/dwm-hero.svg)

**Depone** is a non-executing verifier - re-derives A0/A1/A2 from signed
evidence bytes, offline, cannot raise the grade.

Depone owns the evidence contract for capture manifests, runner receipts,
isolation facts, DSSE envelopes, team ledgers, and error codes. Runtimes such as
[witnessd](https://github.com/Moonweave-Systems/witnessd) execute work and emit
evidence; Depone re-derives the verdict from those bytes. The two repositories
are developed together in the Moonweave workspace but remain separate products.
Their only coupling is the evidence contract.

## Quickstart

```bash
# Installation from source. PyPI publishing is not active yet.
git clone https://github.com/Moonweave-Systems/Depone
cd Depone
python -m pip install --no-deps .

# Check the package-local verifier surface.
depone doctor --json

# Run the offline design -> compile -> verify demo.
depone demo --json --out depone-quickstart

# Re-derive a committed evidence bundle.
depone evidence-ingest --self-test
depone evidence-chain --self-test
depone team-ledger --self-test
```

Source installation smoke is `python scripts/install_smoke.py --json`. It
installs Depone from the local source tree with `--no-deps`, runs the installed
`depone doctor`, and re-validates a committed team-ledger artifact. It does not
publish a package or claim PyPI readiness. The latest checked-in artifact is
[`docs/install-readiness/install-smoke.json`](docs/install-readiness/install-smoke.json).

## What Exists Today

Depone ships a stdlib verifier package, a strict plan validator, evidence
adapters, DSSE/in-toto-shaped substrate helpers, and offline gates for
agent-session evidence. It can re-derive A0/A1/A2 assurance from:

- capture manifests and observer captures,
- runner receipts and local capability receipts,
- isolation facts,
- signed evidence bundles,
- team-ledger and merge-attempt artifacts.

It cannot turn a weak capture into a stronger one. If the bytes only support
A0, the verifier must report A0. If observer capture or isolation evidence is
missing, the verifier must not infer it from prose or operator intent.

The package also contains historical DWM design and workflow-contract tooling.
That tooling is part of the repository today, but the release claim for this
wave is the verifier and evidence-contract role, not a new agent runtime.

## Command Reference

| Command | Description |
|---|---|
| `depone doctor` | Check package-local readiness for agent-session use |
| `depone demo` | Run a local design -> compile -> verify demo |
| `depone validate` | Validate a plan JSON document against the schema |
| `depone compile` | Translate a plan into a target framework artifact |
| `depone verify` | Verify evidence against a plan |
| `depone observe` | Capture observer-owned local evidence for a runner sandbox |
| `depone evidence-substrate` | Emit DSSE/in-toto and OTel GenAI-shaped evidence |
| `depone evidence-ingest` | Verify external evidence subject digests as untrusted input |
| `depone evidence-chain` | Verify an ordered append-only capture-manifest chain |
| `depone team-ledger` | Re-derive team-ledger assurance from committed artifacts |
| `depone team-launch-preflight` | Non-executing gate for planned team lanes |
| `depone team-worktree-prep` | Create/select local lane worktrees without launching agents |
| `depone next` | Re-validate an evidence-run directory and recommend a safe next action |
| `depone mcp` | Serve the same evidence/verify capabilities over MCP stdio |

Internal compatibility commands remain available for existing automation:
`validate-contracts`, `run`/`evidence-run`, `advance`, and the
`agent-fabric-*` command family. Treat those as compatibility surfaces unless a
fresh release note promotes a narrower claim.

## Normal Loop

1. An external runtime executes work in its own sandbox.
2. The runtime emits capture, receipt, isolation, and signing artifacts.
3. Depone reads the artifact bytes offline.
4. Depone re-derives the verdict and assurance grade from the contract.
5. Operators compare that verifier result with the runtime's claim.

For the two-product flagship, witnessd is the executing half and Depone is the
verifying half. witnessd emits evidence bundles; Depone checks whether those
bundles really support the claimed A0/A1/A2 result.

## Safety Model

Depone treats artifacts, not model claims, as the source of truth.
Generated `out/` directories are verification evidence, not source of truth.
Destructive actions, network access, dependency installation, secret access,
production deployment, and history rewrite require explicit gates.

The verifier must not upgrade assurance from self-report alone. A1/A2 report
assurance depends on evidence that can be re-derived from signed or hash-bound
artifact bytes. A3/keyless transparency-log attestation is not implemented.

## What Is Still Honest

Depone claims **no direct-agent superiority** - it is a design + verification
layer, not an agent runtime. It does not claim upward performance. It is not a
public benchmark graph. public trend promotion requires real release history
and measured improvements over established baselines; it is blocked until
release history supports it. Trend promotion is blocked until release history
supports the claim. The skill is named `depone`.

Known limits:

- The July 1, 2026 review found a P0 path where unsigned JSON could spoof
  observed assurance. PR #62 repaired this by requiring trusted-observer
  provenance outside the evidence directory plus Ed25519 DSSE for report-level
  observed assurance.
- HMAC-backed provenance remains dependent on operator policy. An Ed25519-only
  deployment closes that residual policy path.
- Transparency-log and Sigstore-style A3/keyless attestation are not implemented.
- `scripts/dwm_*.py` remains a large historical double-engine beside the
  `depone/` package. It is known release debt and is intentionally not refactored
  in this hardening wave.
- `CLAUDE.md` still says there is no `pyproject.toml`, while this release has a
  real `pyproject.toml`. That documentation contradiction is known debt, not a
  verifier-contract change.

### Inspection

```bash
python scripts/dwm.py doctor
python scripts/dwm.py commands --kind product
python scripts/check_readme_quality.py README.md
python scripts/check_contract.py --tier changed
```

Legacy diagnostics: `python scripts/dwm_demo.py run --out out/demo/quickstart`,
`python scripts/dwm_demo.py inspect --demo out/demo/quickstart`, `python scripts/dwm.py status --run out/v9/v32-semantic-dogfood`, `python scripts/dwm.py next --run out/v9/v32-semantic-dogfood`, `python scripts/dwm.py commands --kind release`.

## Evidence Graphs

![Dogfood progress](assets/dwm-dogfood-progress.svg)
*Dogfood benchmark progression across attempts.*

![Live benchmark](assets/dwm-live-benchmark.svg)
*Live benchmark history - not a public benchmark graph. Benchmark visuals are source-bound.*

## Quality

Release readiness is checked with:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
```

## Position

Depone is not a prompt-only workflow router and not a clone of any one runtime.
It is the offline verifier and evidence-contract authority beside execution
engines. DWM Core keeps agentic work inspectable, reproducible, resumable, and
honest about what has actually been evidenced.

## Documentation

- [`docs/agent-tool-contract.md`](docs/agent-tool-contract.md): agent-facing CLI and evidence contract.
- [`docs/command-reference.md`](docs/command-reference.md), [`docs/spec.md`](docs/spec.md), and [`docs/release-history.md`](docs/release-history.md): command, product, and release references.
- [`references/workflow-plan-schema.md`](references/workflow-plan-schema.md) and [`SKILL.md`](SKILL.md): plan schema and installed Codex skill.

## License

MIT. See [`LICENSE`](LICENSE).
