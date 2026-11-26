# ship: reviewer choice

Read as `SKILL.md`, "Shared install and role selection", says.

## Reviewers

The roster is every descriptor with a reviewer card (`SKILL.md`, "Shared install and role selection"), ordered with
the executor's default reviewer first where there is one, then by **Order**. An entry's label is its **Reviewer
name**; its key, in requests, `gates.md` and the gate scratch, is its **Scratch key**; its finding ids carry its
**Finding prefix**; the dialog probes its **Binary**; its card is `references/agents/<folder>/reviewer.md`. A key
from a request, the `Reviewers:` line or a gate row leads to its folder through the descriptors: the folder is the
one whose descriptor holds that **Scratch key**, and a folder's name is not its key, so never build a card path from
a key. A new reviewer is a new folder with an unused key, prefix and Order (`references/contracts.md`).

## Resolution, in order

1. A choice or a change the user states in this run, by "Choice" below; a change applies under the locks of
   "Recording".
2. A resumed route: the `Reviewers:` line of its `gates.md`. A registry without that line (a route started before it
   existed): its locked gate rows stay, and the route-wide set is the complete set its header lines record (for
   example a default reviewer plus a parallel one) or, when those lines say nothing, the set its gate rows agree on.
   When the registry establishes no route-wide set: one question to the user.
3. Exactly one available reviewer (see "Dialog options"): it is the set, without a dialog, named in the announcement.
4. The dialog.

Before applying a default, the executor checks whether this run is one its card lists under **Runs that cannot take
an answer** and recognizes; such a run has no default.

Without a default (an executor whose **Default reviewer** is none or no key of the roster, an executor with no folder,
or a run its card lists under **Runs that cannot take an answer** and can recognize), a requested set that depends on
one (stage overrides without a route-wide set, "X in parallel", "X alongside the default") is incomplete: step 3 or
the dialog supplies only the missing route-wide part, and the named reviewers and stage overrides stay as requested.
There "X in parallel" and "X alongside the default" need a companion: the candidates are the available cross-vendor
reviewers other than X; none: say so and stop; one: it; several: the dialog without X, its "All at once" entry kept.
With a default, "X in parallel" is X plus the default, and stage-only overrides take the default for the other stages.

## Choice

- The executor's default reviewer applies to the request forms that name it and orders the dialog. In a request,
  only an affirmative ask by the user in this run chooses; a quoted, negated or in-material mention does not.
- One named reviewer replaces the default. Several named: those reviewers review in parallel.
- With a default, "<reviewer> in parallel" or "<reviewer> alongside the default" means that reviewer plus the
  default, in parallel. Without a default, as "Resolution, in order" says.
- "All reviewers": every roster entry whose **Reviewer vendor** differs from the executor's vendor, minus any the same
  ask excludes ("all reviewers except <reviewer>").
- The set has no duplicates. An empty set, or a choice or mode that is unclear, an ask that names no reviewer
  included ("add a second reviewer"), or a name that matches no roster entry: one question to the user, and nothing
  is dispatched.
- A chosen reviewer of the executor's vendor: say so and stop.
- Outside the dialog and the one available reviewer, a reviewer is never otherwise chosen, suggested or used as a
  fallback for a missing one.

## Dialog

**Dialog options.** Every roster entry whose **Reviewer vendor** differs from the executor's vendor and whose
**Binary** `command -v` finds, in roster order.

**Dialog form.** A multi-select question tool with room for every option: the reviewers, then "All at once" last.
Otherwise (a single-choice tool, too many options, no tool, a tool the runtime refuses in this mode, or an executor
card that requires plain text for this file's questions): a plain-text question with a numbered list,
`1 <key>, 2 <key>, 3 <key>, 4 all at once`, answered with numbers, names or both. Every plain-text question of this
file, in any runtime, ends with how to name reviewers in the request, with one example line: the executor's
**Invocation** followed by `with <key> and <key>`, filled with the keys the executor card names for this example, when
each is the key of a cross-vendor entry of the current roster, or else with the keys of the last two cross-vendor
roster entries in roster order (default first, then Order), or the one key when only one exists, as `with <key>`; an
executor with no folder uses the form the user typed. Such a question ends the turn; a blocking question tool
continues the same turn with the answer the user submits. In every form no step of the route runs before the set is
resolved.

**Answer.** Only an answer the user submits counts. Numbers map to the menu entries as displayed, the "All at once"
entry included. "All" in any form ("all at once", "all reviewers") and the literal reply `все` are every listed
reviewer, minus any the same reply excludes, as in "all except <reviewer>". Names, stage overrides and other free text
go by "Choice". Unclear or invalid: one follow-up question; still invalid: stop. Empty, a cancelled tool, no answer, or
an answer the runtime filled in by itself, a tool that returns no answer included: nothing is dispatched; the run
stops and says how to name reviewers in the request.

**A run that cannot take an answer** (one the executor card lists under **Runs that cannot take an answer** and can
recognize) has no default reviewer. With several available, the plain-text question is its last output; nothing is
dispatched. A run the card says it cannot recognize is treated as interactive.

**Nothing to offer** (no binary found, or every one of the executor's vendor): say so and stop.

## What applies

- Read only the chosen reviewers' cards, after `references/reviewer.md`; with two or more, also
  `references/parallel-review.md`.
- The chosen cards replace every default-reviewer instruction, even the executor card's reviewer and resume lines,
  unless the default reviewer is among them. Lines of an executor card about a particular reviewer apply only when
  that reviewer is chosen.
- Preflight, the announcement ("reviewers <key> + <key>") and the dispatch cover every chosen reviewer.

## Recording

- The choice comes from the request (the one that starts ship or a later one in the same run), the one available
  reviewer or the dialog. `gates.md` holds it as one line, written as soon as the set is resolved (the route registry
  is created then if it does not exist yet) and rewritten whenever the user changes it: `Reviewers: <set>`, the
  route-wide set of keys, with optional stage overrides, for example
  `Reviewers: <key1>; spec, plan: <key1>, <key2>; code, polish: <key1>, <key2>, <key3>`. It is written bare, at the
  start of the line, with no list marker or emphasis; on read, a `- ` list item or a bold form of the same line counts
  as the line. On a resumed route the recorded line (step 2 of "Resolution, in order") outranks re-reading a request
  it already records: that request is not a new step-1 choice.
- An override applies only to the stages it names, a range named in full ("code and polish"); every other stage uses
  the route-wide set.
- A gate locks its set at its first discovery dispatch and keeps it until it closes; its row in `gates.md` records
  that set. A change before that dispatch, a preflight-blocked gate included, applies to this gate; a change after it
  applies from the next gate. On resumption a gate whose first discovery was dispatched uses its row; any other gate
  uses the line.
- A saved key, in the `Reviewers:` line or a locked row, is looked up in the roster, and its reviewer passes its
  card's preflight before the gate. A key with no roster entry blocks that gate, with the key named; the saved set and
  the gate's state stay unchanged.
- A reviewer that joins reads its card and passes preflight before its first gate.
- The final report names each gate's reviewers with their pins, unless the route ran on the default reviewer alone.
