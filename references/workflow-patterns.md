# Workflow Patterns

Use these patterns when designing a large multi-agent workflow. Combine them
only when the handoff between patterns is explicit.

## Sequential

Use when each phase depends on the previous phase.

Example: inspect repo -> write plan -> implement -> verify -> review.

Minimum contract:

- Each phase has one output artifact.
- The next phase names the artifact it consumes.
- A failed phase stops the chain or returns to the prior phase with a reason.

## Pipeline

Use when many items move through the same stages and each item can advance
without waiting for every other item.

Example: files go through scan -> finding extraction -> independent refutation.

Rules:

- Prefer this over `parallel` when item-level verification can start early.
- Keep per-item artifacts small.
- Fan in only for deduplication, ranking, or synthesis.

## Parallel Fan-Out / Fan-In

Use when independent workers can investigate separate surfaces or perspectives.

Example: one worker per package, subsystem, data source, or research angle.

Rules:

- Set a concurrency cap.
- Define a shared output schema.
- Add a fan-in worker only after all required branches finish.

## Adversarial Verify

Use when outputs can be plausible but wrong.

Example: code audit findings, research claims, migration edits, PR summaries.

Rules:

- The verifier must be independent of the producer.
- The verifier tries to refute the finding, not rubber-stamp it.
- Verify against GROUND TRUTH, not the producer's (or the brief's) claims: read
  the actual source, data, or artifact and cite it (file:line, value). Any
  "verified" or "confirmed" label arriving as input is itself a claim to refute,
  not a fact.
- Default to refuted/flagged when the ground truth does not support the claim.
- The final report separates confirmed, refuted, and unverified items.

This against-source variant is the highest-value form: in practice it is what
catches a confident brief whose "verified" assumptions are wrong (e.g. skeptics
reading real source line-by-line falsified four "verified" claims and a blind
spot a single pass had accepted). Prefer it whenever a real source, dataset, or
artifact exists to check the claim against.

## Judge Panel

Use when several good answers may exist and the task needs comparison.

Example: architecture alternatives, product plans, prompt designs.

Rules:

- Generate alternatives independently.
- Score with a rubric before synthesis.
- Borrow useful parts from losing candidates only when the judge explains why.

## Loop Until Dry

Use for open-ended discovery when the number of findings is unknown.

Example: bug hunts, citation gaps, dead-code sweeps.

Rules:

- Stop after a fixed max round count.
- Stop early after N consecutive rounds with no new high-value findings.
- Do not reset the loop counter by changing search wording.

## Human Gate

Use when the workflow reaches a risky decision.

Examples: destructive changes, public API changes, dependency installs,
database migrations, production deploys, paid API use, secret access.

Rules:

- State the default safe action.
- Preserve completed work while waiting.
- Resume from the gate without rerunning completed phases when possible.

## Resume And Cache

Use when a workflow is expensive enough that rerunning the prefix is wasteful.

Rules:

- Make deterministic inputs visible in the run record.
- Cache completed phase outputs by phase id and input hash.
- Rerun only invalidated phases after edits.

## Reusable Templates

When a design matches a pattern that already has a validated, parameterized
runtime script, run that script instead of hand-coding a fresh one. See
`templates/` and its README.

- `templates/research-orchestration.workflow.mjs` — research/design questions:
  Scope -> fan-out research -> barrier synthesis -> adversarial-verify-against-
  source -> compose doc. Parameterized through `args` (question, sources, optional
  angles); verify batches claims. Use for multi-angle research where claims must
  be checked against real source/data before they enter the document.
