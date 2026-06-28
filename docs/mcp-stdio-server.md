# Depone MCP Stdio Server

Depone exposes its existing evidence and verification capabilities through a
stdlib-only MCP stdio server:

```bash
python -m depone mcp
```

Register that command with any MCP client that supports stdio servers. The
server offers these tools:

- `depone_evidence_ingest`: ingest external in-toto Statement or DSSE evidence
  as untrusted input.
- `depone_evidence_substrate`: emit Depone's in-toto/DSSE plus OTel evidence
  bundle from a capture manifest.
- `depone_verify`: verify an execution-evidence directory against a Depone plan.

This is the same evidence/verify surface as the CLI, exposed over JSON-RPC MCP
stdio. It does not change Depone's trust model: external evidence remains
untrusted, unsigned content remains content-addressed rather than signature
trusted, and current assurance remains bounded by the existing A1/local-observed
state.

The server writes only newline-delimited JSON-RPC protocol messages to stdout.
Diagnostics go to stderr.
