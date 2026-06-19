# Keelplane Branding

Keelplane is the public product brand for this repository's agent workflow
control-plane.

DWM Core stands for **Deterministic Workflow Machine**. It is the internal
engine name for the deterministic plan, packet, gate, evidence, review, and
resume-state machinery behind Keelplane.

The Codex skill entrypoint remains `dynamic-workflow-designer` so existing
skill activation, fixtures, and `workflow.plan.json` contracts continue to
work. The preferred repository slug remains `dwm` until a deliberate migration
gate proves that changing remotes, packages, paths, or install surfaces will
not break users. The old `dynamic-workflow-designer-skill` slug may appear only
in historical references or compatibility redirects.

## Position

Keelplane is not an unchecked agent launcher. It is a deterministic
control-plane for large AI-assisted work:

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

Keelplane is a deterministic control-plane for large AI-native work. It turns
large goals into hashed plans, packets, dispatches, evidence, reviews, and
resumable runtime state without losing control of what has actually happened.

## Naming Rules

- Use **Keelplane** for the product and public-facing brand.
- Use **DWM Core** for the internal deterministic workflow engine.
- Use **Deterministic Workflow Machine** when expanding DWM Core in formal
  docs.
- Use `dwm` for the GitHub repository slug until a dedicated migration gate
  changes it.
- Keep `dynamic-workflow-designer` for the Codex skill name and `created_by`
  contract values.
- Do not rename existing fixture IDs or `workflow.plan.json` schema fields just
  for branding.
- Do not claim autonomous execution, agent superiority, or benchmark uplift
  from branding changes.
