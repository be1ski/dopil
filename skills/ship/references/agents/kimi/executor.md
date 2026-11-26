# Executor card: Kimi Code

In a Kimi Code session, read `references/executor.md` first. This card overrides its rows **Who the executor is**
(by **Identity**), **Subagents with edit permission** and **Models** (by **Subagent model** and **Model rule**) and
**Structured question** (by **Tools**). For **Route skills** it adds only the install commands and the runtime's skill
names; the list and the catalog rules stay in `references/executor.md`.

## Identity

Run `python3 -I "<skill-dir>/references/agents/kimi/identity.py"` as written, where `<skill-dir>` is the absolute
directory of the loaded `SKILL.md`. It prints `ALIAS:` and `PROVIDER TYPE:`, or one `BLOCKER:` line. A launch that
prints none of these lines, a missing script, a missing interpreter or a crash: blocked; name it and stop before any
dispatch; never run an improvised check instead.

The vendor is Moonshot AI only for `PROVIDER TYPE: kimi`. A `BLOCKER` line or any other type: blocked (a provider
type names a protocol, not a vendor). Never print the output of `kimi provider list --json` yourself.

## Tools

`Bash` with `run_in_background` (foreground at most 300 s; background with `disable_timeout`, completion
by notification, output by `TaskOutput`); `Agent` with `subagent_type: coder` for edits; `AskUserQuestion` (2–4
options, `multi_select`, "Other" added by the runtime). Under Never Ask (`--auto`) Kimi refuses `AskUserQuestion`
("Cannot call AskUserQuestion while auto permission mode is active"), so there every structured question,
escalations and the dialog alike, is plain text. The naming hint of those questions (`references/reviewer-choice.md`,
"Dialog form") names the keys `codex` and `gemini`. In Orca, before every turn end while a dispatch of this run is
unsettled (after `worker-start`, a follow-up, `send`, a `reply`, a batch that leaves other workers running, or a
non-terminal escalation), the executor starts
`ORCA orchestration check --terminal "$ORCA_TERMINAL_HANDLE" --peek --wait --timeout-ms 1800000 --json` with
`run_in_background` and `disable_timeout`. One wait at a time. When it completes, a clean timeout included, or Orca's
own wake arrives, the executor runs the consuming `ORCA orchestration check --terminal "$ORCA_TERMINAL_HANDLE" --json`
and handles that batch as `references/adapter-orca.md` says. A non-zero exit or an error: stop and tell the user, no new wait.
Measured: Orca did not wake an idle Kimi executor on `worker_done`; its own task's completion did, and `--peek --wait`
returns on a new message without consuming it.

## Models

**Subagent model.** Before the first in-session `coder` edit assignment of a route (not for Orca writers), dispatch
one `Agent` with `subagent_type: coder` and the prompt "Reply with exactly OK. Do not read, create or edit any file
and run no command." Then run the **Identity** script with the agent_id that Agent call returned as its one argument,
`python3 -I "<skill-dir>/references/agents/kimi/identity.py" <agent_id>`: it must print the session's `ALIAS`. Measured: the
`Agent` result carries `agent_id: agent-0`, the name of its wire directory. Another alias, a `BLOCKER` line, or no
`agent_id`: no in-session edit subagents for the route; the work they would do runs inline (`references/executor.md`),
a line in the report.

**Model rule.** The session's alias for every role; an escalation is a fresh subagent or worker on the same alias
where the route has one (see **Subagent model**), otherwise it stays inline; a ledger line.

## Route skills

The list and the catalog rules of `references/executor.md`, with this runtime's install and naming.
Superpowers: `/plugins install https://github.com/obra/superpowers` in the Kimi TUI, or an
existing superpowers in `~/.agents/skills`, which Kimi reads. ship: the README's Kimi lines. Update: the same install
commands. After installing or updating either, `/new`. The skill is typed `/skill:ship:ship`. The agent cannot run
`/plugins` itself: give the user the command.

## Instructions

Kimi loads `AGENTS.md` (and `.kimi-code/AGENTS.md`), not `CLAUDE.md` or `GEMINI.md`: the
generic **Repository instructions** row applies.

## Runs that cannot take an answer

None.

## Orca writing workers

