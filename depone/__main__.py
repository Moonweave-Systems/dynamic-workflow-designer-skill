"""Depone CLI entrypoint for core commands and Agent Fabric smoke."""

from __future__ import annotations

import argparse
import sys

from depone.cli import (
    agent_fabric_adapter_smoke,
    agent_fabric_claim_gate,
    agent_fabric_controlled_capture,
    agent_fabric_dogfood_evidence,
    agent_fabric_evidence_chain,
    agent_fabric_evidence_ingest,
    agent_fabric_evidence_substrate,
    agent_fabric_harness_snapshot,
    agent_fabric_observe,
    agent_fabric_paired_evidence,
    agent_fabric_paired_run,
    agent_fabric_seal,
    agent_fabric_sign,
    agent_fabric_smoke,
    agent_fabric_team_ledger,
    agent_fabric_verify_seal,
    agent_fabric_verify_signature,
    advance,
    demo,
    design,
    doctor,
    evidence_next,
    evidence_run,
    validate,
    validate_contracts,
)
from depone import compile as compile_mod
from depone.cli._response import EXIT_INTERNAL, EXIT_USAGE, emit_error, emit_json
from depone.mcp import server as mcp_server
from depone import verify as verify_mod


class DeponeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        if "--json" in sys.argv[1:]:
            emit_json(
                {
                    "error": {
                        "code": "ERR_CLI_USAGE",
                        "message": message,
                        "path": None,
                    }
                }
            )
            self.exit(EXIT_USAGE)
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _add_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one machine-readable JSON object on stdout",
    )


def _add_observe_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--runner-sandbox",
        required=False,
        default="",
        help="Runner worktree/sandbox to observe read-only",
    )
    parser.add_argument(
        "--source-fixture-hash",
        required=False,
        default="",
        help="Expected source fixture hash for the observer capture",
    )
    parser.add_argument(
        "--out",
        default="observer-capture.json",
        help="Observer-owned output path for observer-capture.json",
    )
    parser.add_argument(
        "--log",
        default="verify-log.json",
        help="Observer-owned verification command log path",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Verification command timeout",
    )
    parser.add_argument(
        "--seal-key-file",
        default="",
        help="Optional observer-held HMAC key file outside the runner sandbox",
    )
    parser.add_argument(
        "--seal-key-id",
        default="",
        help="Optional non-secret observer HMAC key label",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)
    parser.add_argument(
        "verification_command",
        nargs=argparse.REMAINDER,
        help="Observer-chosen verification command to run after --",
    )


