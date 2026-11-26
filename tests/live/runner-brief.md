# Live check kit: runner brief

You run live cases of the `ship` skill (a cross-vendor review loop for coding agents) in a throwaway sandbox
repository. You start agent CLIs there, give them a ship task, answer as the case says, and record what happened
against the case's assertions. You do not edit ship and do not judge its design: you report observed behaviour with
evidence. Your cases are in `cases.md`, your launch rows in `runtimes.md`, both next to this file.

## Parameters

The coordinator gives you these; nothing else is assumed.

- `B`: the build under test, read-only (its skill text: `$B/skills/ship/SKILL.md` and `$B/skills/ship/references/`).
  Read `SKILL.md` and the reviewer-choice reference once before your first case, so you know what a run should do.
- `SB`: the sandbox, made by `make-sandbox.sh`; `BASE`: the base SHA it printed.
- `E`: the evidence root, one directory per case id.
- `SEL`: the sandbox's Orca worktree selector.
- The batch: its case ids, the launch rows from `runtimes.md` they use, the resolved model ids, for H and I2 the
  mutant the coordinator loaded, and for D3 the baseline export `B0`.
- The build proof the coordinator ran for this batch's runtime (`runtimes.md`, "Loading").

## Roles

The coordinator loads builds, changes and restores every configuration, and registers the sandbox in Orca. You never
install, uninstall, enable or disable a plugin, never edit any CLI's configuration or trust settings, and never
register or hide an Orca repository. If a case needs one of these, it is NOT RUN with the reason.

A prompt that would change configuration (a trust prompt for any folder, an update prompt, a plugin prompt) is not
yours to answer: record the screen, the folder and the terminal handle, leave the case running, and end your turn with
`PAUSED: <prompt> in <terminal handle>`. The coordinator answers it and tells you to continue.

## Before each case

1. The sandbox is marked and clean: `cat "$SB/.ship-live-sandbox"` prints `BASE`, `git -C "$SB" rev-parse HEAD` is
   `BASE`, `git -C "$SB" status --porcelain` is empty, `$SB/.ship`, `$SB/.superpowers` and `$SB/.git/ship-routes` are
   absent, and the branches are as at `BASE`: `git -C "$SB" for-each-ref --format='%(refname:short) %(objectname)'
   refs/heads` prints one line, the sandbox's own branch at `BASE`, and `git -C "$SB" symbolic-ref -q --short HEAD`
   prints that branch. Otherwise stop the batch and report: never reset a directory that is not marked.
2. Record what exists before the case, into `$E/<case>/before.txt`: the handles of `orca terminal list --json`, the
   dispatch ids of `orca orchestration worker-list --json`, `orca worktree list --json` for the sandbox repository,
   `git -C "$SB" worktree list`, the branch names of `git -C "$SB" for-each-ref --format='%(refname:short)'
   refs/heads` and `git -C "$SB" symbolic-ref -q --short HEAD` (short names, as step 3 of "After each case" uses
   them), and the ids of running `claude`, `codex`, `kimi` and `agy` processes (`ps -axo pid=,comm=`, ids and names
   only). Everything new after the case starts is the case's own if it is in the sandbox, in its worktrees or in a
   directory the executor's transcript shows it creating for a reviewer; anything else is not touched and is
   reported.
3. The PATH precondition, for a case that hides a binary (`runtimes.md`, "PATH without a binary"):
   - Interactive: after the executor starts and before the task, ask it to run
     `for b in claude codex kimi agy; do command -v "$b" || echo "$b: ABSENT"; done` and record the output in
     `$E/<case>/path-check.txt`. Every hidden binary absent and the executor's own and every remaining reviewer
     binary present, or the case is NOT RUN.
   - Print mode (Claude Code print mode, `codex exec`): only the case where one reviewer stays available hides
     binaries, because there ship's own resolution probes every roster binary. The run records its events
     (`runtimes.md`, "Launch variants"); the proof is that probe's `command -v` output in the events. Without it the
     case is NOT RUN.

## During a run

- Start as the launch row says; wait with `orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000
  --json` before the first input. Send text with `orca terminal send --terminal <handle> --text <text> --enter
  --json`, keys as escapes (`$'\x1b'` Escape, `$'\x1b[A'` / `$'\x1b[B'` arrows, space to toggle, `$'\x03'` Ctrl-C).
  Read with `orca terminal read --terminal <handle> --screen --json`. Run `--help` on a subcommand before a flag you
  are unsure of.
