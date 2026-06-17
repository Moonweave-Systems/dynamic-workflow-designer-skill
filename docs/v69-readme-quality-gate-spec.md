# V69 README Quality Gate Spec

Status: implemented README product-page quality gate in
`scripts/check_readme_quality.py`.

## Research and Prior Art

V68 made the README readable again by moving command detail and release history
into separate docs. Without an automated gate, future feature slices can slowly
turn the README back into a release-note stream.

## Product Position and Non-Goals

V69 protects the public page shape. It is a documentation quality gate, not a
benchmark gate and not a product capability claim.

Non-goals:

- do not score marketing copy quality,
- do not block legitimate product updates,
- do not require README to contain every command,
- do not treat process progress as benchmark evidence.

## Workflow Architecture

The command is:

```bash
python scripts/check_readme_quality.py README.md
```

The gate checks:

- maximum README length,
- required product-page sections,
- required process and benchmark graph boundaries,
- links to `docs/command-reference.md` and `docs/release-history.md`,
- excessive `V<number>` release-history mentions.

## Execution Model

The check is read-only. It does not inspect generated `out/` evidence and does
not rewrite README.

## Safety and Verification Gates

The gate blocks README regressions that remove:

- process graph non-benchmark wording,
- public trend promotion caveat,
- generated-output caveat,
- reference docs that hold detailed commands and version history.

## Evaluation Fixtures

`--self-test` covers:

- a compact valid README,
- a release-note-shaped README with too many version mentions,
- missing command/history reference docs.

## Release Plan

V69 adds the gate to the release command corpus so README cleanup remains
enforced before later public polish or benchmark graph work.
