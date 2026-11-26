# ship: connecting an agent

Read before connecting an agent or changing an agent folder.

## The folder

Everything ship knows about one agent lives in `references/agents/<folder>/`: the descriptor `agent.md`, the executor
card `executor.md`, the reviewer card `reviewer.md`, and the scripts and profiles its cards name. The core
(`SKILL.md` and the files directly in `references/`) names no agent: the roster comes from the descriptors, so a new
agent is connected by adding its folder. No file in a folder contains a path into another agent's folder, and a card
names a core file by its full path (`references/executor.md`), never bare.

The descriptor is a table `| Field | Value |`, one row per field. A field outside its role is absent, not none.

| Field | Required | Value |
|---|---|---|
| Name | always, unique | The runtime's name; startup matches it against where ship was invoked |
| Executor card | always | `executor.md` or none |
| Reviewer card | always | `reviewer.md` or none; not both none |
| Invocation | with an executor card | How the user types ship in this runtime, with `<task>`; the naming hint's example |
| Default reviewer | with an executor card | The scratch key of a reviewer in another folder, or none |
| Binary | with a reviewer card | The CLI the dialog probes with `command -v` |
| Reviewer name | with a reviewer card | The dialog's label |
| Reviewer vendor | with a reviewer card | The vendor of the model it reviews with |
| Scratch key | with a reviewer card, unique | Gate-scratch subdirectory and `Reviewers:` token; `[a-z0-9-]+` |
| Finding prefix | with a reviewer card, unique | One capital letter |
| Order | with a reviewer card, unique | Positive integer: the dialog position after the default; a new agent takes the next free number |

A Scratch key and a Finding prefix never change once released: saved routes name them.

## Executor card contract

An executor is plugged in through `references/executor.md` and, if it has one, its card; both are read before the
first step of the route. A card is read after `references/executor.md`, names in its opening lines the rows it
overrides, and overrides only those. A row without a working fallback is blocking. Route skills are not replaced by a
manual pass: if the needed one is missing, say which one and stop, as with a missing reviewer card.

Its parts, as headings in this order: **Identity**, **Tools**, **Models**, **Route skills**, **Instructions**, **Runs
that cannot take an answer**, **Orca writing workers**, **Follow-ups**, **Stop**, **Recovery**, **Closing**,
**Pitfalls**. A part the generic row covers as this runtime needs is the one line
``As `references/executor.md`, **<row>**.``; a part with nothing for this runtime is `None.`. **Stop** and
**Recovery** always say how this executor's writers stop and recover, and a card may name the keys of its naming
hint's example (`references/reviewer-choice.md`, "Dialog form").

| Capability | Why | Fallback | Part |
|---|---|---|---|
| Who the executor is: vendor, model family | Otherwise there is nothing to check the "reviewer ≠ executor" invariant against | None. Unknown who is executing — blocks | Identity |
| Background launch of a long command | Discovery takes minutes and must not be lost to a timeout | A timeout above 15 minutes | Tools |
| Subagents with permission to edit files | Parallel fixing of findings in non-overlapping files | Fix sequentially and say in the report that there was no parallelism | Tools |
| A simplifying pass over the diff that applies edits | Polish: reuse and simplification | Go through the diff by hand against the same criteria, say that the pass was manual | Tools |
| A "what can be deleted here" pass that lists | Polish: deletion | Same | Tools |
| A structured question to the user | Escalation | A plain text question | Tools |
| Route skills | Spec, plan, TDD, isolation, per-task loops | None for the skill file itself; for the mechanism the skill asks for — yes | Route skills |

The other parts: **Models**, the model of every role and its escalation; **Instructions**, the instruction files the
runtime loads itself; **Runs that cannot take an answer**, each such mode, and whether the run can recognize it (one
it cannot is treated as interactive); **Orca writing workers**, **Follow-ups**, **Stop**, **Recovery** and
**Closing**, how its writers start, take follow-ups, stop with proof, recover from a failed start or a writer lost
mid-task, and close (`references/adapter-orca.md`); **Pitfalls**.