- Record the announcement ("Using ship: …" in the task's language) verbatim. Record any reviewer question exactly
  before answering it: its form (question tool, `ask_question`, plain text), entries, order, markers, and the last
  lines that follow it.
- If the executor asks anything the case does not script (route, scope), answer briefly so the case proceeds as
  written ("one-off route", "yes, proceed"). Never approve anything outside the sandbox.
- Wait in stretches of up to 10 minutes with `terminal wait --for tui-idle` and read the screen between them. In Orca
  the executor ends its turn while it waits for a worker; the run is over only at its final report, a blocker, or the
  case's stop point. After 25 minutes with no change on screen and no live worker of the case, record the screen and
  report the case as stalled.
- Save evidence as you go under `$E/<case>/`: `menu.txt`, `announcement.txt`, `final.txt`, the events file, the
  receipts of the case's workers (`orca orchestration worker-list --json`, filtered to them), and extracts of the
  executor's transcript (`runtimes.md`, "Transcripts") with the lines each assertion rests on.

## Build proof, every case

Record in `$E/<case>/build-proof.txt`: the coordinator's `diff -r` result for this runtime, the path of the `SKILL.md`
the executor loaded, and one executor file it read, both from its transcript or events. On the baseline the executor
file is its adapter or card under `references/`; on a later build a card under `references/agents/`. In an interactive
session also ask at the end, "Print the absolute path of the ship SKILL.md you loaded", and record the answer. A
loaded path outside the row's "Loaded `SKILL.md`" fails the case.

For an Antigravity executor, before the task type `/ship:sh` without Enter and record the completion screen in
`$E/<case>/slash-probe.txt`; it must show `/ship:ship`. Then clear the input (Escape, then Ctrl-U) and send the task.
No `/ship:ship` completion: the case is NOT RUN, because an executor without the registered skill can still find
`SKILL.md` on disk and look as if it ran ship. The `SKILL.md` path the session reports must be the row's "Loaded
`SKILL.md`".

## After each case, pass or fail

1. Settle what the case owns, and only that. Stop each of its live workers (`orca orchestration worker-stop
   --dispatch <id> --json`) and close each of its terminals, the executor's included, with `orca terminal close
   --terminal <handle> --json`. A terminal is gone only with `close.ptyKilled: true`, or when its handle is missing
   from `orca terminal list --json` with `truncated: false`; liveness `exited` or `lost` alone proves nothing. An
   interactive Codex session outlives its closed terminal (Codex 0.172.0 runs its thread in a shared app-server): in a
   terminal in the sandbox start `codex resume <its thread id>`, press Escape to end its running turn, prove from its
   rollout (`runtimes.md`, "Transcripts") that the turn ended, and close that terminal too, all before step 2. A
   QUIT-ON-LINE watcher still running (its PID in `$E/<case>/quit.pid`) is stopped with `kill <pid>` and proven gone
   with `ps -p <pid>`, also before step 2. Every process the case owns has ended: wait up to 10 minutes, then stop it
   with `kill <pid>` and prove it gone with `ps -p <pid>`. Record all of it in `$E/<case>/cleanup.txt`.
2. Copy `$SB/.ship`, `$SB/.superpowers` and `$SB/.git/ship-routes` (those present) into `$E/<case>/`, with each route
   root outside `$SB` that a pointer in `$SB/.git/ship-routes/` names, and write
   `git -C "$SB" log --oneline "$BASE"..HEAD`, `git -C "$SB" status --porcelain` and `git -C "$SB" diff "$BASE"` to
   `$E/<case>/sandbox-state.txt`.
3. Remove only the worktrees the case created: `orca worktree rm --worktree <selector> --delete-branch --json` for
   Orca's (`orca worktree create` made a branch for each), `git -C "$SB" worktree remove <path>` for the others, then
   `git -C "$SB" worktree prune`. Then delete the branches the case created, so the next case does not meet them:
   every branch that `before.txt` does not list, with `git -C "$SB" branch -D <name>`; if the sandbox's `HEAD` is on
   one of them, first `git -C "$SB" checkout -q -f <the branch before.txt records>`. This sweep also takes a branch
   that `--delete-branch` kept. Record the removals and deletions in `$E/<case>/cleanup.txt`.
4. Reset, only while `cat "$SB/.ship-live-sandbox"` still prints `BASE`:
   `git -C "$SB" reset -q --hard "$BASE" && git -C "$SB" clean -fdq && rm -rf "$SB/.ship" "$SB/.superpowers"
   "$SB/.git/ship-routes"`. Never `git clean -x`: it would delete the ignored `.claude/` and `.agents/` setup.
5. Write `$E/<case>/result.md`: the case id and title; PASS, FAIL or NOT RUN; the run conditions (start and end
   times, the CLI versions, the executor's model and every reviewer's model from receipts and transcripts); one row
   per assertion with the observed value and the evidence file; anything surprising.

## Hard rules

- Never print the environment: no bare `env`, `export`, `set` or `printenv`; only `env -u VAR cmd`, `env PATH=… cmd`
  and single named variables.
- Never print the output of `kimi provider list --json` (it carries credentials) and never read credential files.
- Never run `agy plugin import`.
- No install, no configuration edit, no repository registration (see "Roles"); never touch any ship checkout or
  worktree other than reading `B`.
- No git push and no remote operation.
- No subagents of your own.
- Keep every script and temp file in a scratch directory of your own (named after your batch); other runners may run
  in other sandboxes at the same time, and their files, terminals and processes are not yours.
- One case at a time: cases that share a sandbox or a plugin cache never overlap.
- A case that cannot run for an external reason (a CLI not logged in, a quota, a missing prerequisite): NOT RUN with
  the evidence, then the next case. NOT RUN never counts as a pass.

## Your report

One line per case, `<id> — PASS | FAIL | NOT RUN | PAUSED — <the key observation>`, then a short list of what looks
like a ship defect, with its evidence path. Nothing else.
