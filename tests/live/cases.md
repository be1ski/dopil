# Live check kit: cases

Each `###` instance is one case for `runner-brief.md`. Its first line names the executor (a variant of `runtimes.md`),
the reviewers and where it runs; its `Request:` lines name what you type. `baseline` instances run on every build,
the baseline included, which is an earlier dopil export (`runtimes.md`, "Building an export"), as D3's `B0`;
`after-only` instances need what only a later build has. Assertions are about behaviour, so they hold on every dopil
build; a value marked "record" is compared with the baseline, not with this file. The previous plugin's layout appears
only in group M. Every instance also records the build proof of `runner-brief.md`.

## Inputs

Every text a case types is defined here, so every run types the same strings. A `Request: <name> + <name>` line is
typed as the variant's invocation with `<task>` replaced by those texts in order, joined by one space: in Claude Code,
`Request: T1 + BY-CODEX` is `/dopil In wc/count.py, when … add a test for it. Review by codex.` A `Request (<when>):`
line says which session or half it belongs to. FIX, STOP and NEXT are typed alone, at the point the case names.

| Name | Text |
|---|---|
| T1 | `In wc/count.py, when no file argument is given, print a usage line to stderr and exit with status 2; add a test for it.` |
| T2 | `Add a --json flag to wc/count.py that prints the three counts as a JSON object {"lines": …, "words": …, "chars": …} instead of the plain line; keep the plain output as the default; tests for both. Full route: spec, plan, code.` |
| RC | `Take the uncommitted change in wc/count.py through the code gate as it is, without editing it first, then fix what the review finds. It must print "usage: count.py FILE" to stderr and exit with status 2 when no file argument is given.` |
| RF | `Review only the spec docs/usage.md, without implementing it.` |
| RESUME | `continue the dopil route in this repository` |
| BY-CODEX | `Review by codex.` |
| BY-CLAUDE | `Review by claude.` |
| BY-KIMI | `Review by kimi.` |
| BY-CODEX-KIMI | `Review by codex and kimi.` |
| PAR-CODEX | `Codex in parallel.` |
| PAR-KIMI | `Kimi in parallel.` |
| FIX | `Before you accept this task, ask its writer for one small follow-up: rename any name that is unclear; if nothing is unclear, have it reply that nothing changed.` |
| STOP | `Stop the work now.` |
| NEXT | `What now?` |
| ALL | `all at once` |

An `Answer:` is typed exactly as written in a plain-text dialog (a key such as `codex`, or ALL). In a question tool it
selects that reviewer's entry, or the All at once entry for ALL, unless the instance says to type it into the
tool's free-text entry.

RC follows P, and RF follows PF.

P, the planted code defect (stdout and exit status 0 instead of stderr and 2, no test), uncommitted:

```bash
python3 -I - "$SB/wc/count.py" <<'PY'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
old = "    argv = sys.argv[1:] if argv is None else argv\n"
assert text.count(old) == 1
new = old + '    if not argv:\n        print("usage: count.py FILE")\n        return\n'
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
```

PF, the planted spec defect (its two paragraphs contradict each other), untracked:

```bash
mkdir "$SB/docs" && cat > "$SB/docs/usage.md" <<'MD'
# Usage error

When `wc/count.py` runs without a file argument, it prints `usage: count.py FILE` to stderr and exits with status 2.

A test in `tests/test_count.py` runs the script without arguments and asserts exit status 1 and the usage line on
stdout.
MD
```

QUIT-ON-LINE, for cases that end a session as soon as the reviewer set is recorded and before any dispatch, started
in the background right after the request is sent:

```bash
bash -c 'sb=$0 handle=$1 line="^([-*][[:space:]]+)?(\*\*)?Reviewers(\*\*)?:"
recorded() {
  grep -Eqs "$line" "$sb"/.dopil/*/gates.md && return
  for pointer in "$sb"/.git/dopil-routes/*.txt; do
    grep -Eqs "$line" "$(head -n 1 "$pointer" 2>/dev/null)/gates.md" && return
  done
  return 1
}
until recorded; do
  [ "$SECONDS" -lt 1800 ] || { echo "QUIT-ON-LINE: no Reviewers line after 30 minutes, terminal left open"; exit 1; }
  sleep 1
done
orca terminal close --terminal "$handle" --json' "$SB" "<handle>" > "$E/<case>/quit.json" 2>&1 &
echo "$!" > "$E/<case>/quit.pid"
```

It reads `gates.md` under `$SB/.dopil` and under each route root a pointer in `$SB/.git/dopil-routes/` names, and takes
the line bare, as a list item or bold. It closes the session's terminal: `close.ptyKilled: true` in `quit.json` is
the proof. After 30 minutes without the line it stops, leaves the terminal open and says so in `quit.json`. Its PID
is in `quit.pid` for the runner's cleanup. Record `gates.md` and whether anything was dispatched; the next session
starts in a new terminal.

## Menus

The reviewer dialog each executor shows, by scratch key. In every form: the default first where the executor has
one, "All at once" last, labels recorded verbatim, and no route step before the set is resolved (no edit in the
sandbox, no reviewer process, worker or gate round).