def _add_team_ledger_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ledger",
        default="",
        help="Input Depone Team Ledger v0 JSON",
    )
    parser.add_argument(
        "--out",
        default="team-ledger-verdict.json",
        help="Output path for Team Ledger verdict JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_evidence_substrate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--capture-manifest",
        default="",
        help="Input Agent Fabric capture manifest JSON",
    )
    parser.add_argument(
        "--runner-receipt",
        default="",
        help="Optional V126 runner receipt JSON for OTel runner attributes",
    )
    parser.add_argument(
        "--out",
        default="evidence-substrate-bundle.json",
        help="Output evidence substrate bundle JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_evidence_ingest_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--statement",
        help="Input in-toto Statement JSON or bundle JSON containing statement",
    )
    group.add_argument(
        "--dsse",
        help="Input DSSE envelope JSON or bundle JSON containing dsse_envelope",
    )
    group.add_argument(
        "--signed-bundle",
        help="Input signed evidence bundle JSON; requires --public-key",
    )
    parser.add_argument(
        "--public-key",
        default="",
        help="Ed25519 public key PEM used to verify --signed-bundle",
    )
    parser.add_argument(
        "--otel-spans",
        default=None,
        help="Optional OTel span JSON or bundle JSON containing otel_spans",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help=(
            "Subject artifact locator as name=path[:raw|:json]; repeat for "
            "each artifact. Default digest mode is raw bytes."
        ),
    )
    parser.add_argument(
        "--out",
        default="evidence-ingest-verdict.json",
        help="Output evidence ingest verdict JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_evidence_chain_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--capture",
        action="append",
        default=[],
        help="Capture manifest JSON path; repeat in append-only chain order",
    )
    parser.add_argument(
        "--out",
        default="evidence-chain-verdict.json",
        help="Output evidence chain verdict JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_team_ledger_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ledger",
        default="",
        help="Input team-ledger.json to validate",
    )
    parser.add_argument(
        "--base-dir",
        default="",
        help="Base directory for relative lane evidence_dir values; defaults to ledger parent",
    )
    parser.add_argument(
        "--out",
        default="team-ledger-verdict.json",
        help="Output path for the team ledger verdict JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_evidence_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--runner-sandbox",
        required=False,
        default="",
        help="Runner worktree/sandbox to observe read-only",
    )
    parser.add_argument(
        "--source-fixture",
        required=False,
        default="",
        help="Reference adapter/source fixture JSON to hash-bind",
    )
    parser.add_argument(
        "--runner-uid",
        type=int,
        default=None,
        help=(
            "OS uid the runner/agent ran under, when the observer launched it "
            "isolated (different user/container). Enables A2 only if the "
            "observer output dir is not writable by that uid; omit for A1."
        ),
    )
    parser.add_argument(
        "--runner-user",
        default="",
        help=(
            "OS user for an observer-launched uid runner. Provide with "
            "--runner-command to bind the runner uid to an observer launch receipt."
        ),
    )
    parser.add_argument(
        "--runner-command",
        default="",
        help=(
            "Shell command to run as --runner-user inside --runner-sandbox before "
            "observer capture."
        ),
    )
    parser.add_argument(
        "--runner-container-id",
        default="",
        help=(
            "Docker container id to inspect as externally launched runner context. "
            "This records container facts but does not by itself raise assurance "
            "to A2. Mutually exclusive with --runner-uid and observer-launched "
            "container options."
        ),
    )
    parser.add_argument(
        "--runner-container-image",
        default="",
        help=(
            "Docker image for an observer-launched runner container. Provide with "
            "--runner-container-command to bind the inspected container id to the "
            "runner launch."
        ),
    )
    parser.add_argument(
        "--runner-container-command",
        default="",
        help=(
            "Shell command to run inside the observer-launched runner container "
            "with --runner-sandbox mounted at /work."
        ),
    )
    parser.add_argument(
        "--runner-container-hold-seconds",
        type=int,
        default=600,
        help=(
            "Seconds to keep the observer-launched runner container alive after "
            "its command succeeds so the observer can inspect it."
        ),
    )
    parser.add_argument(
        "--sign-private-key",
        default="",
        help=(
            "Ed25519 private key PEM for optional operator-key DSSE signing of "
            "the evidence bundle."
        ),
    )
    parser.add_argument(
        "--sign-key-id",
        default="",
        help="Non-secret key label to embed in the optional evidence-run signature.",
    )
    parser.add_argument(
        "--sign-public-key",
        default="",
        help=(
            "Optional Ed25519 public key PEM used to verify the signed bundle "
            "immediately after evidence-run signs it."
        ),
    )
    parser.add_argument(
        "--out",
        default="evidence-run",
        help="Output directory for all evidence-run artifacts",
    )
    parser.add_argument(
        "--allow-touched-file",
        action="append",
        default=[],
        help="Allowed touched file for capture manifest validation; repeatable",
    )
    parser.add_argument(
        "--verify-plan",
        default="",
        help="Optional plan JSON for the final Depone verify step",
    )
    parser.add_argument(
        "--verify-evidence",
        default="",
        help="Optional evidence directory for the final Depone verify step",
    )
    parser.add_argument(
        "--verify-adapter",
        default="generic",
        help="Evidence adapter for the final Depone verify step",
    )
    parser.add_argument(
        "--operator-view-out",
        default="",
        help="Optional operator view path for the final Depone verify step",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Observer verification command timeout",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)
    parser.add_argument(
        "verification_command",
        nargs=argparse.REMAINDER,
        help="Observer-chosen verification command to run after --",
    )


def _add_team_ledger_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ledger",
        default="",
        help="Team Ledger v0 JSON path to validate",
    )
    parser.add_argument(
        "--base-dir",
        default="",
        help="Base directory for relative lane evidence_dir values; defaults to ledger parent",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path for the Team Ledger verdict JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_evidence_next_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--evidence-dir",
        default="",
        help="Evidence-run artifact directory to re-validate before selecting next action",
    )
    parser.add_argument(
        "--source-fixture",
        default="",
        help=(
            "Optional source fixture JSON path override for the source_fixture subject"
        ),
    )
    parser.add_argument(
        "--previous-capture",
        default="",
        help=(
            "Optional predecessor capture-manifest.json for validating a prev_capture_hash subject"
        ),
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path for the evidence-next decision JSON",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(parser)


def _add_advance_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--evidence-dir",
        default="",
        help="Previous evidence-run artifact directory to re-validate before one continuation",
    )
    parser.add_argument(
        "--advance-out",
        default="",
        help="Output path for the advance decision artifact; defaults to <out>/advance-decision.json",
    )
    parser.add_argument(
        "--previous-source-fixture",
        default="",
        help="Optional source fixture override used only for the previous evidence-next gate",
    )
    _add_evidence_run_args(parser)


