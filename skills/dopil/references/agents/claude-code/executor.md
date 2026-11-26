# Executor card: Claude Code

Read after `references/executor.md`, before the first step of the route. This card overrides its rows **Who the
executor is** (by **Identity**), **Background launch**, **Subagents with edit permission**, **Simplifying and deletion
passes** and **Structured question** (by **Tools**), **Models**, **Route skills**, **Repository instructions** (by
**Instructions**) and **Orca without a card** (by **Orca writing workers**, **Follow-ups**, **Stop**, **Recovery** and
**Closing**). **Engineering baseline** and **Reviewer calls and long waits** apply as written.

## Identity

| Capability | Covered by |
|---|---|
| Who the executor is | Mechanically: `test "${CLAUDECODE:-}" = 1` confirms Claude Code, and `test -z "${CODEX_SANDBOX:-}${CODEX_THREAD_ID:-}"` confirms that the run is not going on **inside** codex. Both markers are set by the runtime itself. The agent additionally states the model family and version aloud |

## Tools

| Capability | Covered by |
|---|---|
| Background launch | `run_in_background` of Bash |
| Subagents with edit permission | Invoking dopil lifts the session restriction "do not call subagents unless asked": the invocation is the user's permission. `Agent`. **Not `Workflow`**: its subagents are always in `acceptEdits` regardless of the session mode. In Orca, edits are made by `--agent claude` workers per the section "Executor as worker" in `references/adapter-orca.md`; `Agent` remains for reading, exploration and task review, `Workflow` is not fit there either |
| Simplifying pass | The `simplify` skill, if registered. Not registered — a manual pass against the same criteria and a line in the report that the pass was manual |
| Deletion pass | The `ponytail:ponytail-review` skill, if registered. Not registered — a manual pass and a line in the report |
| Structured question | `AskUserQuestion` |

## Models

Applies to Orca workers (`--model`) and to own subagents (`model` of `Agent`). The model
is set explicitly on every launch: an omitted one inherits the session's model, which is usually more capable and more
expensive than the task needs.
A direct instruction from the user takes precedence over the table. The external reviewer's model does not belong here: its pin is in
the reviewer card.

| Role | Model |
|---|---|
| Main agent: route, spec, plan, triage, rulings, gates | The session's own model. Dopil does not switch it |
| Task executor, fixer of gate findings, polish | `opus` |
| Mechanical task: ready code or exact values are in the plan, 1–2 files | `sonnet` |
| SDD task reviewer | `opus`; re-review of a small fix — `sonnet` |
| Exploration, search, running checks | `sonnet` |
| Escalation: fix rounds 4–5, `BLOCKED` due to complexity, a task with an architectural choice | One class up: `sonnet` → `opus` → `fable`. When no higher class is available to the user, the same class as a fresh worker, with a line in the ledger. The session's own model is never an escalation target by itself: it may be lower than the stuck worker's class |

A doubt between `sonnet` and `opus` is resolved in favour of `opus`: the extra turns of a cheap model cost more than its price.
Do not give `fable` to workers on the first attempt: it is a targeted escalation, not the base model. Pass the class
alias; the runtime resolves it to the newest model of that class. A class the user cannot use is replaced by the
next class up when one is available, otherwise by the next one down, and the report says so.

## Route skills

| Capability | Covered by |
|---|---|
| Route skills | The superpowers plugin: brainstorming `superpowers:brainstorming`, planning `superpowers:writing-plans`, TDD `superpowers:test-driven-development`, isolated tree `superpowers:using-git-worktrees`, per-task loops `superpowers:subagent-driven-development`; auxiliary — receiving review `superpowers:receiving-code-review`, verification before completion `superpowers:verification-before-completion`, branch finishing `superpowers:finishing-a-development-branch`. The namespace depends on the agent: in another runtime the same skills are registered differently. Each counts as present when the catalog lists it either as `superpowers:<skill>` (plugin install) or as bare `<skill>` (skills directory install). If any is missing from the catalog: stop and tell the user to run `/plugin install superpowers@claude-plugins-official`. |

## Instructions

None beyond what Claude Code loads itself: the **Repository instructions** row of `references/executor.md` does not
apply.

## Runs that cannot take an answer

Print mode (`claude -p`): recognized when the runtime says the session is non-interactive or `AskUserQuestion` is
not among the tools. Then there is no default reviewer, as `references/reviewer-choice.md`, "A run that cannot take
an answer", says.

## Orca writing workers

Task executors, gate fixers, parallel fixers, polishers and fix rounds 4–5 are `--agent claude` workers, started as the
table of `references/adapter-orca.md`, "Executor as worker", says; the task executor:
`ORCA orchestration worker-start --spec-file "$W/task-N-dispatch.md" --task-title "dopil impl: task N" --worktree
"<tree selector>" --agent claude --model <class per Models> --json > "$W/task-N-receipt.json"`. The model is set
explicitly for each worker via `--model`, per **Models**: invoking dopil is the user naming the model in the sense of
the `orchestration` guide, which otherwise adds `--model` only on the user's word. Write `agent` and `model` from the
receipt to the SDD ledger.

The route's isolated tree is Orca's (`references/adapter-orca.md`, "Isolated tree"), not `EnterWorktree`: Orca does
not show trees in `.claude/worktrees/` in the panel; workers in them are alive but invisible.

**A reopened Claude worker does not keep its permission mode.** Orca resumes the session without the
permission flag of the first start, so the worker runs in the default mode of the user's Claude Code settings.
A reopened worker that goes silent may be waiting for an approval in its tab: tell the user to look there
before treating it as stuck.

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
`Agent` (**Tools**) take over the task, and the report says so. No proof — the task waits.

**A writer lost mid-task.** As the `orchestration` guide says: retry it or tell the user.

## Closing

Orca closes finished workers itself.

## Pitfalls

**Runtime rules that dopil lifts.**
`codex-result-handling` requires stopping after showing review findings and not applying fixes. Inside
dopil rounds this does not apply: the round's findings are shown to the user in the round message; it is a
progress report, not a question about what to fix, and the user permitted applying them by invoking the skill.
Outside dopil the rule applies as written. The exception is the same as before: a change of agreed behaviour is
escalated.

- `Workflow` and `Agent` differ not in performance but in edit mode. Mixing them up means
  getting accepted edits where you expected review
- Route skills are looked up where the runtime registered them; the `~/.agents/skills/` directory is understood by
  other runtimes too, so one clone of superpowers serves several agents at once
