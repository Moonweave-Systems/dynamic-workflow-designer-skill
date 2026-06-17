# V66 Dogfood Progress Spec

Status: implemented dogfood evidence process progress graph in
`scripts/dwm_dogfood_progress.py`.

## Research and Prior Art

V65 creates a reviewed local chart render, but that render is still not a public
benchmark trend. The user-visible graph that should update every iteration is a
process graph: which evidence gates exist, which are still missing, and whether
the current chain is blocked.

## Product Position and Non-Goals

V66 tracks workflow progress, not performance superiority. It is safe to update
after every dogfood slice because it does not claim upward benchmark movement.

Non-goals:

- do not claim upward performance,
- do not publish README benchmark assets,
- do not mark `public_readme_ready` true,
- do not hide incomplete stages,
- do not read generated prose as source truth.

## Workflow Architecture

The command is:

```bash
python scripts/dwm_dogfood_progress.py build --out out/dogfood-progress/<progress_id>
```

It reads status-bound dogfood artifacts:

- acquisition,
- pair,
- clean pair root,
- graph-ready series,
- chart candidate,
- chart review,
- local render.

It writes:

- `dogfood-progress.json`,
- `dogfood-progress.svg`,
- `dogfood-progress.md`,
- `status.json`.

## Execution Model

The graph is horizontal process completion. Green nodes mean a matching
artifact/status pair exists. Grey nodes mean the stage is not yet complete.
The SVG explicitly states: process completion, not upward performance claim.

## Safety and Verification Gates

The gate blocks:

- `ERR_DOGFOOD_PROGRESS_STALE_ARTIFACT` when artifact JSON and status JSON
  differ,
- missing unsafe source roots,
- output path traversal,
- symlink paths.

## Evaluation Fixtures

`fixtures/v66/manifest.json` covers:

- partial progress with two completed stages,
- full progress with seven completed stages,
- stale artifact blocking.

## Release Plan

V66 gives README and operator work a safe graph surface to update frequently.
Future promotion can copy this progress graph to tracked assets after a separate
README asset gate, without pretending it is a benchmark trend.
