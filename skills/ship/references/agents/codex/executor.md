# Executor card: Codex

The executor is Codex (OpenAI, GPT family). The chosen reviewers come from `references/reviewer-choice.md`, and
their cards are read before the first gate.

Read after `references/executor.md`. This card overrides its rows **Who the executor is** (by **Identity**),
**Background launch**, **Subagents with edit permission**, **Simplifying and deletion passes** and **Structured
question** (by **Tools**), **Models**, **Route skills**, **Repository instructions** (by **Instructions**) and **Orca
without a card** (by **Orca writing workers**, **Follow-ups**, **Stop**, **Recovery** and **Closing**), and adds
**External CLI access** to **Reviewer calls and long waits**. **Engineering baseline** applies as written.

## Identity

| Capability | Covered by |
|---|---|
| Who the executor is | The system context of the current session identifies Codex/OpenAI/GPT; in the local CLI an additional marker is a non-empty `CODEX_THREAD_ID`. Take the model version from the session context; do not guess it from someone else's config |

## Tools

| Capability | Covered by |
|---|---|
| Long launch | `exec_command` returns the `session_id` of the live process, then `write_stdin` reads the result. In a runtime with `functions.exec`, first wait for the tool call itself; if it returned a `cell_id`, continue via `functions.wait`. These are different IDs, and neither of them is the reviewer's ID |
| External CLI access | A reviewer CLI may need the network, its login and writing its own state; the selected reviewer card's **Access** names what. Check the permissions currently in effect in the runtime; `~/.codex/config.toml` alone does not determine them. If access is already granted, launch right away. If the sandbox actually forbids the needed access, use the permission mechanism the runtime provides for this command only; bypassing the ban or changing the global config is not allowed |
| Subagents with edit permission | The delegation mechanism available in the current Codex: `collaboration.spawn_agent` or `spawn_agent`. Only non-overlapping files and the current session's permissions. No mechanism — sequential work, note it in the report. In Orca, edits are made by `--agent codex` workers per the section "Executor as worker" in `references/adapter-orca.md`; the own mechanism remains for reading, exploration and task review |
| Simplifying pass | An available simplification skill; otherwise a manual pass over your own diff: reuse and reduction, noted in the report |
| Deletion pass | `ponytail-review`, if available; otherwise a separate manual "what can be deleted" pass |
| Question to the user | The available `request_user_input_async`; `request_user_input` only in a mode where it is allowed; otherwise a plain text question |

**Questions of `references/reviewer-choice.md`.** Codex asks every question of that file (the dialog, its follow-up,
the one-question cases) in plain text, never through `request_user_input` or `request_user_input_async`; this
overrides the "Question to the user" row above.

**Long review.**
Launch the helper from the reviewer card as a process with the access described in the selected reviewer card's
**Access**; with a short yield it keeps running. A sandbox refusal is a launch that did not happen:
first remove the specific restriction in a permitted way, then repeat, without counting the round.
If the runtime does not allow the necessary access, name the restriction and leave the gate open.
Wait via `write_stdin` with empty input and report progress regularly.
Do not launch a second instance of the same round while the first one is alive.

## Models

For workers and subagents the model is set explicitly, by the SDD tiers: the base working model for
executors and fixers, a cheap one for mechanical work from a ready plan, the strongest one only by escalation
(fix rounds 4–5, `BLOCKED` due to complexity). Take the concrete GPT line IDs from the user's
instructions; if there are none — one question before the first dispatch.

## Route skills

| Capability | Covered by |
|---|---|
| Route skills | `superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:test-driven-development`, `superpowers:using-git-worktrees`, `superpowers:subagent-driven-development`; auxiliary — `superpowers:receiving-code-review`, `superpowers:verification-before-completion`, `superpowers:finishing-a-development-branch`. Each counts as present when the catalog lists it either as `superpowers:<skill>` (plugin install) or as bare `<skill>` (skills directory install). If any is missing: stop and tell the user to install it with `/plugins`: search for superpowers, install |

**How to read dependencies.**
Look the skill up in the current session's catalog of available skills; the registered name may lack
`superpowers:`. If there is no Skill call, reading the full `SKILL.md` at the path given in the catalog
and following its instructions is the standard way of using it. A missing Skill tool does not mean
the skill is missing. If the file itself is missing — name the missing dependency, as the core requires.

## Instructions

The order of stages is set by ship, the repository's requirements by its `AGENTS.md`. Do not repeat a
brainstorm already held and do not create a second worktree if the current session is already isolated. Questions that affect
the product or the scope are asked to the user; technical findings are worked through independently.

## Runs that cannot take an answer

`codex exec` cannot take an answer, but the run cannot recognize it: it is treated as interactive.

## Orca writing workers

Task executors, gate fixers, parallel fixers, polishers and fix rounds 4–5 are `--agent codex` workers, started as the
table of `references/adapter-orca.md`, "Executor as worker", says; the task executor:
`ORCA orchestration worker-start --spec-file "$W/task-N-dispatch.md" --task-title "ship impl: task N" --worktree
"<tree selector>" --agent codex --model <GPT id per Models> --json > "$W/task-N-receipt.json"`. The model is set
explicitly for each worker via `--model`, per **Models**: invoking ship is the user naming the model in the sense of
the `orchestration` guide, which otherwise adds `--model` only on the user's word. Write `agent` and `model` from the
receipt to the SDD ledger.

## Follow-ups

Fix rounds 1–3, the gate fixer's later rounds and polish follow-ups go by `send` to the latest dispatch, as
`references/adapter-orca.md`, "Executor as worker", says. If the receipt says `delivery: started_fresh`, Orca could
not reopen the worker and a new one took the round — a line in the ledger. Fix rounds 4–5: a new `worker-start` on a
model one step above the stuck one, per **Models**. Nothing higher in the same vendor — the same model as a fresh
worker, a line in the ledger. Do not wake the stuck one again.

## Stop

`ORCA orchestration worker-stop --dispatch <latest dispatchId> --json`, in the sequence of
`references/adapter-orca.md`, "Stopping at the user's request". The stop is confirmed only if the response has
`state: stopped`, `processAction: closed_agent_terminal` and `close.ptyKilled: true`.

## Recovery

**Failed start.** Only after the proof `references/adapter-orca.md`, "If the worker did not start", requires does
the delegation mechanism of **Tools** take over the task, and the report says so. No proof — the task waits.

**A writer lost mid-task.** As the `orchestration` guide says: retry it or tell the user.

## Closing

Orca closes finished workers itself.

## Pitfalls

None.
