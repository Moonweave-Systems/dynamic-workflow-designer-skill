# V53 Demo Inspect Spec

Status: implemented first demo inspect surface in `scripts/dwm_demo.py`.

## Research and Prior Art

V51 created the canonical demo and V52 moved that demo into the README entry
path. The next usability gap was inspection: a user could run the demo, but had
to manually open several generated files to understand whether the result was
still coherent.

V53 adds an explicit inspect command for existing demo output.

## Product Position and Non-Goals

`scripts/dwm_demo.py inspect` reads an existing demo directory and writes a
human-readable summary. It does not rerun demo commands.

Non-goals:

- do not execute live adapters,
- do not mutate source files,
- do not refresh stale demo artifacts silently,
- do not claim benchmark superiority,
- do not make generated demo output a source of truth.

## Workflow Architecture

The command is:

```bash
python scripts/dwm_demo.py inspect --demo out/demo/quickstart
```

It reads:

- `demo.json`,
- `status.json`,
- `.dwm_demo-owned.json`,
- declared artifacts from each recorded demo command.

It writes:

- `demo-inspect.json`,
- `demo-summary.md`.

## Safety and Verification Gates

The inspect gate blocks:

- `ERR_DEMO_ARTIFACT_MISSING` when the demo sentinel, `demo.json`,
  `status.json`, results, or declared artifacts are missing,
- `ERR_DEMO_STALE_HASH` when `demo.json` and `status.json` drift apart or the
  command hash no longer matches the current demo command plan.

## Evaluation Fixtures

`fixtures/v53/manifest.json` covers:

- positive: canonical demo inspect creates `demo-inspect.json` and
  `demo-summary.md`,
- negative: missing demo artifacts are blocked,
- negative: stale command hash is blocked.

## Release Plan

V53 should land before measured dogfood comparison work. The demo now has a
closed loop: run it, inspect it, and only then decide whether later live
adapter or benchmark work is justified.