| Executor | Form | Entries, in order |
|---|---|---|
| Claude Code | its question tool, multi-select; the answer continues the same turn | `codex`, `kimi`, All at once |
| Codex | plain text, numbered, ending with how to name reviewers in a `$dopil` request; the turn ends | `claude`, `kimi`, All at once |
| Kimi Code under `--auto` | plain text, numbered, ending with how to name reviewers in a `/skill:dopil:dopil` request; the turn ends | `codex`, `claude`, All at once |
| Antigravity on a Gemini model | `ask_question`, multi-select, in this order, no "(Recommended)" | `codex`, `claude`, `kimi`, All at once |
| Antigravity on a non-Gemini model | the same | every reviewer of another vendor than the model's, in the order `codex`, `claude`, `kimi` (a `claude-` model: `codex`, `kimi`), All at once |

## Continuity

A verification continues the discovery's thread, by transport:

- headless: the pinned session, thread or conversation id in the gate scratch (`thread-id`) unchanged from discovery
  through every verification, and each verification command resumes that id;
- Orca standard worker: each verification receipt has `delivery` `reopened` or `follow_up`, and the worker's
  transcript holds the earlier round;
- kept terminal: the same terminal handle and the same conversation or session id for every round.

## Group A: the dialog and a one-off route, per launch variant

Steps: start the variant; send the request; answer as the instance says; run to the final report.

Assert: the dialog as "Menus" says; the announcement names the set (record verbatim); `gates.md` holds `Reviewers:
<set>`; every gate is reviewed by every reviewer in the set, each verification continuous; outside Orca the reviewers
run headless and no Orca worker exists; in Orca one receipt per reviewer and round (agent, model, effort, its
terminal in the sandbox), every edit by the executor's writing workers (their receipts' agent and model; for
Antigravity, its own `invoke_subagent` subagents, with no Orca worker running `agy`) and none by the main agent, the
executor waking by itself on every `worker_done` with no keystroke from you, every reviewer and writer worker of the
route ended by its card's closing procedure or by Orca's release of a settled worker, and a plain shell that `orca
worktree create` opened recorded, not asserted; the final report names each gate's reviewers with their pins, the
executor's vendor and model family, and the polish delta or its absence.

### A-claude-one · baseline

Executor: Claude Code · Reviewers: codex · outside Orca. Answer: `codex` only.
Request: T1

### A-claude-all · baseline

Executor: Claude Code · Reviewers: codex, kimi · in Orca. Answer: ALL.
Request: T1

### A-codex-one · baseline

Executor: Codex · Reviewers: claude · outside Orca. Answer: `claude`. Also: the question is on screen as plain text,
not inside a question tool, and nothing (a test, a fix) is written before the answer.
Request: T1

### A-codex-all · baseline

Executor: Codex · Reviewers: claude, kimi · in Orca. Answer: ALL. The plain-text check of A-codex-one.
Request: T1

### A-kimi-one · baseline

Executor: Kimi Code · Reviewers: codex · outside Orca. Answer: `codex`. Also: the identity result (`ALIAS`,
`PROVIDER TYPE: kimi`, vendor Moonshot AI) before the dialog; the plain-text question ends with the example
`/skill:dopil:dopil <task> with codex and claude`.
Request: T1

### A-kimi-all · baseline

Executor: Kimi Code · Reviewers: codex, claude · in Orca. Answer: ALL. Also: each writer in a terminal the
executor created with its pinned `kimi --auto -m <alias>` launch and started by `worker-start --terminal`, never
`worker-start --agent kimi`.
Request: T1

### A-agy-gemini-one · baseline

Executor: Antigravity on a Gemini model · Reviewers: codex · outside Orca. Answer: `codex`. Also: the identity result
(`MODEL`, `VENDOR: Google`) before the dialog.
Request: T1

### A-agy-gemini-all · baseline

Executor: Antigravity on a Gemini model · Reviewers: codex, claude, kimi · in Orca. Answer: ALL.
Request: T1

### A-agy-other-one · baseline

Executor: Antigravity on a non-Gemini model · Reviewers: the first entry · outside Orca. Answer: the first entry.
Also: the identity result names the model's vendor; every skill file is read with `read_file` and whole (no skill
file through `cat`; a partial read continued to its end).
Request: T1

### A-agy-other-all · baseline

Executor: Antigravity on a non-Gemini model · Reviewers: every entry · in Orca. Answer: ALL. The read check of
A-agy-other-one.
Request: T1

## Group B: a named reviewer, per executor with a default

Steps: in Orca, send the request; stop at the named reviewer's first discovery receipt.

Assert: no dialog and no reviewer question; `gates.md` holds `Reviewers: <key>`; one receipt of that reviewer.

### B-claude · baseline

Executor: Claude Code · Reviewers: codex · in Orca.
Request: T1 + BY-CODEX

### B-codex · baseline

Executor: Codex · Reviewers: claude · in Orca.
Request: T1 + BY-CLAUDE

