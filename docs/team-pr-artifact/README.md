# Team PR Artifact Fixture

This directory contains a deterministic PR/check artifact for Team Ledger lanes.
It is produced from saved GitHub-style JSON, so review and validation do not
require `gh`, network access, credentials, or PR mutation.

Regenerate the fixture from a saved `gh pr view --json` payload:

```bash
python3 -m depone team-pr-artifact \
  --input saved-gh-pr-view.json \
  --captured-at 2026-06-30T15:30:00Z \
  --expected-head-sha bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --out docs/team-pr-artifact/pr-artifact.json \
  --json
```

Validate the committed artifact without network:

```bash
python3 -m depone team-pr-artifact \
  --artifact docs/team-pr-artifact/pr-artifact.json \
  --expected-head-sha bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --json
```

Boundary: this command records observed PR/check facts only. It does not approve
or merge a pull request, call live models, attest provider runtime isolation, or
raise assurance. Failed checks, pending checks, stale artifacts, bad
mergeability, malformed state, and SHA/URL mismatches block.
