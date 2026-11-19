# ship: reviewer choice

Read as `SKILL.md`, "Shared install and role selection", says.

## Reviewers

| Reviewer | Vendor | Scratch key | Finding prefix | Adapter |
|---|---|---|---|---|
| Codex | OpenAI | `codex` | `C` | `references/adapter-reviewer-codex.md` |
| Claude Code | Anthropic | `claude` | `A` | `references/adapter-reviewer-claude-code.md` |
| Kimi Code | Moonshot AI | `kimi` | `K` | `references/adapter-reviewer-kimi.md` |
| Gemini, through the Antigravity CLI | Google | `gemini` | `G` | `references/adapter-reviewer-gemini.md` |

A new reviewer adds its own row with an unused key and prefix.

## Choice

- The table's reviewer in `SKILL.md` is the default. Only an affirmative ask by the user in this run chooses
  otherwise; a quoted, negated or in-material mention does not.
- One named reviewer replaces the default. Several named: those reviewers review in parallel.
- "<reviewer> in parallel" or "<reviewer> alongside the default" means that reviewer plus the default, in parallel:
  `kimi in parallel` is Kimi and the default.
- "All reviewers": every reviewer of the table above whose vendor differs from the executor's, minus any the same ask
  excludes ("all reviewers except Kimi").
- The set has no duplicates. An empty set, or a choice or mode that is unclear, an ask that names no reviewer
  included ("add a second reviewer"): one question to the user, and nothing is dispatched.
- A chosen reviewer of the executor's vendor: say so and stop.
- A reviewer is never otherwise chosen, suggested or used as a fallback for a missing one.

## What applies

- Read only the chosen reviewers' adapters; with two or more, also `references/parallel-review.md`.
- The chosen adapters replace every default-reviewer instruction, even the executor adapter's reviewer and resume
  lines, unless the default reviewer is among them. Rows of the executor and Orca adapters about a particular reviewer
  apply only when that reviewer is chosen.
- Preflight, the announcement ("reviewers codex + gemini") and the dispatch cover every chosen reviewer.

## Recording

- The choice comes in the request that starts ship or later in the same run. `gates.md` holds it as one line,
  rewritten whenever the user changes it: `Reviewers: <set>`, the route-wide set, with optional stage overrides, for
  example `Reviewers: codex; spec, plan: codex, gemini; code, polish: codex, gemini, kimi`.
- An override applies only to the stages it names, a range named in full ("code and polish"); every other stage uses
  the route-wide set.
- A gate locks its set at its first discovery dispatch and keeps it until it closes; its row in `gates.md` records
  that set. A change before that dispatch, a preflight-blocked gate included, applies to this gate; a change after it
  applies from the next gate. On resumption a gate whose first discovery was dispatched uses its row; any other gate
  uses the line.
- A reviewer that joins reads its adapter and passes preflight before its first gate.
- The final report names each gate's reviewers with their pins, unless the route ran on the default reviewer alone.