## Group C: runs that cannot take an answer

Steps: the variant's print mode, its events recorded (`runtimes.md`). A `-one` instance stops after the first
discovery's result is saved in the gate scratch: stop the process and prove it gone.

### C-claude-one · baseline

Executor: Claude Code · Reviewers: codex · print mode, `PATH` without `kimi`. Assert: dopil's own probe in the
events finds no `kimi`; no question; `Reviewers: codex`; the Codex discovery ran headless, with its thread id and
review in the gate scratch.
Request: T1

### C-claude-several · baseline

Executor: Claude Code · Reviewers: none · print mode. Assert: the numbered plain-text question is the last output,
followed by how to name reviewers in the request with one `/dopil` example line; nothing dispatched (no reviewer
process, no gate round); no tracked file changed.
Request: T1

### C-claude-parallel · baseline

Executor: Claude Code · Reviewers: as resolved · print mode, then interactive outside Orca. Run (a), print mode,
stopped once every reviewer's first discovery started: record the resolution (the baseline's text: no default, so the
companion is the one remaining reviewer `codex`, no question). Then settle and reset as `runner-brief.md`, "After each
case", steps 1–4 say, and check the sandbox as "Before each case" says, so run (b) also starts from `BASE`; each run's
evidence goes under `$E/<case>/a/` or `$E/<case>/b/`. Run (b), interactive, stopped once every reviewer's first
discovery started: record the resolution (the baseline's text: `kimi` plus the default `codex`, no question). Assert:
each run's resolution, question entries and dispatches as recorded on the baseline.
Request (both runs): T1 + PAR-KIMI

### C-codex-one · baseline

Executor: Codex · Reviewers: claude · print mode, `PATH` without `kimi`, with Codex's `PATH` flags. Assert: dopil's
own probe in the events finds no `kimi`; no question; `Reviewers: claude`; the Claude Code discovery ran headless,
with its session id and review in the gate scratch.
Request: T1

### C-codex-several · baseline

Executor: Codex · Reviewers: none · print mode. Assert: the numbered plain-text question is the last output,
followed by how to name reviewers in the request with one `$dopil` example line; nothing dispatched; no tracked file
changed.
Request: T1

### C-codex-parallel · baseline

Executor: Codex · Reviewers: as resolved · print mode, then interactive outside Orca. Run (a), `codex exec`: record
the resolution (the baseline's text: Codex cannot tell `codex exec` from an interactive session, so it resolves as
run (b)). Then settle and reset as `runner-brief.md`, "After each case", steps 1–4 say, and check the sandbox as
"Before each case" says, so run (b) also starts from `BASE`; each run's evidence goes under `$E/<case>/a/` or
`$E/<case>/b/`. Run (b), interactive, stopped once every reviewer's first discovery started: record the resolution (the
baseline's text: `kimi` plus the default `claude`, no question). Assert: each run's resolution, question entries and
dispatches as recorded on the baseline.
Request (both runs): T1 + PAR-KIMI

## Group D: resume

Steps: in Orca; stop at the first discovery receipt after the resume.

### D-line · baseline

Executor: Claude Code · Reviewers: codex · in Orca. Session 1: answer `codex`, QUIT-ON-LINE. Session 2, in a new
terminal. Assert: session 1 recorded `Reviewers: codex` and dispatched nothing; session 2 shows no dialog and no
reviewer question, keeps the line unchanged, and dispatches the first gate's discovery to `codex`. Record how
session 2 recovers the request text.
Request (session 1): T2
Request (session 2): RESUME

### D-legacy · baseline

Executor: Claude Code · Reviewers: codex · in Orca. Before the start, write a registry from before the `Reviewers:`
line:

```bash
python3 -I - "$SB" "$(git -C "$SB" rev-parse --path-format=absolute --git-common-dir)" <<'PY'
import os, sys
sb, common = sys.argv[1:]
root = os.path.join(sb, ".dopil", "2026-11-01-usage")
os.makedirs(os.path.join(root, "spec-01"))
os.makedirs(os.path.join(common, "dopil-routes"))
files = {
    os.path.join(sb, ".dopil", ".gitignore"): "*\n",
    os.path.join(root, "gates.md"): (
        "# dopil route 2026-11-01-usage: wc/count.py usage error\n\n"
        "Route: full (spec → plan → code → polish). Executor: Claude Code.\n"
        "Reviewer: codex (default)\n\n"
        "| Gate | Scope | Scratch | State | Proof |\n|---|---|---|---|---|\n"
        "| spec-01 | file: %s/spec.md | %s/spec-01 | closed (2 rounds, codex) | codex VERDICT: ALL RESOLVED |\n"
        % (root, root)),
    os.path.join(root, "spec.md"): (
        "# wc/count.py: usage error without a file argument\n\n"
        "When `wc/count.py` is run without a file argument, it prints a single usage line, `usage: count.py FILE`, "
        "to stderr and exits with status 2. Nothing is written to stdout in that case, and the behaviour with a file "
        "argument stays as it is.\n\n"
        "A unit test in `tests/test_count.py` runs the script with no arguments and asserts the exit status 2, an "
        "empty stdout and a stderr that starts with `usage:`. `python3 -m unittest discover -s tests` is the check.\n"),
    os.path.join(common, "dopil-routes", "2026-11-01-usage.txt"): root + "\n",
}
for path, text in files.items():
    with open(path, "x", encoding="utf-8") as f:
        f.write(text)
PY
```

Assert: no dialog and no question; the set `codex` taken from the header; `Reviewers: codex` written before the
first dispatch; the next gate's discovery goes to `codex`.
Request: RESUME

## Group D3: a gate opened on an earlier dopil build, resumed on the later build

Two paired runs. `B0` is an earlier dopil export (`runtimes.md`, "Building an export") whose source SHA the
coordinator records with the run; until two dopil builds exist, D3 is not run. Steps: create the terminal with no
command (`orca terminal create --worktree "$SEL" --title "live <case>" --json`) and record its handle; type the start
with `--plugin-dir $B0`; apply P and send the earlier half's request; as soon as the code gate's `ledger.md`
holds a finding line, quit the executor with Ctrl-C twice, before any verification starts (a verification already
started: the pair is rerun), and prove the process ended, leaving the tree, the scratch, `.git/dopil-routes`, the
reviewer's thread and any reviewer terminal in place; record `gates.md`, the ledger and `thread-id`; in the same
terminal type the start with `--plugin-dir $B`, wait for it, send the later half's request; stop when the code gate
is closed. Settle and reset only after the pair has settled.

Assert: the same terminal handle in both halves; after the resume no dialog and no reviewer question, the
`Reviewers:` line unchanged, the gate's row keeping its scope, scratch and reviewers while its State and Proof
advance, no new discovery for the open gate, its verification in the original thread as "Continuity" says for the
transport, the planted finding resolved and the gate closed by `VERDICT: ALL RESOLVED`; the build proof of each half
(a card under `references/agents/` of `B0`, then of `B`).

### D3-headless · after-only

Executor: Claude Code · Reviewers: codex · outside Orca (both starts prefixed).
Request (earlier half): RC + BY-CODEX
Request (later half): RESUME

### D3-kept · after-only

Executor: Claude Code · Reviewers: kimi · in Orca. Also: the Kimi reviewer's terminal handle and session id recorded
before the quit are the ones the verification uses, with a `delivery: follow_up` receipt.
Request (earlier half): RC + BY-KIMI
Request (later half): RESUME

## Group M: an old route migrated on resume

A sandbox copy of an old route: the previous plugin's route as its build 574afe1 left it, a closed spec gate and an
open code gate, resumed by the build under test.

Setup, by the runner, in this order:

1. Its own one-shot sandbox: `bash <this directory>/make-sandbox.sh <a fresh path> "$B" <superpowers>`, where
   `<superpowers>` is the `installPath` that `claude plugin list --json` gives for superpowers. `MSB` is that
   sandbox's physical path (`pwd -P` inside it) and `MBASE` the SHA the script printed: a pair of its own beside the
   kit's `SB` and `BASE`, which stay as they are. `MSB` equal to `SB`: the case is NOT RUN.
2. In `$MSB/.claude/settings.json`, the sandbox's own file, add to `enabledPlugins` a `false` entry for every plugin
   `claude plugin list --json`, run in `$MSB`, lists, except superpowers (the route needs it), the `@builtin` ones and
   those of scope `session`. The same list, run again, goes into `$E/M-claude/plugins.json`: each plugin turned off
   shows `enabled: false`, superpowers `enabled: true`; any other value makes the case NOT RUN, with that listing kept.
3. "Before each case" of `runner-brief.md`, against this sandbox, with `MSB` and `MBASE` in place of `SB` and `BASE`.
4. Apply P, committed nowhere, then write the old layout: `.ship/.gitignore` holding the single line `*`; the route's
   `gates.md` with `Reviewers: codex`, a closed file gate `spec-01` over a one-line spec in the scratch and an open git
   gate `code-01`, both Scratch cells absolute paths under `$MSB/.ship/2026-11-20-usage/`; `code-01`'s `base-sha`
   (`MBASE`), `ledger.md` (the first line with the scope, the working directory and the base, then one open finding
   naming P) and `thread-id` (a thread that does not exist); the pointer `.git/ship-routes/2026-11-20-usage.txt`. The
   block reads the sandbox's git paths with the five variables that point git elsewhere removed, stops on a failing
   git command, and writes nothing unless the git dir is `$MSB/.git`, the one of this standalone sandbox:

```bash
python3 -I - "${MSB:?}" <<'PY'
import os, subprocess, sys
sb = sys.argv[1]
if not (os.path.isabs(sb) and os.path.isfile(os.path.join(sb, ".dopil-live-sandbox"))):
    sys.exit("refusing %r: not the absolute path of a marked sandbox; nothing written" % sb)
env = {k: v for k, v in os.environ.items()
       if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR")}
def git(*args):
    return subprocess.run(["git", "-C", sb] + list(args), env=env, check=True, stdout=subprocess.PIPE,
                          universal_newlines=True).stdout.strip()
base = git("rev-parse", "HEAD")
common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
if common != os.path.join(sb, ".git"):
    sys.exit("refusing %r: its git dir is %s, not its own .git; nothing written" % (sb, common))
root = os.path.join(sb, ".ship", "2026-11-20-usage")
spec, code = os.path.join(root, "spec-01"), os.path.join(root, "code-01")
scope = "git diff %s -- wc/count.py tests/test_count.py" % base
os.makedirs(spec)
os.makedirs(code)
os.makedirs(os.path.join(common, "ship-routes"))
files = {
    os.path.join(sb, ".ship", ".gitignore"): "*\n",
    os.path.join(root, "gates.md"): (
        "# Route 2026-11-20-usage: wc/count.py usage error\n\n"
        "Reviewers: codex\n\n"
        "| Gate | Scope | Scratch | State | Proof |\n|---|---|---|---|---|\n"
        "| spec-01 | file: %s/spec.md | %s | closed (1 round, codex) | codex VERDICT: ALL RESOLVED |\n"
        "| code-01 | %s | %s | open (codex) | - |\n" % (root, spec, scope, code)),
    os.path.join(root, "spec.md"): (
        "Without a file argument, `wc/count.py` prints `usage: count.py FILE` to stderr and exits with status 2, "
        "and a test in `tests/test_count.py` covers it.\n"),
    os.path.join(code, "base-sha"): base + "\n",
    os.path.join(code, "ledger.md"): (
        "Scope: %s. Working directory: %s. Base: %s.\n"
        "#1 · 01 · \"main() prints the usage line to stdout and returns with status 0 when no file argument is "
        "given; stderr and status 2 are asked, and no test covers it\" · open · %s\n" % (scope, sb, base, scope)),
    os.path.join(code, "thread-id"): "00000000-0000-7000-8000-000000000000\n",
    os.path.join(common, "ship-routes", "2026-11-20-usage.txt"): root + "\n",
}
for path, text in files.items():
    with open(path, "x", encoding="utf-8") as f:
        f.write(text)
PY
```

5. From `$MSB`, `python3 -I "$B/skills/dopil/references/migrate.py" check` into `$E/M-claude/check.txt` with its exit
   status: exit 1, a `MOVE` line each for the route, its pointer and `$MSB/.ship`, and `RESTART-LATER <gates.md>:
   code-01`. Otherwise the case is NOT RUN, with that output.

Steps: start outside Orca from the kit's worktree into this sandbox, `orca terminal create --worktree "$SEL" --title
"live M-claude" --command "cd <MSB> && env -u ORCA_TERMINAL_HANDLE claude --plugin-dir $B
--dangerously-skip-permissions" --json`; type the request as the descriptor's Invocation (as the coordinator's L1
check proved it); answer the migration question with its entry that confirms no session of the previous plugin runs
(in plain text: `No session of the previous plugin runs.`); as soon as `RESTART code-01 -> code-02` appears, copy
`$MSB/.dopil/2026-11-20-usage/gates.md` to `$E/M-claude/gates-at-restart.md` (watch the transcript, `runtimes.md`,
"Transcripts", between the waits), before the gate's State moves on; stop when `code-02` is closed. "After each case"
of `runner-brief.md` covers both layouts, `$MSB/.ship` and `$MSB/.git/ship-routes` as well as the new ones, runs its
git commands in the clean context of the setup block, and deletes the sandbox.

