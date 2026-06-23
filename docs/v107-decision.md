# V107 Decision

Decision: keep as the Agent Fabric control-plane direction spec.

Command used to verify this documentation-only PR:

```bash
python scripts/check_contract.py --tier changed
```

V107 records the final direction for a Keelplane-compatible agent system without
implementing that system. The accepted boundary is:

- Keelplane Core remains deterministic and owns contracts, evidence, decisions,
  and assurance.
- Agent Fabric is a separate execution-plane layer for profile routing,
  role/toolbelt compilation, context policy, harness adapter lowering, and
  evidence handoff.
- Native harnesses such as Codex, Claude Code, OpenCode/OMO, shell, LangGraph,
  or Conductor remain responsible for actual execution.

This decision intentionally does not claim:

- agent quality improvement;
- productivity improvement;
- direct-Codex, Claude Code, OpenCode, or OMO superiority;
- live model execution;
- hard per-agent tool filtering in any native harness;
- production readiness for the existing role pack.

The next implementation slice should be contract-only:

1. add role, toolbelt, capability, compile-report, invocation, and agent-result
   schemas;
2. add fixtures for exact, approximated, and unsupported-critical tool mappings;
3. reject reviewer write access, undeclared MCP tools, missing evidence
   obligations, and agent-written authoritative evidence;
4. avoid live model calls until deterministic fixture behavior is stable.

The current `agents/openai.yaml`, `packaging/dwm-roles.json`, V22 role pack
contract, V105 final profiles, and V105 agent-team spec are useful inputs, but
they are not yet the world-class Agent Fabric. V107 keeps the distinction
explicit so later work can build the Agent Fabric without weakening Keelplane's
evidence boundary.
