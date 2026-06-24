# V111 Decision

Decision: document the V111 Agent Fabric operator-view/exporter contract before
integrating the implementation slice.

V111 should make the V110 report fields easier for an operator to read without
changing the trust model. The view/exporter is a presentation layer over Depone
verification reports: it can summarize `verdict`, `decision`, `assurance`, and
Agent Fabric capture entries, but it cannot create new evidence or upgrade an
assurance label.

Accepted direction:

- consume existing verification report JSON as the source of truth;
- preserve `A0-claims-only` and `A1-local-observed` exactly as V109/V110 define
  them;
- keep invalid capture manifests visible and fail-closed through the underlying
  report;
- expose evidence paths in any exported summary for traceability;
- keep the implementation stdlib-only and deterministic.

Integration risks to resolve after code integration:

- confirm the final exporter command name and output files;
- align tests with the actual implementation rather than this provisional docs
  contract;
- avoid duplicating report validation in the view layer;
- ensure missing V110 fields are displayed as compatibility risks, not as a
  stronger pass state;
- keep public docs on the Depone brand and avoid reintroducing old product
  naming.

This decision intentionally does not claim:

- live model or command execution;
- external attestation;
- new assurance levels beyond V109/V110;
- improved productivity, speed, cost, quality, or direct-agent superiority;
- release readiness before the implementation, tests, and contract gates are
  integrated.
