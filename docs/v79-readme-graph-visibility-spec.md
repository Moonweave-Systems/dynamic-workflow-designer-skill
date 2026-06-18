# V79 README Graph Visibility Spec

Status: implemented README graph visibility audit in
`scripts/dwm_readme_graph_visibility.py`.

V79 consumes the V78 graph timing decision and audits README graph text. It does
not generate a graph, edit README assets, publish a benchmark trend, execute a
queued command, or create a worktree.

## Scope

The audit reads:

- `README.md`;
- `out/graph-timing/v78-canonical/graph-timing.json`.

It writes `readme-graph-visibility.json`, `readme-graph-visibility.md`, and
`status.json` under `out/readme-graph-visibility/`.

## Policy

The current safe state is `readme_visibility_ready` only when V78 reports
`progress-only-visible`, the process graph is explicitly labeled as not a public benchmark graph,
and the public benchmark trend remains blocked.

The benchmark evidence image may remain visible only with source-bound language
and the statement that trend promotion is blocked until real release history
supports the claim. Public upward benchmark claims remain blocked.

This audit does not generate a graph.

## Evaluation Fixtures

`fixtures/v79/manifest.json` covers:

- current safe process and benchmark evidence visibility;
- missing process label blocking;
- missing benchmark label blocking;
- public trend readiness blocking this gate;
- forbidden superiority claim blocking.

## Release Commands

```bash
python scripts/dwm_readme_graph_visibility.py --self-test
python scripts/dwm_readme_graph_visibility.py --manifest fixtures/v79/manifest.json --out out/readme-graph-visibility/v79-final
python scripts/dwm_readme_graph_visibility.py audit --readme README.md --timing out/graph-timing/v78-canonical/graph-timing.json --out out/readme-graph-visibility/v79-canonical
```

The canonical audit should return `readme_visibility_ready` while V78 remains
`progress-only-visible`.
