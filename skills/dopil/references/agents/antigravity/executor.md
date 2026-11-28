# Executor card: Antigravity CLI

In an Antigravity CLI session, read `references/executor.md` first. This card overrides its rows **Who the executor
is** (by **Identity**), **Subagents with edit permission** and **Models** (by **Subagent model**) and **Structured
question** (by **Tools**). For **Route skills** it adds only the commands, which only the user types, and the
runtime's skill names.

## Identity

Run `python3 -I "<skill-dir>/references/agents/antigravity/identity.py"` as written, where `<skill-dir>` is the
absolute directory of the loaded `SKILL.md`, during the executor's own turn, never inside a subagent: at the route's
start, with its `VENDOR` recorded in `gates.md` as the executor's vendor, and again before every edit subagent's
start and every reviewer dispatch, discovery and verification. It prints `MODEL:` and `VENDOR:`, or one
`BLOCKER:` line. A launch that prints none of these lines, a missing script, a missing interpreter or a crash:
blocked; name it and stop before any dispatch; never run an improvised check instead.

A `BLOCKER` line: blocked. A `VENDOR` equal to that of any reviewer in the gate's set (its locked row,
`references/reviewer-choice.md`) stops the route and is told to the user, with no reselection. A `VENDOR` other than the recorded
one blocks: no edit subagent and no review; tell the user the executor's vendor changed.

## Tools

No skill tool; `read_file` takes absolute paths only; skill and reference files are read with `read_file`,
never through `cat` or another shell command (measured: agy cut the middle of a long `cat` output), and a
partial read is continued from the offset or line range `read_file` returns until the whole file is read, before
acting on it (measured: a read stopped at 46,080 bytes); `run_command` backgrounds after at most 10 s,
completion arrives as a system message, output by `manage_task` or the task log; `invoke_subagent` with
`TypeName: self` for edits; `ask_question` with `is_multi_select`, its options passed in the dialog's order and with
no "(Recommended)" marker (otherwise the model reorders them and adds one). Todo lists are task artifacts. In Orca,
before every turn end while a dispatch of this run is unsettled (after `worker-start`, a follow-up, `send`, a
`reply`, a batch that leaves other workers running, or a non-terminal escalation), the executor starts
`ORCA orchestration check --terminal "$ORCA_TERMINAL_HANDLE" --peek --wait --timeout-ms 1800000 --json` with
`run_command`. One wait at a time. When it completes, inline or in the background, a clean timeout included, or Orca's
own wake arrives, the executor runs the consuming `ORCA orchestration check --terminal "$ORCA_TERMINAL_HANDLE" --json`
and handles that batch as `references/adapter-orca.md` says. A non-zero exit or an error: stop and tell the user, no new wait.
Measured: Orca did not wake an idle agy executor after its writers; its own task's completion did, and
`--peek --wait` returns on a new message without consuming it.

## Models

**Subagent model.** Always `Model: inherit`; the tiers (`flash_lite`, `flash`, `pro`) map to Gemini models whatever
the session runs. Measured: an `inherit` subagent under a Claude session ran that Claude model. An escalation is a
fresh `inherit` subagent, a ledger line.

## Route skills

The list and the catalog rules of `references/executor.md`, with this runtime's commands, which only the user types:
the executor shows them and stops, and runs no `agy` command itself. Superpowers: `agy plugin install
https://github.com/obra/superpowers` (agy does not read `~/.agents/skills`), then a new session; when it may be
installed but disabled or missing a skill (unverified), also `agy plugin enable superpowers`, or `agy plugin uninstall
superpowers` before the install. dopil: the README's Antigravity lines. Skills appear as `dopil:dopil`, typed
`/dopil:dopil`. Update: the same commands. Never `agy plugin import`: it imports every Claude Code plugin with its
hooks into every agy session.

## Instructions

Antigravity loads `GEMINI.md` and `AGENTS.md`, not `CLAUDE.md`: the generic **Repository
instructions** row applies.

## Runs that cannot take an answer

None.

## Orca writing workers

None. Orca never starts `agy` for this executor: Google's terms bar another agent driving agy on consumer plans, and
`worker-start --agent antigravity` may run it through `agy acp`. In Orca, edits stay with `invoke_subagent`, as
`references/executor.md`, **Orca without a card**, says.

## Follow-ups

None.

## Stop

The writers are the session's own `invoke_subagent` subagents. On the user's stop the executor starts no new one and
waits until every running one has finished, its completion seen, before any save or rollback of
`references/adapter-orca.md`, "Stopping at the user's request"; one it cannot see finish is named to the user, and the
tree is left as it is.

## Recovery

A subagent that fails to start or ends without its report: once it has finished, the executor does that task inline
itself, with a ledger line.

## Closing

None.

## Pitfalls

None.