For the task executor, gate fixer, parallel fixer, polisher and escalation. Never
`worker-start --agent kimi`: its first prompt is not delivered. One terminal per writer:
`ORCA terminal create --worktree <the route's tree selector, or current on a one-off route> --command "<launch>"`,
where `<launch>` is built per argument as `printf '%q ' KIMI_CODE_HOME="<the parent's Kimi home>"
"<the parent's resolved kimi path>" --auto -m "<alias>"`, with `KIMI_MODEL_THINKING_EFFORT="<the parent's value>"`
after the Kimi home only if the parent's shell has it set. No `--skills-dir`, unlike the Kimi reviewer's launch: the
writer keeps the user's skills (it needs the TDD skill). Invoking ship in Orca authorizes `--auto` (Never Ask)
for these writers, as Codex workers run in Orca's own mode. The launch command is the writer's pin; it is not
re-checked inside the same terminal. Then `ORCA terminal wait --terminal <handle> --for tui-idle`: a `blockedReason`
of `agent-trust-workspace` means the user accepts the folder in that tab, then the same wait again; any other
unsatisfied wait: show the user the screen, close the terminal, the start did not happen. Only after a satisfied
wait, `ORCA orchestration worker-start --spec-file … --terminal <handle>`; only a `ready` receipt counts. Any other:
**Recovery**, **Failed start**; a writer lost mid-task: **Recovery**, **A writer lost mid-task**. The handle and every
dispatch id go into the SDD ledger or the gate scratch.

## Follow-ups

Fix rounds, later gate-fixer rounds and polish follow-ups go as a new task into the same terminal,
never as `send`: after the writer's `worker_done`, `ORCA terminal wait --terminal <its handle> --for tui-idle`, then
`ORCA orchestration worker-start --spec-file … --terminal <the same handle> --json`; only a `ready` receipt for that
handle counts. Measured: this continues the same Kimi session; on a closed terminal it fails `agent_unconfigured`
with no new terminal. `agent_unconfigured` or any other failure: no new writer until the old one is proven gone
(**Closing**); then a fresh pinned terminal, a ledger line. A failed follow-up restarts its Task there as
**Recovery**, **A writer lost mid-task**, says; one refused before Orca created a Task gets a fresh start
there with the first assignment file plus the brief.

## Stop

In the sequence of `references/adapter-orca.md`, "Stopping at the user's request". A Kimi Code writer runs in a
terminal ship created, and `worker-stop` on its dispatch leaves that terminal open (measured: on a settled dispatch it
returns the settled state, `processAction: none`, `close: null`): its stop is **Closing**, `ORCA terminal close
--terminal <handle> --json` with `close.ptyKilled: true`, or the handle verified absent as that part says.

## Recovery

**Failed start.** In the sequence of `references/adapter-orca.md`, "If the worker did not start". Kimi Code has no
takeover by its own subagent. The proof is the failed start's terminal closed or gone as **Closing** says:
`ORCA terminal close --terminal <handle> --json` with `close.ptyKilled: true`, or the handle missing from an
untruncated `ORCA terminal list`. A `worker-release` receipt, `retained` included, is cleanup, not proof. Only after
that proof is a fresh configured Kimi worker started into its new pinned terminal per **Orca writing workers**, as the
same Task with the flags of **A writer lost mid-task** below. No proof, or the fresh worker cannot start either: the
task waits and the user is told.

**A writer lost mid-task** (its terminal gone or closed after its `ready` receipt and before its `worker_done`) has no
takeover by the executor's own subagent. Only after the old terminal is proven gone, as **Closing** says, is a fresh
writer started per **Orca writing workers**, its pins kept, with `--task <its Task>` in place of `--spec-file` and any
`--task-title`, plus `--retry-of <its dispatch id>` only when Orca reports that Task failed or blocked; a ledger line.

## Closing

A writer's terminal stays through interim `worker_done` messages and is closed when its role is accepted
or abandoned: task done, gate closed, polish accepted, escalation, failed start, user stop (the terminal close is the
stop). The close is `ORCA terminal close --terminal <handle> --json` returning `close.ptyKilled: true`, or else the
handle missing from `ORCA terminal list --json` with `truncated: false`. Only these prove a writer gone: liveness
`exited` or `lost` alone does not, and a terminal still listed is closed first.

## Pitfalls

"Trust this folder?" in a new worktree.
