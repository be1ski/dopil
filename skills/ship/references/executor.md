# Executor: generic rule

Read by every executor, before its card if it has one; a card overrides a row only where it says so. The rows cover
the executor contract (`references/contracts.md`) with the runtime's own tools and add the conventions every executor
shares.

**Who the executor is.** The vendor and model family of the model the session runs, not of the CLI. The card names
the mechanical proof. Without a card, the agent's own statement is the only proof: say so in the announcement.

**Background launch.** The runtime's background shell: completion by its notification, output from its task output.
No background mechanism: a foreground timeout above 15 minutes.

**Subagents with edit permission.** The runtime's edit-capable subagent, which must run a model of the executor's
vendor: the session's model unless the card names another same-vendor choice. When no same-vendor edit subagent is
usable (the runtime has none, cannot guarantee its model, or the card's model proof failed), there are no edit
subagents for the route: the full route executes the plan inline with superpowers' `executing-plans` instead of
`subagent-driven-development`, fixes are sequential, the gates are unchanged; a line in the report. On an Orca
route whose card supplies writing workers, those **Orca writing workers** are the edit mechanism, and the in-session
edit subagent question and the `executing-plans` fallback of this row do not apply there.

**Models.** The card's rule. Without a card: the session's model for every role; the escalation SDD's fix loop asks
for (one class up) runs on the same model, taken by a fresh edit subagent or Orca writer only where the route has
one; with none, the work stays inline; a ledger line.

**Simplifying and deletion passes.** The registered `simplify` and `ponytail-review` skills if present; otherwise
manual passes against the same criteria, each named as manual in the report.

**Structured question.** The runtime's question tool for escalations; the dialog's form is set in
`reviewer-choice.md`. No tool: a plain-text question.

**Route skills.** `brainstorming`, `writing-plans`, `test-driven-development`, `using-git-worktrees`,
`subagent-driven-development` and `executing-plans` (both: which one runs may be settled only by a card's later model
proof, and `executing-plans` uses the scripts of `subagent-driven-development`), `receiving-code-review`,
`verification-before-completion`, `finishing-a-development-branch`; each is present by bare name or with a
namespace prefix. A runtime without a skill tool reads a skill's `SKILL.md` by the absolute path its catalog gives
and resolves relative paths against that file's directory. A missing skill: name it and its package (superpowers,
`https://github.com/obra/superpowers`), give the card's install command if it has one, otherwise ask the user to
install it through their agent's plugin mechanism; never invent a command; stop.

**Repository instructions.** Read the instruction files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) that apply to the
paths of the work and that the runtime did not load itself; every writing subagent's and worker's assignment names
them.

**Engineering baseline.** Mandatory `pragmatic-engineering`; resolve the path, read it and pass it to all reviewers
and polish passes per the core's section "Baseline approach to review" (`SKILL.md`) and `references/gate.md`,
section "Engineering baseline in review prompts".

**Environment.** Never print the environment or a filtered dump of it: no bare `env`, `export`, `set` or
`printenv`, and no `env | grep` of a prefix (`grep` over the environment is a dump too). Read a needed variable by its
name, one named variable at a time, and never print a variable whose name says token, key, secret or password.

**Reviewer calls and long waits.** Per the chosen reviewers' cards, which use only shell commands; a long run
goes through **Background launch**.

**Orca without a card.** Applies to an executor that has no card or whose card supplies no Orca writing workers.
Reviewers still run as Orca workers per `adapter-orca.md`. Edits stay with the executor's own edit subagents or its
sequential inline work: an exception to "In Orca only workers edit code", named in the report. The fingerprint and
one-writer rules of `adapter-orca.md` are kept, with these in-session writers in place of writing workers: every one
of them has settled (finished, nothing left running in the background) before any fingerprint, save or rollback.
