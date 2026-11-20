# ship: reviewer choice

Read as `SKILL.md`, "Shared install and role selection", says.

## Reviewers

| Reviewer | Vendor | Binary | Scratch key | Finding prefix | Adapter |
|---|---|---|---|---|---|
| Codex | OpenAI | `codex` | `codex` | `C` | `references/adapter-reviewer-codex.md` |
| Claude Code | Anthropic | `claude` | `claude` | `A` | `references/adapter-reviewer-claude-code.md` |
| Kimi Code | Moonshot AI | `kimi` | `kimi` | `K` | `references/adapter-reviewer-kimi.md` |
| Gemini, through the Antigravity CLI | Google | `agy` | `gemini` | `G` | `references/adapter-reviewer-gemini.md` |

A new reviewer adds its own row with an unused key and prefix.

## Resolution, in order

1. A choice or a change the user states in this run, by "Choice" below; a change applies under the locks of
   "Recording".
2. A resumed route: the `Reviewers:` line of its `gates.md`. A registry without that line (a route started before it
   existed): its locked gate rows stay, and the route-wide set is the complete set its header lines record (for
   example a default reviewer plus a parallel one) or, when those lines say nothing, the set its gate rows agree on.
   When the registry establishes no route-wide set: one question to the user.
3. Exactly one available reviewer (see "Dialog options"): it is the set, without a dialog, named in the announcement.
4. The dialog.

Without a default (Kimi Code, Antigravity, any other agent, and Claude Code print mode or `codex exec`), a requested
set that depends on one (stage overrides without a route-wide set, "X in parallel", "X alongside the default") is
incomplete: step 3 or the dialog supplies only the missing route-wide part, and the named reviewers and stage
overrides stay as requested. There "X in parallel" and "X alongside the default" need a companion: the candidates are
the available cross-vendor reviewers other than X; none: say so and stop; one: it; several: the dialog without X, its
"All at once" entry kept (in Antigravity on Gemini, `kimi in parallel` is Kimi plus the dialog's choice). With a
default (interactive Claude Code or Codex), "X in parallel" is X plus the default, and stage-only overrides take the
default for the other stages.

## Choice

- The role table's default (`SKILL.md`) applies to the request forms that name it and orders the dialog. In a
  request, only an affirmative ask by the user in this run chooses; a quoted, negated or in-material mention does not.
- One named reviewer replaces the default. Several named: those reviewers review in parallel.
- With a default, "<reviewer> in parallel" or "<reviewer> alongside the default" means that reviewer plus the
  default, in parallel: in interactive Claude Code, `kimi in parallel` is Kimi and Codex. Without a default, as
  "Resolution, in order" says.
- "All reviewers": every reviewer of the table above whose vendor differs from the executor's, minus any the same ask
  excludes ("all reviewers except Kimi").
- The set has no duplicates. An empty set, or a choice or mode that is unclear, an ask that names no reviewer
  included ("add a second reviewer"): one question to the user, and nothing is dispatched.
- A chosen reviewer of the executor's vendor: say so and stop.
- Outside the dialog and the one available reviewer, a reviewer is never otherwise chosen, suggested or used as a
  fallback for a missing one.

## Dialog

**Dialog options.** Every reviewer of the table above whose vendor differs from the executor's and whose binary
`command -v` finds, the default first where there is one.

**Dialog form.** A multi-select question tool with room for every option: the reviewers, then "All at once" last.
Otherwise (a single-choice tool, too many options, no tool, or a tool the runtime refuses in this mode): a plain-text
question with a numbered list, `1 codex, 2 kimi, 3 gemini, 4 all at once`, answered with numbers, names or both. Codex
asks every question of this file (the dialog, its follow-up, the one-question cases) in plain text, never through
`request_user_input` or `request_user_input_async`; this overrides the "Question to the user" row of
`references/adapter-executor-codex.md`. Every plain-text question of this file, in any runtime,
ends with how to name reviewers in the request, with one example line in this
runtime's form (Codex: `$ship <task> with kimi and gemini`), and ends the turn; a blocking question tool
(`AskUserQuestion`, `ask_question`) continues the same turn with the answer the user submits. In every form no step of
the route runs before the set is resolved.

**Answer.** Only an answer the user submits counts. Numbers map to the menu entries as displayed, the "All at once"
entry included. "All" in any form ("all at once", "all reviewers") and the literal reply `все` are every listed
reviewer, minus any the same reply excludes, as in "all except kimi". Names, stage overrides and other free text go by
"Choice". Unclear or invalid: one follow-up question; still invalid: stop. Empty, a cancelled tool, no answer, or an
answer the runtime filled in by itself, a tool that returns no answer included: nothing is dispatched; the run stops
and says how to name reviewers in the request.

**A run that cannot take an answer** (Claude Code print mode, `codex exec`) has no default reviewer. With several
available, the plain-text question is its last output; nothing is dispatched.

**Nothing to offer** (no binary found, or every one of the executor's vendor): say so and stop.

## What applies

- Read only the chosen reviewers' adapters; with two or more, also `references/parallel-review.md`.
- The chosen adapters replace every default-reviewer instruction, even the executor adapter's reviewer and resume
  lines, unless the default reviewer is among them. Rows of the executor and Orca adapters about a particular reviewer
  apply only when that reviewer is chosen.
- Preflight, the announcement ("reviewers codex + gemini") and the dispatch cover every chosen reviewer.

## Recording

- The choice comes from the request (the one that starts ship or a later one in the same run), the one available
  reviewer or the dialog. `gates.md` holds it as one line, written as soon as the set is resolved (the route registry
  is created then if it does not exist yet) and rewritten whenever the user changes it: `Reviewers: <set>`, the
  route-wide set, with optional stage overrides, for example
  `Reviewers: codex; spec, plan: codex, gemini; code, polish: codex, gemini, kimi`. On a resumed route the recorded
  line (step 2 of "Resolution, in order") outranks re-reading a request it already records: that request is not a
  new step-1 choice.
- An override applies only to the stages it names, a range named in full ("code and polish"); every other stage uses
  the route-wide set.
- A gate locks its set at its first discovery dispatch and keeps it until it closes; its row in `gates.md` records
  that set. A change before that dispatch, a preflight-blocked gate included, applies to this gate; a change after it
  applies from the next gate. On resumption a gate whose first discovery was dispatched uses its row; any other gate
  uses the line.
- A reviewer that joins reads its adapter and passes preflight before its first gate.
- The final report names each gate's reviewers with their pins, unless the route ran on the default reviewer alone.