An identity check longer than one line ships as a Python script in the folder, run by absolute path with
`python3 -I` from the loaded `SKILL.md`'s directory. It prints fixed lines or one `BLOCKER:` line with a non-zero
exit, never a credential or the environment; a launch that prints no recognized line blocks.

## Reviewer card contract

The parts of a reviewer card, and when the executor uses each, are in `references/reviewer.md`. The card covers
these capabilities. A row without a working fallback is blocking: without it the reviewer is not fit for ship, and
the user is told so rather than having it worked around.

| Capability | Why | Fallback | Part |
|---|---|---|---|
| Who the reviewer is: vendor, model family, version | Otherwise there is nothing to check the "reviewer ≠ executor" invariant against mechanically | None. Unknown who is answering — blocks | Contract card, Preparation and pin |
| A discovery call over a scope described in prose | The gate scope cannot always be expressed with flags: from a saved SHA to the working tree or to a fixed end SHA | Scope flags, if they cover exactly the needed slice. Neither one nor the other — blocks | Calls |
| Verification in the **same** thread, addressed by id | The reviewer keeps its own list in context; a narrow question converges, a fresh one does not | None. The card must provide a thread in every mode it has declared | Calls |
| Distinguishable "clean" / "findings" / "run did not happen" | The gate's exit condition | A last-line contract in the prompt. If it does not hold — blocks | Acceptance |
| "File as is" mode, without a git diff | Spec, plan, file outside the repository, unchanged file | None. A reviewer that cannot read a file by path is not fit for ship | Calls |
| The reviewer itself re-reads the current state on verification | Otherwise it judges the fix by the executor's retelling | The delta from the saved base in the prompt; snapshots and deletion — per the rules of "Polish" (`references/polish.md`) | Calls, Prompts |
| Confirmation of reading the baseline and of scope coverage | A clean verdict without the material having been read does not close the gate | Successful reads in the events or the full material in the reviewer's context; without proof the run does not count | Acceptance |
| The run survives a long wait | Measured: a round on a 221-line diff took 541 s, did not fit into a 10-minute timeout and was lost entirely | Background launch, if the runtime supports it; otherwise a timeout above 15 minutes | Calls |
| The pin of the model and of all settings that affect the output is visible and recorded | Without it rounds are not comparable with each other | A setting the reviewer does not have (for example reasoning effort) — an explicit `N/A`. An unknown value of an existing setting blocks | Preparation and pin |

A new card is written against this table: cover every row with a command or a fallback, check on a live run that
discovery returns a list and that verification — in the thread or through the declared fallback — returns a verdict,
and only after that put it into the route.

## Outside the skill

An agent with an executor card also needs, in this repository: its plugin manifest at the repository root, which the
unit tests validate; its install section in `README.md`, ending with its own update line; and its launch rows in
`tests/live/runtimes.md`. Every role also needs its instances in the live check kit's cases (`tests/live/cases.md`).

## Done

An agent is connected when the unit tests pass and the live check kit's cases for each of its roles pass, run as
`tests/live/runner-brief.md` says.

## Known pitfalls

- Orca may not wake an idle TUI executor: the card arms its own background wait before every turn end.
- A runtime may cut long shell output or a partial file read: read every file with its file tool, whole.
- A non-interactive mode may be indistinguishable from an interactive one: the card lists what it can and cannot
  recognize.
- A weak model rewrites inline blocks: a check longer than one line ships as a script.
- New worktrees raise trust prompts: the card says how a start waits for the user's answer.
- An update prompt blocks a CLI's start: show the user the screen and repeat after they clear it.
- A login shell may restore a `PATH` a test removed: a kit case proves the binary is hidden before it counts.
- A reopened worker may lose its start flags: the card either never reopens its workers with `send` or says what a
  reopened worker loses.
