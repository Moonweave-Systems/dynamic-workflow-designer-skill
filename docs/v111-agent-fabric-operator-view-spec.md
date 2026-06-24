# V111 Agent Fabric Operator View Spec

V111 adds the documentation contract for a small operator-facing view/exporter
on top of the V110 verification report fields.

## Boundary

The view consumes an existing Depone verification report. It does not execute
commands, create Agent Fabric captures, validate live model output, introduce a
new assurance level, or bypass evidence-contract failures.

The source of truth remains the verification report JSON and the evidence files
referenced by that report. The view may summarize fields, but it must not turn a
summary into stronger proof than the report already carries.

## Required report inputs

A V111-compatible view must read these V110 fields when present:

- `verdict`;
- `decision`;
- `assurance`;
- `agent_fabric_captures[]` entries with `evidence_path`, `assurance`,
  `decision`, `valid`, and `errors`.

Missing V110 fields must be rendered as an integration risk, not silently
upgraded to success. Invalid capture entries must remain visible to the
operator.

## View/export behavior

The operator view should make the following distinctions explicit:

- report verdict versus operator-facing decision;
- report-level assurance versus capture-level assurance;
- valid captures versus invalid captures;
- self-report-only `A0-claims-only` material versus locally observed
  `A1-local-observed` material;
- evidence-contract failures versus Agent Fabric capture failures.

A markdown or JSON export may be added as long as it is deterministic,
stdlib-only, and derived from report fields. The export must preserve source
paths so an operator can trace each displayed capture back to the underlying
evidence artifact.

## Integration risks

This docs slice was written before the V111 implementation slice was integrated
into this worker worktree. The known integration risks are:

- the final exporter name, command shape, and output path may differ from this
  contract and must be reconciled before release;
- the exporter must not duplicate V110 validation logic in a divergent way;
- reports without `agent_fabric_captures` must remain compatible and should show
  `A0-claims-only` rather than inventing a stronger assurance;
- invalid capture manifests must stay fail-closed in the report and visible in
  the view;
- Depone branding must remain public-facing, with DWM Core used only for the
  internal engine where needed.

## Verification

The implementation slice should provide focused tests for:

```bash
python3 tests/test_agent_fabric_report_assurance.py
python3 -m depone verify --self-test
python3 -m depone validate-contracts --self-test
```

If a dedicated exporter command is added, its self-test or targeted unit test
must be listed here before V111 is considered release-ready.
