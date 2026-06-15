# DWM Branding

DWM stands for **Deterministic Workflow Machine**.

It is the product name for this repository's agent workflow control-plane. The
legacy Codex skill entrypoint remains `dynamic-workflow-designer` so existing
skill activation, fixtures, and `workflow.plan.json` contracts continue to
work.

The preferred repository slug is `dwm`. The old
`dynamic-workflow-designer-skill` slug may appear only in historical references
or compatibility redirects.

## Position

DWM is not an unchecked agent launcher. It is a deterministic control-plane for
large AI-assisted work:

```text
goal
-> workflow plan
-> packet
-> dispatch
-> result evidence
-> review
-> ingestion
-> next frontier
```

The defining rule is that artifacts and verification state are the source of
truth, not model claims.

## Short Description

DWM is a deterministic workflow control-plane for agentic work. It turns large
goals into hashed packets, dispatches, evidence, reviews, and resumable runtime
state.

## Naming Rules

- Use **DWM** for the product and system.
- Use **Deterministic Workflow Machine** on first mention in formal docs.
- Use `dwm` for the GitHub repository slug when available.
- Keep `dynamic-workflow-designer` for the Codex skill name and `created_by`
  contract values.
- Do not rename existing fixture IDs or `workflow.plan.json` schema fields just
  for branding.
