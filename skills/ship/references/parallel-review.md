# ship: parallel review

Applies to every gate that runs with more than one chosen reviewer (`references/reviewer-choice.md`), whatever the
stage: spec, plan, code, polish delta, confirmation pass. The chosen reviewers are equal. Each follows its own
adapter and the core rules; this file lists only what changes.

## Preparation and layout

- Every chosen reviewer of the gate passes preflight and its adapter's preparation before any discovery starts. One
  of them blocked: the gate is blocked; never go on with fewer reviewers.
- Each reviewer's scratch `<gate scratch>/<key>/`, with the scratch key of `references/reviewer-choice.md`, is a
  complete gate scratch for its adapter, and `SHIP_GATE` points there: its own copy of `base-sha` or of the snapshot
  description, its `thread-id`, `ledger.md`, pin and round files.
- The gate scratch root holds the shared round state. Before the shared round's first reviewer call, write
  `round-NN-state` (the scoped diff or snapshot hash; it is also that round's stall-rule save) and the
  before-fingerprints, `round-NN-tree-before` (plus the `-doc-` pair); `round-NN-tree-after` follows when all
  responses are in. The fingerprints are taken with the commands of `references/adapter-orca.md`, "What Orca
  does not provide", in and outside Orca.
- `NN` at the root numbers the shared round; each reviewer's ledger records its own round file for each shared
  round. A retry in a new scratch follows `references/ledger.md`.
- `gates.md` names every reviewer scratch of this gate, with its pin and thread file, so a resumed coordinator finds
  them all.
- Each reviewer has its own thread, its own frozen discovery list and its own ledger. Finding ids carry the
  reviewer's finding prefix from `references/reviewer-choice.md`, followed by the number. Known task-review items
  from SDD go to every discovery, and each reviewer's decision on them is kept in its own ledger.

## Rounds

- Every round is a shared round over one recorded state: `round-NN-state` and the fingerprints. Every reviewer gets
  that same state; nothing is edited until all responses of the round are in.
- A round counts only when all responses are in and the after-fingerprints match the before-fingerprints. A
  mismatch voids every response of the round. A verdict counts only for the state it covered. A voided round, for
  this or any other reason below, is handled as a fingerprint mismatch in `references/adapter-orca.md` (outside git,
  name the changed scope paths), in headless runs too. Before the next shared round, every attempt of the voided
  round settles: a `worker_done` or a stop confirmed as `references/adapter-orca.md` requires (headless: the process
  has ended); a reviewer whose previous attempt may still run is never started. A voided discovery freezes no list:
  every reviewer runs discovery again on the next recorded state. A voided verification keeps the last counted
  lists: every reviewer verifies the next recorded state in its same thread.
- Each reviewer's ledger records which rounds counted and marks a voided round as voided, whatever its adapter
  already wrote to `last-review.txt`. The ledger, not that file, is what triage and the report read.
- Triage applies its normal rules to every finding of every list: check the premise, fix, reject with proof, or
  escalate. When findings of several reviewers lead to the same fix, the fix is made once and each reviewer gets the
  response line for its own finding. Contradicting findings are triaged the same way; none wins by default.
- One round message per round covers every reviewer; its header names them all.
- Then every reviewer verifies in its own thread on the new state. For each reviewer, every edit made for the
  findings of every other reviewer is disclosed with the block "ADDITIONAL EDIT, not raised by you" of the
  verification framework (`references/prompts.md`). A reviewer whose list is already closed verifies every later
  state too, until the gate closes.
- The gate closes when, on the same final state, each reviewer has either a clean discovery with no edits after it
  or `VERDICT: ALL RESOLVED`, and no ledger has an open line (known-item decisions included); for code and config
  gates the checks run on that state as well.
- A run that did not happen for a reviewer is rerun for that reviewer only, on the same recorded state; the
  responses of every other reviewer of that round stand. Before the retry, compare the current scoped diff or
  snapshot hash with `round-NN-state`; a difference voids the round.
- Stall rules apply to each reviewer's list, counted only over rounds where that reviewer had open lines.
  Escalation rules are unchanged.

## Orca

- The reviewer workers of a round run at the same time; there are no writing workers during the round, and one
  fingerprint pair covers them all.
- A Kimi or Gemini terminal of a gate is closed when the gate ends, as `references/adapter-reviewer-kimi.md`,
  "Orca", and `references/adapter-reviewer-gemini.md`, "Gate end", say.

## Final report

Under the table: every reviewer, each with its pin per gate (one line when no pin changed between gates). Each row
shows whose finding it was.
