# ship: reviewer

Read before the first reviewer call of every gate, then the card of each reviewer in the gate's set,
`references/agents/<folder>/reviewer.md`. This file says what every card holds and when the executor uses each part.
The gate protocol is in `references/gate.md` and the prompt frameworks are in `references/prompts.md`; a card holds
only its reviewer's commands, checks and pitfalls.

Every reviewer card has these parts, as headings in this order. A part with nothing for its reviewer is the one line
`None.`

| Part | What it holds | When the executor uses it |
|---|---|---|
| Contract card | The card filled against the reviewer card contract of `references/contracts.md` | Before the first call, to know the reviewer's modes, thread, read proof and pin |
| Requirements | The CLI, its versions and the tools its commands need. Any missing one blocks, with no fallback reviewer | Preflight, before the gate's preparation |
| Preparation and pin | The steps before the first discovery of each gate: whether the user is asked to choose a model, what blocks, and where the pin is recorded (the ledger, `gates.md`, receipts) | Before the first discovery of each gate; the pin then holds for the whole gate |
| Calls | Discovery and verification per mode (file, diff, snapshot), the files each round and attempt writes, how a retry is numbered, how the prompt is delivered | Every round |
| Acceptance | What counts as a run that happened, clean or findings, per mode and phase, with its read proof; which files a counted attempt writes, in which order | After every attempt, before triage |
| Prompts | The role lines, the card's substitutions in the frameworks of `references/prompts.md`, the input files and their budget | When the round prompt is assembled |
| Orca | The card's departures from `references/adapter-orca.md`: an Orca agent worker with its values, or its own start, verification and checks | Every round when the session runs in Orca |
| Gate end | Every trigger (closed, abandoned, stopped by the user, and the card's own) with its steps, proof and order | When the gate ends |
| Access | What an executor in a sandbox grants per command: network, login, state directory | Before every call from a sandboxed executor |
| Pitfalls | Known traps of the reviewer's CLI | Before the first call |

When the session runs in Orca, the card's **Orca** part, with `references/adapter-orca.md`, takes the place of
**Calls** and **Acceptance**, except for what that part takes from them by name.

A run that did not happen is not a round (`references/gate.md`): the card's **Acceptance** decides, and the retry
follows its **Calls**. A response that passed **Acceptance** is not yet a counted round when the gate has several
reviewers: `references/parallel-review.md` can void it.
