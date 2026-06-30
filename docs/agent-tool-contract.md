# Depone Agent Tool Contract

Depone is an agent-session evidence tool. Agents call it to generate safe
workflow contracts, capture observer-owned evidence, serialize evidence into
portable shapes, and verify claims without trusting their own final message.

## Agent-Safe Command Surface

All agent-safe commands are stdlib-only, work from a source install with
`python -m pip install --no-deps .`, and avoid platform-specific shell
assumptions. Prefer `python -m depone ...` in docs, tests, and agent prompts so
Windows, macOS, and Linux use the active interpreter.

Core official surface:

| Command | Purpose |
| --- | --- |
| `depone doctor --json` | Check package-local readiness before a session. |
| `depone design --json` | Generate a safe workflow contract scaffold. |
| `depone validate --json` | Validate a workflow contract. |
| `depone compile --json` | Emit a target workflow artifact. |
| `depone verify --json` | Verify execution evidence against a plan. |
| `depone observe --json` | Capture observer-owned evidence for a runner sandbox. |
| `depone evidence-substrate --json` | Emit in-toto/DSSE and OTel GenAI-shaped evidence. |
| `depone evidence-ingest --json` | Verify untrusted external evidence subject digests. |
| `depone run --json` | Native runner-facing alias for the existing evidence loop. |
| `depone next --json` | Re-validate an evidence-run directory and select the next safe action. |
| `depone mcp` | Serve evidence tools over MCP stdio. |
| `depone demo --json` | Run the offline design, compile, verify demo. |

Convenience wrapper:

| Command | Purpose |
| --- | --- |
| `depone run --json` | Native-runner alias for the existing evidence loop; behavior-compatible with `evidence-run`. |
| `depone evidence-run --json` | Run the common observe, substrate, ingest, and verify loop in one command. |
| `depone next --json` | Native operator alias for `evidence-next`; re-validates artifacts and recommends a next action without executing it. |
| `depone evidence-next --json` | Re-validate capture, runner receipt, statement subjects, and ingest decision before continuing. |

The older `agent-fabric-*` commands remain callable for compatibility but are
not the preferred agent-facing surface.

`depone run` is an evidence-native command surface, not a promise that Depone
executes or schedules agent teams. It preserves the same fail-closed evidence
semantics as `evidence-run`; compatibility callers may continue using
`python -m depone evidence-run --runner-sandbox ...`.

When `depone run` / `evidence-run` launches a uid runner itself with
`--runner-user`, it also writes `runner-receipt.json` under the output
directory. That receipt is rehashed as a DSSE statement subject and reflected in
the OTel GenAI-shaped spans; it does not raise assurance by itself.

`depone next` consumes the artifact directory produced by `depone run`. It
recomputes the capture, runner receipt, in-toto/DSSE subject digests, and OTel
shape before returning `continue` or `blocked`. A recorded `ingest-verdict.json`
is reported but not trusted as the decision source.

## Machine Contract

When `--json` is present, stdout is exactly one JSON object. Human-readable logs
belong on stderr or are suppressed. Paths in JSON are ordinary strings and must
not depend on a platform-specific separator for the verdict meaning. Errors use:

```json
{"error":{"code":"ERR_EXAMPLE","message":"what failed","path":null}}
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | success, pass, or verified |
| `1` | fail, blocked, or refuted |
| `2` | inconclusive or insufficient evidence |
| `3` | usage, config, or input error |
| `4` | internal/runtime error |

Agent callers should treat `2` as a useful result, not a crash: it means Depone
could not honestly prove or refute the claim with the supplied evidence.

## Minimal Evidence Folder

Agent sessions should preserve these artifacts whenever available:

| Artifact | Purpose |
| --- | --- |
| `run-metadata.json` | Run id, rounds, and invocation records. |
| `command.log` | Verification command transcript or structured receipt. |
| `git-diff.patch` | Workspace delta observed after execution. |
| `test.log` | Test or verifier output. |
| `agent-final-message.txt` | The agent's claimed outcome. |
| `evidence-contract.json` | Required evidence declaration. |

Absent required subjects make evidence `inconclusive`. Present digest mismatch
is `blocked`. A matching subject digest can pass subject-binding verification,
but foreign predicates remain opaque unless Depone explicitly recognizes them.

The final message is never the source of truth by itself. Depone compares claims
against receipts, logs, diffs, manifests, and digests so planned work and
executed work stay separate.

## Canonical Agent Loop

```bash
python -m depone doctor --json
python -m depone design "audit all API routes" --surface . --out plan.json --json
python -m depone validate plan.json --json
python -m depone run --runner-sandbox ./runner-worktree \
  --source-fixture depone/fixtures/agent_fabric/reference_adapter_shell.json \
  --out ../observer/evidence-run --allow-touched-file sample.txt \
  --verify-plan plan.json --verify-evidence ./evidence \
  --json -- python -m unittest
python -m depone next --evidence-dir ../observer/evidence-run \
  --out ../observer/evidence-next.json --json
```

The expanded loop remains available when agents need to inspect each artifact:

```bash
python -m depone observe --runner-sandbox ./runner-worktree --source-fixture-hash <sha256> \
  --out ../observer/observer-capture.json --log ../observer/verify-log.json \
  -- python -m unittest
python -m depone evidence-substrate --capture-manifest capture-manifest.json \
  --out evidence-bundle.json --json
python -m depone evidence-ingest --dsse evidence-bundle.json:dsse_envelope \
  --artifact depone-capture-manifest=capture-manifest.json:json \
  --out ingest-verdict.json --json
python -m depone verify plan.json --evidence ./evidence --out report.json --json
```

Depone does not execute the agent task. It records, serializes, and verifies
evidence from a run performed by another agent or framework.