Assert: the build proof, with the loaded `SKILL.md` at `$B/skills/dopil/SKILL.md`; the migration question once, after
`check` and before `run`, both by that skill's `references/migrate.py`; after `run`, `$MSB/.ship` and
`$MSB/.git/ship-routes` gone, the route under `$MSB/.dopil/2026-11-20-usage/` and the pointer
`$MSB/.git/dopil-routes/2026-11-20-usage.txt` holding that path; in `gates.md`, the `spec-01` row closed and unchanged
apart from the new prefix, and the marker line `Migrated <date>: restart on resume: code-01`; `code-01` superseded
(`code-01 restarts as code-02`, its row `closed: superseded by code-02 (migration)`, the line `code-01 superseded by
code-02`); in `gates-at-restart.md`, the row `code-02` `open (restarted from code-01…)`; `#1` in
`code-02/codex/known-items.md`, `code-02/base-sha` equal to `MBASE`, and `code-02` with a discovery of its own (not
the fixture's `thread-id`); the reviewer's
decision on `#1` in that discovery, kept in `code-02`'s ledger: CONFIRMED, then fixed and verified, or, when the
executor fixed P before that discovery, NOT A DEFECT with the fix inside the reviewed diff; `code-02` closed over the
old base by the normal exit condition, zero discovery findings or `VERDICT: ALL RESOLVED`. Recorded, not asserted:
whether a message after `run` naming what moved and the gates that restart appears as assistant text, verbatim where
it does, as the announcement is recorded (Claude Code often keeps such a message in its thinking).

### M-claude · after-only

Executor: Claude Code · Reviewers: codex · outside Orca, in its own sandbox.
Request: RESUME

## Group E: dialog answers

Steps: in Orca unless the instance says otherwise; send the request; answer as the instance says; stop at the first
discovery receipt of every chosen reviewer.

### E-claude-one-available · baseline

Executor: Claude Code · Reviewers: codex · in Orca, `PATH` without `kimi`. Assert: no dialog; the
announcement names `codex`; `Reviewers: codex`; one Codex receipt.
Request: T1

### E-claude-cancel · baseline

Executor: Claude Code · Reviewers: none · in Orca. Answer: cancel the question tool (Escape), then type NEXT. Assert:
nothing dispatched and no route step; record what the executor says in that turn and in reply to NEXT (the
baseline's text: how to name reviewers in the request).
Request: T1

### E-agy-cancel · baseline

Executor: Antigravity on a Gemini model · Reviewers: none · in Orca. Answer: cancel `ask_question` (Escape), then type
NEXT. Assert as E-claude-cancel.
Request: T1

### E-claude-numbered · baseline

Executor: Claude Code · Reviewers: kimi · in Orca. Answer: `2` typed into the tool's free-text entry. Assert:
`Reviewers: kimi`; one Kimi receipt and no other reviewer.
Request: T1

### E-claude-all-except · baseline

Executor: Claude Code · Reviewers: codex · in Orca. Answer: `all except kimi` typed into the free-text entry.
Assert: `Reviewers: codex`; its receipt; no Kimi.
Request: T1

### E-kimi-companion · baseline

Executor: Kimi Code · Reviewers: codex, claude · in Orca. Assert: no companion question, since `claude` is the one
remaining reviewer; `Reviewers:` with `codex` and `claude`; both receipts. Record any announcement made before the
set is resolved.
Request: T1 + PAR-CODEX

### E-agy-companion · baseline

Executor: Antigravity on a Gemini model · Reviewers: kimi, codex · in Orca. Answer: `codex`. Assert: `ask_question`
with `codex`, `claude`, All at once (no `kimi`); `Reviewers:` with `kimi` and `codex`; both receipts.
Request: T1 + PAR-KIMI

### E-claude-none · baseline

Executor: Claude Code · Reviewers: none · in Orca, `PATH` without `codex` and `kimi`. Assert: the executor says
no reviewer is available and stops; no dialog, no dispatch, no route step.
Request: T1

## Group R: a reviewer card through one gate

Steps: apply P (or PF for RF); send the request; stop when the gate is closed.

Assert: the discovery reports the planted defect (the stdout and exit-status mismatch, or the spec's contradiction);
a verification runs as "Continuity" says for the transport; the finding is resolved and the gate closed by `VERDICT:
ALL RESOLVED`; the reviewer's pin (model, effort) and the round files in the gate scratch recorded.

### R-codex-headless-diff · baseline

Executor: Claude Code · Reviewers: codex · outside Orca. Also: the discovery is Codex's native diff review
(`codex exec review` in the transcript).
Request: RC + BY-CODEX

### R-codex-headless-file · baseline

Executor: Claude Code · Reviewers: codex · outside Orca. Also: a file-mode discovery in controlled text (its
`REVIEWED` and `CONTEXT` lists and the `VERDICT` line).
Request: RF + BY-CODEX

### R-codex-orca · baseline

Executor: Claude Code · Reviewers: codex · in Orca.
Request: RC + BY-CODEX

### R-claude-headless · baseline

Executor: Codex · Reviewers: claude · outside Orca.
Request: RC + BY-CLAUDE

### R-claude-orca · baseline

Executor: Codex · Reviewers: claude · in Orca.
Request: RC + BY-CLAUDE

### R-kimi-headless · baseline

Executor: Claude Code · Reviewers: kimi · outside Orca.
Request: RC + BY-KIMI

### R-kimi-orca · baseline

Executor: Claude Code · Reviewers: kimi · in Orca, a kept terminal.
Request: RC + BY-KIMI

## Group F: a full route with writers, per executor card

Steps for `F-<card>`: in Orca, send the request; at the first task writer's `worker_done`, before the executor
accepts the task, type FIX into the executor (Kimi Code queues text typed while it works: Ctrl-S steers it in); run
to the final report.

Assert: every edit by the executor's writing workers (their receipts' agent and model), none by the main agent; the
forced follow-up goes the card's way and completes (Claude Code, Codex: `send` to the writer's latest dispatch with
`delivery` `reopened` or `follow_up`, or `started_fresh` with a ledger line; Kimi Code: `terminal wait
--for tui-idle`, then `worker-start --terminal <the same handle>` with a `ready` receipt, no `send` to a writer, the
writer's session holding both prompts); each verification continuous; the executor waking by itself on every
`worker_done`; every gate closed with its proof; the final report; every reviewer and writer worker of the route
ended by its card's closing procedure (`runner-brief.md`, terminal-close proof) or by Orca's release of a settled
worker, and a plain shell that `orca worktree create` opened recorded, not asserted.

Steps for `F-stop-<card>`: in Orca, send the request; once the first task writer has a `ready` receipt and no
`worker_done`, type STOP into the executor; stop at the executor's report after the stop.

Assert: every writing worker of the tree stopped and proven before any save or rollback (Claude Code, Codex:
`worker-stop` with `state: stopped`, `processAction: closed_agent_terminal`, `close.ptyKilled: true`; Kimi Code:
`terminal close` with `close.ptyKilled: true`, or the handle missing from an untruncated `terminal list`), the proof
earlier in the transcript than the saved patch and any rollback; the ledger line `Stopped by user: dispatch <id>, patch
<path>, tree at <SHA>`; a rollback only where `gates.md` recorded the tree clean before the first dispatch (record
which); no continuation: no new writer and no `send` to the stopped one.

### F-claude · baseline

Executor: Claude Code · Reviewers: codex · in Orca.
Request: T2 + BY-CODEX

### F-codex · baseline

Executor: Codex · Reviewers: claude · in Orca.
Request: T2 + BY-CLAUDE

### F-kimi · baseline

Executor: Kimi Code · Reviewers: codex · in Orca. Also, a lost writer: after the forced follow-up completes, close the
next writer's terminal while it has a `ready` receipt and no `worker_done` (the polisher at the latest) with
`orca terminal close`, `close.ptyKilled: true`. Assert: no takeover by an in-session subagent; the old terminal
proven gone before a new writer; a fresh writer in a new pinned terminal with the same pins, started as the same Task
(`--task <its Task>`, with `--retry-of` only when Orca reports that Task failed or blocked); a ledger line; the route
completes; record whether the final report names the recovery.
Request: T2 + BY-CODEX

### F-stop-claude · baseline

Executor: Claude Code · Reviewers: codex · in Orca.
Request: T2 + BY-CODEX

### F-stop-codex · baseline

Executor: Codex · Reviewers: claude · in Orca.
Request: T2 + BY-CLAUDE

### F-stop-kimi · baseline

Executor: Kimi Code · Reviewers: codex · in Orca.
Request: T2 + BY-CODEX

## Group H: builds and registries without an agent folder

Inputs are mutant exports of the later build (`runtimes.md`, "Building an export"), loaded by the coordinator:
`-no-kimi` without `skills/dopil/references/agents/kimi`, `-no-codex` without `…/agents/codex`. Claude Code loads them
with `--plugin-dir`.

### H-no-kimi · after-only

Executor: Claude Code on `-no-kimi` · Reviewers: codex · in Orca, `kimi` on `PATH`. Stop at its first discovery
receipt. Assert: `kimi` present inside the executor (the interactive PATH check of `runner-brief.md`, run although
nothing is hidden); no dialog: `codex` is the one available reviewer, named in the announcement, with no Kimi;
nothing blocks.
Request: T1

### H-no-codex · after-only

Executor: Claude Code on `-no-codex` · Reviewers: none · outside Orca. Assert: no default, and no reviewer but
`kimi`, so `kimi` has no companion: the executor says so and stops; nothing dispatched, no route step.
Request: T1 + PAR-KIMI

### H-missing-key-line · after-only

The `Reviewers:` line names a key that has no folder, and no gate is locked yet. Executor: Claude Code, session 1 on
`$B`, session 2 on `-no-kimi` · Reviewers: codex, kimi · outside Orca. Session 1 ends by QUIT-ON-LINE; session 2
runs in a new terminal. Assert: session 1 dispatched no discovery and locked no row (no gate row in `gates.md`
records a locked set), its preflight probes (versions, model lookups, login checks) allowed and recorded; on resume
the first gate, by the line, blocks with a message naming `kimi`; the saved set unchanged (the `Reviewers:` line); no
dispatch.
Request (session 1): T1 + BY-CODEX-KIMI
Request (session 2): RESUME

### H-missing-key-row · after-only

A locked gate row names a key that has no folder, and the `Reviewers:` line does not. Executor: Claude Code on
`-no-kimi` · Reviewers: codex, kimi (the fixture's locked row) · outside Orca. Before the start, apply P, then write
the registry: the line `Reviewers: codex` and the open gate `code-01` locked to `codex` and `kimi`, its first
discovery dispatched:

```bash
python3 -I - "$SB" "$(git -C "$SB" rev-parse HEAD)" \
  "$(git -C "$SB" rev-parse --path-format=absolute --git-common-dir)" <<'PY'
import os, sys
sb, base, common = sys.argv[1:]
root = os.path.join(sb, ".dopil", "2026-11-01-usage-row")
gate = os.path.join(root, "code-01")
scope = "git diff %s -- wc/count.py tests/test_count.py" % base
os.makedirs(os.path.join(gate, "codex"))
os.makedirs(os.path.join(gate, "kimi"))
os.makedirs(os.path.join(common, "dopil-routes"))
files = {
    os.path.join(sb, ".dopil", ".gitignore"): "*\n",
    os.path.join(root, "gates.md"): (
        "# dopil route 2026-11-01-usage-row: wc/count.py usage error\n\n"
        "Route: one-off (code → gate → polish → delta gate). Executor: Claude Code.\n"
        "Reviewers: codex\n\n"
        "| Gate | Scope | Scratch | Reviewers | State | Proof |\n|---|---|---|---|---|---|\n"
        "| code-01 | %s | %s (codex/, kimi/) | codex, kimi (locked at r01) | open: round 01 discovery dispatched | - |\n"
        % (scope, gate)),
    os.path.join(gate, "base-sha"): base + "\n",
    os.path.join(common, "dopil-routes", "2026-11-01-usage-row.txt"): root + "\n",
}
for key in ("codex", "kimi"):
    files[os.path.join(gate, key, "base-sha")] = base + "\n"
    files[os.path.join(gate, key, "ledger.md")] = ""
    files[os.path.join(gate, key, "round-01-prompt.md")] = "Review the change: %s.\n" % scope
for path, text in files.items():
    with open(path, "x", encoding="utf-8") as f:
        f.write(text)
PY
```

Assert: `code-01`, by its locked row, blocks with a message naming `kimi`; the saved set unchanged (the line
`Reviewers: codex` and the row's locked set `codex, kimi`) and the row's State cell unchanged; nothing dispatched (no
reviewer process, no new file in `code-01/`). A resume that follows the line instead reviews with `codex` alone: FAIL.
Request: RESUME

## Group I1: identity scripts run by path

Assertions inside the A instances of the later build: the executor's transcript shows the exact invocation
`python3 -I "<skill dir>/references/agents/<folder>/identity.py"`, where `<skill dir>` is the absolute directory of
the loaded `SKILL.md`, and no inline identity block.

### I1-kimi · after-only

Executor: Kimi Code · inside A-kimi-one and A-kimi-all. Assert: the invocation at the route's start, before the vendor
is stated, printing `ALIAS:` and `PROVIDER TYPE: kimi`; outside Orca also the invocation with the coder's agent id as
its argument before the first in-session coder edit, printing the same `ALIAS`.

### I1-agy-gemini · after-only

Executor: Antigravity on a Gemini model · inside A-agy-gemini-one and A-agy-gemini-all. Assert: the invocation at the
route's start, printing `MODEL:` and `VENDOR: Google`, and again before every edit subagent's start and every reviewer
dispatch, discovery and verification.

### I1-agy-other · after-only

Executor: Antigravity on a non-Gemini model · inside A-agy-other-one and A-agy-other-all. Assert as I1-agy-gemini,
with `VENDOR:` the model's vendor.

## Group I2: a missing or failing identity script

Inputs: `-no-identity` (both identity scripts removed) and `-bad-identity` (both replaced by
`raise SystemExit(3)`), mutants of the later build. The coordinator loads the instance's mutant and proves the
loaded copy lacks the script or holds the failing one. Steps: outside Orca, send the request. Assert: the executor
stops before the dialog and any dispatch and names the identity blocker; no edit in the sandbox.

### I2-kimi-missing · after-only

Executor: Kimi Code on `-no-identity` · Reviewers: none · outside Orca.
Request: T1

### I2-kimi-failing · after-only

Executor: Kimi Code on `-bad-identity` · Reviewers: none · outside Orca.
Request: T1

### I2-agy-missing · after-only

Executor: Antigravity on a Gemini model on `-no-identity` · Reviewers: none · outside Orca.
Request: T1

### I2-agy-failing · after-only

Executor: Antigravity on a Gemini model on `-bad-identity` · Reviewers: none · outside Orca.
Request: T1

## Skill files and their cases

For reruns after a change: a changed file reruns the instances of its row, selected by their first line. Paths are
under `skills/dopil/`, the same on the baseline, an earlier dopil export, as on the build under test.

| Changed file | Instances |
|---|---|
| `SKILL.md`, `references/executor.md`, `references/route.md`, any `references/agents/*/agent.md`, `skills/pragmatic-engineering/SKILL.md`, a file not listed here | all |
| `references/reviewer-choice.md` | groups A, B, C, D, D3, E, F, H, M, R |
| `references/reviewer.md`, `references/gate.md`, `references/prompts.md`, `references/ledger.md`, `references/triage.md`, `references/checks.md`, `references/report.md` | all except C-claude-several, C-codex-several, E-claude-cancel, E-agy-cancel, E-claude-none and group I2, group M included |
| `references/polish.md` | groups A and F |
| `references/parallel-review.md` | every instance with two or more reviewers |
| `references/adapter-orca.md` | every instance in Orca |
| `references/migrate.py` | group M |
| `references/contracts.md` | none: the unit tests check it |
| `references/agents/claude-code/executor.md` | every instance whose executor is Claude Code |
| `references/agents/codex/executor.md` | every instance whose executor is Codex |
| `references/agents/kimi/executor.md`, its identity script | every instance whose executor is Kimi Code |
| `references/agents/antigravity/executor.md`, its identity script | every instance whose executor is Antigravity |
| any other file in `references/agents/<folder>/` | every instance whose reviewers include that folder's key |
