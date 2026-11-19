# ship: parallel review

Read only when the user asked for Kimi in parallel (`SKILL.md`). Two equal reviewers, the table's reviewer and
Kimi, review every gate of the route: spec, plan, code, polish delta, confirmation pass. Each follows its own
adapter and the core rules; this file lists only what changes.

## Preparation and layout

- Both reviewers pass preflight and, at each gate, their adapter's preparation before either discovery starts.
  Either one blocked: the gate is blocked; never go on with one reviewer.
- Each reviewer's scratch `<gate scratch>/<reviewer>/` (`codex`, `claude`, `kimi`) is a complete gate scratch for
  its adapter, and `SHIP_GATE` points there: its own copy of `base-sha` or of the snapshot description, its
  `thread-id`, `ledger.md`, pin and round files.
- The gate scratch root holds the shared round state. Before the pair round's first reviewer call, write
  `round-NN-state` (the scoped diff or snapshot hash; it is also that round's stall-rule save) and the
  before-fingerprints, `round-NN-tree-before` (plus the `-doc-` pair); `round-NN-tree-after` follows when both
  responses are in. The fingerprints are taken with the commands of `references/adapter-orca.md`, "What Orca
  does not provide", in and outside Orca.
- `NN` at the root numbers the pair round; each reviewer's ledger records its own round file for each pair round.
  A retry in a new scratch follows `references/ledger.md`.
- `gates.md` names both reviewer scratches, their pins and thread files for this gate, so a resumed coordinator
  finds both.
- Each reviewer has its own thread, its own frozen discovery list and its own ledger. Finding ids carry the
  reviewer's initial: `C1` Codex, `A1` Claude, `K1` Kimi. Known task-review items from SDD go to both discoveries,
  and each reviewer's decision on them is kept in its own ledger.

## Rounds

- Every round is a pair round over one recorded state: `round-NN-state` and the fingerprints. Both reviewers get
  that same state; nothing is edited until both responses of the round are in.
- A round counts only when both responses are in and the after-fingerprints match the before-fingerprints. A
  mismatch voids both responses of the round. A verdict counts only for the state it covered. A voided round, for
  this or any other reason below, is handled as a fingerprint mismatch in `references/adapter-orca.md` (outside git,
  name the changed scope paths), in headless runs too. Before the next pair, both attempts of the voided round
  settle: a `worker_done` or a stop confirmed as `references/adapter-orca.md` requires (headless: the process has
  ended); a reviewer whose previous attempt may still run is never started. A voided discovery freezes no list:
  both reviewers run discovery again on the next recorded state. A voided verification keeps the last counted
  lists: both reviewers verify the next recorded state in their same threads.
- Each reviewer's ledger records which rounds counted and marks a voided round as voided, whatever its adapter
  already wrote to `last-review.txt`. The ledger, not that file, is what triage and the report read.
- Triage applies its normal rules to every finding of both lists: check the premise, fix, reject with proof, or
  escalate. When findings of both reviewers lead to the same fix, the fix is made once and each reviewer gets the
  response line for its own finding. Contradicting findings are triaged the same way; neither wins by default.
- One round message per round covers both reviewers; its header names both.
- Then both reviewers verify in their own threads on the new state. For each reviewer, the edits made for the
  other reviewer's findings are disclosed with the block "ADDITIONAL EDIT, not raised by you" of the verification
  framework (`references/prompts.md`). A reviewer whose list is already closed verifies every later state too,
  until the gate closes.
- The gate closes when, on the same final state, each reviewer has either a clean discovery with no edits after it
  or `VERDICT: ALL RESOLVED`, and both ledgers have no open line (known-item decisions included); for code and
  config gates the checks run on that state as well.
- A run that did not happen for one reviewer is rerun for that reviewer only, on the same recorded state; the
  other's response of that round stands. Before the retry, compare the current scoped diff or snapshot hash with
  `round-NN-state`; a difference voids the round.
- Stall rules apply to each reviewer's list, counted only over rounds where that reviewer had open lines.
  Escalation rules are unchanged.

## Orca

- The two reviewer workers run at the same time; there are no writing workers during the round, and one
  fingerprint pair covers both.
- The Kimi terminal of a gate is closed when the gate ends, as `references/adapter-reviewer-kimi.md`, "Orca", says.

## Final report

Under the table: both reviewers, each with its pin per gate (one line when no pin changed between gates). Each row
shows whose finding it was.