def main() -> None:
    parser = DeponeArgumentParser(
        prog="depone",
        description="Workflow designer + cross-platform evidence verifier.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"depone v{__import__('depone').__version__}",
    )

    sub = parser.add_subparsers(
        dest="command", required=True, parser_class=DeponeArgumentParser
    )

    # design
    design_parser = sub.add_parser(
        "design", help="Decompose an objective into a workflow plan"
    )
    design_parser.add_argument(
        "objective", nargs="?", help="Natural-language objective"
    )
    design_parser.add_argument(
        "--out", default="plan.json", help="Output path for plan.json"
    )
    design_parser.add_argument(
        "--surface", help="Repo path, API spec, or doc URL in scope"
    )
    design_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(design_parser)

    # validate
    validate_parser = sub.add_parser(
        "validate", help="Validate a plan.json against the schema"
    )
    validate_parser.add_argument("plan", nargs="?", help="Path to plan.json")
    validate_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(validate_parser)

    # compile
    compile_parser = sub.add_parser(
        "compile", help="Compile a plan into a target framework workflow"
    )
    compile_parser.add_argument("plan", nargs="?", help="Path to plan.json")
    compile_parser.add_argument(
        "--target",
        default=None,
        choices=["conductor", "langgraph", "agent-fabric"],
        help="Target workflow framework",
    )
    compile_parser.add_argument("--out", default="workflow.yaml", help="Output path")
    compile_parser.add_argument(
        "--harness",
        default="shell",
        help="Agent Fabric target harness (used with --target agent-fabric)",
    )
    compile_parser.add_argument(
        "--roles",
        action="append",
        default=[],
        help=(
            "Role contract JSON path for --target agent-fabric; may be repeated "
            "or point at a role-set JSON"
        ),
    )
    compile_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(compile_parser)

    # verify
    verify_parser = sub.add_parser(
        "verify", help="Verify execution evidence against a plan"
    )
    verify_parser.add_argument("plan", nargs="?", help="Path to plan.json")
    verify_parser.add_argument(
        "--evidence", default=None, help="Path to execution evidence directory"
    )
    verify_parser.add_argument(
        "--adapter", default="generic", help="Evidence adapter (conductor, generic)"
    )
    verify_parser.add_argument(
        "--out", default="verification-report.json", help="Output path for report"
    )
    verify_parser.add_argument(
        "--operator-view-out",
        default=None,
        help="Output path for a V111 operator-readable report view",
    )
    verify_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(verify_parser)

    # validate-contracts
    vc_parser = sub.add_parser(
        "validate-contracts",
        help="Validate V107 Agent Fabric contracts (roles, toolbelts, harnesses)",
    )
    vc_parser.add_argument("--file", help="Path to a single contract JSON file")
    vc_parser.add_argument(
        "--all", action="store_true", help="Validate all contracts under contracts/"
    )
    vc_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # mcp
    mcp_parser = sub.add_parser(
        "mcp",
        help="Run the stdlib-only MCP stdio server for Depone evidence tools",
    )
    mcp_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # doctor
    doctor_parser = sub.add_parser(
        "doctor",
        help="Check package-local readiness for agent-session use",
    )
    doctor_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(doctor_parser)

    # agent-fabric-smoke
    smoke_parser = sub.add_parser(
        "agent-fabric-smoke",
        help="Export the source-only Agent Fabric compile-to-report smoke summary",
    )
    smoke_parser.add_argument("--profile", help="Agent Fabric profile JSON path")
    smoke_parser.add_argument(
        "--roles",
        action="append",
        default=[],
        help="Role contract JSON path; may be repeated or point at a role-set JSON",
    )
    smoke_parser.add_argument(
        "--plan", help="Depone plan JSON path for report verification"
    )
    smoke_parser.add_argument("--harness", default="shell", help="Target harness name")
    smoke_parser.add_argument(
        "--out",
        default="agent-fabric-smoke.json",
        help="Output path for smoke summary JSON",
    )
    smoke_parser.add_argument(
        "--operator-view-out",
        default=None,
        help="Optional output path for the embedded operator Markdown view",
    )
    smoke_parser.add_argument(
        "--observer-capture",
        default=None,
        help="Optional Depone observer capture JSON for A1-local-observed smoke",
    )
    smoke_parser.add_argument(
        "--allow-touched-file",
        action="append",
        default=[],
        help="Allowed touched file for observer capture validation; may be repeated",
    )
    smoke_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-harness-snapshot
    harness_snapshot_parser = sub.add_parser(
        "agent-fabric-harness-snapshot",
        help="Export source-only Agent Fabric harness capability snapshots",
    )
    harness_snapshot_parser.add_argument(
        "--harness",
        action="append",
        default=[],
        help=(
            "Harness name to include; may be repeated, "
            "defaults to all known harnesses"
        ),
    )
    harness_snapshot_parser.add_argument(
        "--out",
        default="agent-fabric-harness-snapshot.json",
        help="Output path for harness snapshot JSON",
    )
    harness_snapshot_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-adapter-smoke
    adapter_smoke_parser = sub.add_parser(
        "agent-fabric-adapter-smoke",
        help="Export source-only Agent Fabric adapter smoke reports",
    )
    adapter_smoke_parser.add_argument(
        "--adapter-fixture", help="Reference adapter fixture JSON path"
    )
    adapter_smoke_parser.add_argument(
        "--harness-snapshot",
        default=None,
        help="Optional harness snapshot JSON path; defaults to adapter harness",
    )
    adapter_smoke_parser.add_argument(
        "--out",
        default="agent-fabric-adapter-smoke.json",
        help="Output path for adapter smoke report JSON",
    )
    adapter_smoke_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )




    # agent-fabric-controlled-capture
    controlled_capture_parser = sub.add_parser(
        "agent-fabric-controlled-capture",
        help="Export source-only Agent Fabric controlled capture corpus reports",
    )
    controlled_capture_parser.add_argument(
        "--capture-manifest",
        action="append",
        default=[],
        help="Agent Fabric capture manifest JSON path; repeat for corpus coverage",
    )
    controlled_capture_parser.add_argument(
        "--out",
        default="controlled-capture-corpus.json",
        help="Output path for controlled capture corpus JSON",
    )
    controlled_capture_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-dogfood-evidence
    dogfood_evidence_parser = sub.add_parser(
        "agent-fabric-dogfood-evidence",
        help="Export source-only Agent Fabric dogfood evidence",
    )
    dogfood_evidence_parser.add_argument(
        "--capture-manifest",
        action="append",
        help=(
            "Agent Fabric capture manifest JSON path; repeat to export a "
            "controlled capture corpus summary"
        ),
    )
    dogfood_evidence_parser.add_argument(
        "--out",
        default="dogfood-evidence.json",
        help="Output path for dogfood evidence report JSON",
    )
    dogfood_evidence_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-paired-evidence
    paired_evidence_parser = sub.add_parser(
        "agent-fabric-paired-evidence",
        help="Export source-only paired Agent Fabric dogfood evidence",
    )
    paired_evidence_parser.add_argument(
        "--adapter-smoke", help="Adapter smoke report JSON path"
    )
    paired_evidence_parser.add_argument(
        "--dogfood-evidence", help="Dogfood evidence JSON path"
    )
    paired_evidence_parser.add_argument(
        "--claim-scope",
        default="public-benefit",
        help="Claim scope being paired",
    )
    paired_evidence_parser.add_argument(
        "--out",
        default="agent-fabric-paired-evidence.json",
        help="Output path for paired evidence report JSON",
    )
    paired_evidence_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-paired-run
    paired_run_parser = sub.add_parser(
        "agent-fabric-paired-run",
        help="Export V126 observer captures and runner receipts for paired runs",
    )
    paired_run_parser.add_argument("--repo", default=".", help="Observed repo path")
    paired_run_parser.add_argument(
        "--source-fixture-hash",
        help="Expected source fixture hash for the observer capture",
    )
    paired_run_parser.add_argument(
        "--out",
        default="observer-capture.json",
        help="Output path for observer capture JSON",
    )
    paired_run_parser.add_argument(
        "--log",
        default=None,
        help="Output path for verification command log JSON",
    )
    paired_run_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Verification command timeout",
    )
    paired_run_parser.add_argument(
        "--runner-receipt-out",
        default=None,
        help="Optional output path for runner receipt JSON",
    )
    paired_run_parser.add_argument(
        "--runner-kind",
        default="manual",
        choices=["codex-cli", "manual"],
        help="Runner that performed the agent arm",
    )
    paired_run_parser.add_argument(
        "--arm",
        default="direct",
        choices=["direct", "governed"],
        help="Paired-run arm being observed",
    )
    paired_run_parser.add_argument("--task-id", default="manual-task")
    paired_run_parser.add_argument(
        "--runner-invocation",
        action="append",
        default=[],
        help="Runner invocation token; repeat for each argv item",
    )
    paired_run_parser.add_argument("--transcript-path", default="")
    paired_run_parser.add_argument(
        "--runner-log",
        default="",
        help="Optional Codex runner stdout/stderr log JSON path",
    )
    paired_run_parser.add_argument(
        "--codex-prompt",
        default=None,
        help="Run codex exec with this prompt before observer verification",
    )
    paired_run_parser.add_argument(
        "--codex-prompt-file",
        default=None,
        help="Read codex exec prompt from this UTF-8 file",
    )
    paired_run_parser.add_argument(
        "--codex-sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Sandbox mode passed to codex exec",
    )
    paired_run_parser.add_argument(
        "--report-out",
        default=None,
        help="Write a paired-run report from existing direct/governed artifacts",
    )
    paired_run_parser.add_argument("--direct-runner", default="")
    paired_run_parser.add_argument("--direct-observer", default="")
    paired_run_parser.add_argument("--governed-runner", default="")
    paired_run_parser.add_argument("--governed-observer", default="")
    paired_run_parser.add_argument("--runner-exit-code", type=int, default=0)
    paired_run_parser.add_argument("--started-at", default="")
    paired_run_parser.add_argument("--ended-at", default="")
    paired_run_parser.add_argument("--human-intervened", action="store_true")
    paired_run_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    paired_run_parser.add_argument(
        "verification_command",
        nargs=argparse.REMAINDER,
        help="Verification command to run after --",
    )

    # agent-fabric-observe
    observe_parser = sub.add_parser(
        "agent-fabric-observe",
        help="Run a separated observer-owned capture over a runner sandbox",
    )
    _add_observe_args(observe_parser)

    # observe (agent-facing alias)
    observe_alias_parser = sub.add_parser(
        "observe",
        help="Run a separated observer-owned capture over a runner sandbox",
    )
    _add_observe_args(observe_alias_parser)

    # agent-fabric-seal
    seal_parser = sub.add_parser(
        "agent-fabric-seal",
        help="Write an observer-held HMAC seal for a capture",
    )
    seal_parser.add_argument("--capture", default="", help="Observer capture JSON")
    seal_parser.add_argument("--seal-key-file", default="", help="Raw HMAC key file")
    seal_parser.add_argument(
        "--seal-key-id",
        default="",
        help="Non-secret key label to embed in the seal",
    )
    seal_parser.add_argument("--out", default="", help="Output seal JSON path")
    seal_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-verify-seal
    verify_seal_parser = sub.add_parser(
        "agent-fabric-verify-seal",
        help="Verify an observer-held HMAC seal for a capture",
    )
    verify_seal_parser.add_argument("--capture", default="", help="Observer capture JSON")
    verify_seal_parser.add_argument("--seal", default="", help="Observer seal JSON")
    verify_seal_parser.add_argument(
        "--seal-key-file",
        default="",
        help="Raw HMAC key file",
    )
    verify_seal_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-sign
    sign_parser = sub.add_parser(
        "agent-fabric-sign",
        help="Sign a DSSE evidence bundle with an operator Ed25519 key via openssl",
    )
    sign_parser.add_argument("--bundle", default="", help="Evidence bundle JSON")
    sign_parser.add_argument("--private-key", default="", help="Ed25519 private key PEM")
    sign_parser.add_argument(
        "--key-id",
        default="",
        help="Non-secret key label to embed in the DSSE signature",
    )
    sign_parser.add_argument("--out", default="", help="Output signed bundle JSON")
    sign_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-verify-signature
    verify_signature_parser = sub.add_parser(
        "agent-fabric-verify-signature",
        help="Verify a DSSE evidence bundle signature with an Ed25519 public key",
    )
    verify_signature_parser.add_argument(
        "--bundle",
        default="",
        help="Signed evidence bundle JSON",
    )
    verify_signature_parser.add_argument(
        "--public-key",
        default="",
        help="Ed25519 public key PEM",
    )
    verify_signature_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # agent-fabric-evidence-substrate
    evidence_substrate_parser = sub.add_parser(
        "agent-fabric-evidence-substrate",
        help="Export V128 in-toto/DSSE and OTel GenAI evidence bundle",
    )
    _add_evidence_substrate_args(evidence_substrate_parser)

    # evidence-substrate (agent-facing alias)
    evidence_substrate_alias_parser = sub.add_parser(
        "evidence-substrate",
        help="Export V128 in-toto/DSSE and OTel GenAI evidence bundle",
    )
    _add_evidence_substrate_args(evidence_substrate_alias_parser)

    # agent-fabric-evidence-ingest
    evidence_ingest_parser = sub.add_parser(
        "agent-fabric-evidence-ingest",
        help="Ingest external in-toto/DSSE and OTel evidence as untrusted input",
    )
    _add_evidence_ingest_args(evidence_ingest_parser)

    # evidence-ingest (agent-facing alias)
    evidence_ingest_alias_parser = sub.add_parser(
        "evidence-ingest",
        help="Ingest external in-toto/DSSE and OTel evidence as untrusted input",
    )
    _add_evidence_ingest_args(evidence_ingest_alias_parser)

    # agent-fabric-evidence-chain
    evidence_chain_parser = sub.add_parser(
        "agent-fabric-evidence-chain",
        help="Verify an ordered append-only capture manifest chain",
    )
    _add_evidence_chain_args(evidence_chain_parser)

    # evidence-chain (agent-facing alias)
    evidence_chain_alias_parser = sub.add_parser(
        "evidence-chain",
        help="Verify an ordered append-only capture manifest chain",
    )
    _add_evidence_chain_args(evidence_chain_alias_parser)


    # team-ledger
    team_ledger_parser = sub.add_parser(
        "team-ledger",
        help="Validate a Team Ledger v0 fan-in artifact",
    )
    _add_team_ledger_args(team_ledger_parser)

    # agent-fabric-team-ledger
    agent_fabric_team_ledger_parser = sub.add_parser(
        "agent-fabric-team-ledger",
        help="Validate a Team Ledger v0 fan-in artifact",
    )
    _add_team_ledger_args(agent_fabric_team_ledger_parser)

    # evidence-run
    evidence_run_parser = sub.add_parser(
        "evidence-run",
        help="Run observe -> evidence-substrate -> evidence-ingest -> verify",
    )
    _add_evidence_run_args(evidence_run_parser)

    # run (native runner alias)
    run_parser = sub.add_parser(
        "run",
        help="Compatibility alias for evidence-run",
    )
    _add_evidence_run_args(run_parser)

    # evidence-next
    evidence_next_parser = sub.add_parser(
        "evidence-next",
        help="Re-validate an evidence-run directory and select the next safe action",
    )
    _add_evidence_next_args(evidence_next_parser)

    # next (native operator alias)
    next_parser = sub.add_parser(
        "next",
        help="Compatibility alias for evidence-next",
    )
    _add_evidence_next_args(next_parser)

    # advance
    advance_parser = sub.add_parser(
        "advance",
        help="Gate and run exactly one evidence-run continuation after evidence-next",
    )
    _add_advance_args(advance_parser)


    # team-ledger
    team_ledger_parser = sub.add_parser(
        "team-ledger",
        help="Validate a Team Ledger v0 leader/lane fan-in record",
    )
    _add_team_ledger_args(team_ledger_parser)

    team_ledger_alias_parser = sub.add_parser(
        "agent-fabric-team-ledger",
        help="Validate a Team Ledger v0 leader/lane fan-in record",
    )
    _add_team_ledger_args(team_ledger_alias_parser)

    # agent-fabric-claim-gate
    claim_gate_parser = sub.add_parser(
        "agent-fabric-claim-gate",
        help="Gate Agent Fabric public claims on source evidence",
    )
    claim_gate_parser.add_argument(
        "--adapter-smoke", help="Adapter smoke report JSON path"
    )
    claim_gate_parser.add_argument(
        "--paired-evidence",
        default=None,
        help="Optional paired evidence report JSON path",
    )
    claim_gate_parser.add_argument(
        "--claim-scope",
        default="public-benefit",
        help="Claim scope being gated",
    )
    claim_gate_parser.add_argument(
        "--out",
        default="agent-fabric-claim-gate.json",
        help="Output path for claim gate report JSON",
    )
    claim_gate_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )

    # demo
    demo_parser = sub.add_parser(
        "demo", help="Run a complete design -> compile -> verify cycle"
    )
    demo_parser.add_argument(
        "--out", default=None, help="Output directory for demo artifacts"
    )
    demo_parser.add_argument(
        "--self-test", action="store_true", help="Run self-test and exit"
    )
    _add_json_arg(demo_parser)

    args = parser.parse_args()

    try:
        if args.command == "design":
            design.run(args)
        elif args.command == "validate":
            validate.run(args)
        elif args.command == "compile":
            compile_mod.run(args)
        elif args.command == "verify":
            verify_mod.run(args)
        elif args.command == "validate-contracts":
            validate_contracts.run(args)
        elif args.command == "mcp":
            mcp_server.run(args)
        elif args.command == "doctor":
            doctor.run(args)
        elif args.command == "agent-fabric-smoke":
            agent_fabric_smoke.run(args)
        elif args.command == "agent-fabric-harness-snapshot":
            agent_fabric_harness_snapshot.run(args)
        elif args.command == "agent-fabric-adapter-smoke":
            agent_fabric_adapter_smoke.run(args)
        elif args.command == "agent-fabric-controlled-capture":
            agent_fabric_controlled_capture.run(args)
        elif args.command == "agent-fabric-dogfood-evidence":
            agent_fabric_dogfood_evidence.run(args)
        elif args.command == "agent-fabric-paired-evidence":
            agent_fabric_paired_evidence.run(args)
        elif args.command == "agent-fabric-paired-run":
            agent_fabric_paired_run.run(args)
        elif args.command in ("agent-fabric-observe", "observe"):
            agent_fabric_observe.run(args)
        elif args.command == "agent-fabric-seal":
            agent_fabric_seal.run(args)
        elif args.command == "agent-fabric-verify-seal":
            agent_fabric_verify_seal.run(args)
        elif args.command == "agent-fabric-sign":
            agent_fabric_sign.run(args)
        elif args.command == "agent-fabric-verify-signature":
            agent_fabric_verify_signature.run(args)
        elif args.command in ("agent-fabric-evidence-substrate", "evidence-substrate"):
            agent_fabric_evidence_substrate.run(args)
        elif args.command in ("agent-fabric-evidence-ingest", "evidence-ingest"):
            agent_fabric_evidence_ingest.run(args)
        elif args.command in ("agent-fabric-evidence-chain", "evidence-chain"):
            agent_fabric_evidence_chain.run(args)
        elif args.command in ("team-ledger", "agent-fabric-team-ledger"):
            agent_fabric_team_ledger.run(args)
        elif args.command in ("evidence-run", "run"):
            evidence_run.run(args)
        elif args.command in ("evidence-next", "next"):
            evidence_next.run(args)
        elif args.command == "advance":
            advance.run(args)
        elif args.command in ("team-ledger", "agent-fabric-team-ledger"):
            agent_fabric_team_ledger.run(args)
        elif args.command == "agent-fabric-claim-gate":
            agent_fabric_claim_gate.run(args)
        elif args.command == "demo":
            demo.run(args)
        else:
            parser.print_help()
            sys.exit(EXIT_USAGE)
    except SystemExit:
        raise
    except Exception as exc:
        emit_error(
            args,
            code="ERR_INTERNAL",
            message=str(exc),
            exit_code=EXIT_INTERNAL,
        )


if __name__ == "__main__":
    main()
