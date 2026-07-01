# Depone Runtime Substrate Direction

Status: direction note for upcoming team/runtime slices.
Date: 2026-07-01.

## Position

Depone should remain an evidence/control plane first. The runtime substrate is a
means to produce verifiable receipts, not the product's source of truth.

tmux and OMX are useful for live operator supervision, persistent panes, and
temporary multi-worker coordination. They are not precise enough to be Depone's
canonical runtime record. Pane scrollback, prompt text, and chat summaries can
help humans inspect a run, but a Depone decision must be backed by machine
artifacts that can be revalidated without replaying a terminal session.

## External Direction

The surrounding coding-agent market is moving toward background/cloud execution,
custom environments, hooks, permissions, and PR-oriented output:

- Codex cloud runs tasks in the background and can work in parallel in its own
  cloud environment:
  <https://developers.openai.com/codex/cloud>.
- Codex cloud environments create a container, check out the selected repo
  branch or commit, run setup, and apply internet access settings:
  <https://developers.openai.com/codex/cloud/environments>.
- GitHub Copilot cloud agent starts from GitHub, IDE, REST API, CLI, MCP,
  planning, and automation surfaces, and can work in the background with PR
  output:
  <https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/start-copilot-sessions>.

Depone should interoperate with that direction by observing and validating
artifacts, not by pretending local terminal orchestration is equivalent to a
provider runtime attestation.

Runtime substrate references:

- tmux is explicitly a terminal multiplexer that manages pseudo-terminal panes,
  which makes it suitable for supervision but not sufficient as a structured
  evidence ledger by itself: <https://man7.org/linux/man-pages/man1/tmux.1.html>.
- Rust has mature process and PTY building blocks, including `portable-pty` and
  Tokio process support, but those are runner implementation options rather than
  evidence-model replacements: <https://docs.rs/portable-pty/latest/portable_pty/>
  and <https://docs.rs/tokio/latest/tokio/process/index.html>.

## Substrate Decision

Use this order unless a future PR proves a concrete need to change it:

1. **Structured receipts are canonical.** Depone records argv, cwd, environment
   policy, start/end timestamps, exit code, transcript path or hash, git
   base/head, touched files, evidence directory, and validation result.
2. **Python stdlib subprocess is the near-term runner.** It keeps the CLI
   installable and matches the repo invariant of no third-party Python
   dependencies.
3. **PTY is optional and narrow.** Use a pseudo-terminal only for adapters that
   truly need terminal behavior. Prefer non-interactive subprocess execution for
   deterministic checks.
4. **tmux/OMX is an operator adapter.** It can launch, supervise, or display
   work, but it does not define pass/fail. Pass/fail comes from Depone
   validators over receipts and artifacts.
5. **Rust is a later runner-daemon option.** Rust libraries such as
   `portable-pty` and async process runtimes such as Tokio can be appropriate
   for a robust cross-platform PTY/process supervisor, but only after Waves 2
   through 4 expose a real limitation in the Python stdlib runner.
6. **Cloud execution stays receipt-based first.** A cloud lane is an observed
   external fact unless the provider exposes a verifiable attestation Depone can
   validate locally.

## What Not To Build Yet

- Do not rewrite Depone in Rust.
- Do not add a terminal emulator as a dependency.
- Do not make tmux scrollback or pane state a validator input.
- Do not launch live model adapters inside the minimal local team loop.
- Do not raise A2/A3 assurance from runtime convenience alone.

## Next Implementation Implications

Wave 2, `team-merge-attempt`, should derive fan-in evidence from a real git
merge attempt in a disposable or otherwise proven-safe worktree. It does not
need tmux or Rust.

Wave 4, Codex-only launch receipt, should record the exact launch boundary:
capability receipt, argv, sandbox/approval policy, cwd, transcript, exit code,
and blocked/pass decision. It must not read token-bearing files and must not
claim that Codex capability detection equals execution.

Wave 3, minimal local `depone team`, should sequence existing primitives and
stop at receipts. It should not launch Codex, Claude Code, OpenCode, OMX
workers, cloud workers, or a live model API in its first PR.

Only after those slices are boring should a future PR evaluate whether a
Depone-owned runner daemon is needed. That PR must include failing tests or
operational evidence showing the Python stdlib runner is not enough.
