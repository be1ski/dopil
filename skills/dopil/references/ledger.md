# dopil: ledger

## Ledger

**Each new route gets a new scratch-root**, for example `.dopil/<unique-route-id>/`,
or a new directory outside the tree. Inside a git tree, create `.dopil/.gitignore` with the single line `*`
if it is missing: the scratch then ignores itself and the repository's own `.gitignore` stays untouched.
Create the root so that creation fails if the name exists; do not reuse a past
route even after it is completed. A continuation of the same route keeps the earlier root.
Inside it each gate gets a separate directory: `spec-01/`, `plan-01/`, `code-01/`, `polish-01/`,
`confirm-01/`. Parallel routes also have different roots.
For recovery in Git, write the absolute path of the scratch-root to the file
`<git-common-dir>/dopil-routes/<route-id>.txt`, where `git-common-dir` is obtained with
`git rev-parse --path-format=absolute --git-common-dir` from any worktree. This is a pointer to the registry,
not one more ledger. Outside Git, or when the git directory is not writable for the current runtime (a sandbox that makes `.git` read-only), keep such a pointer in `.dopil/routes/` of the original working directory instead; do not ask for a permission only to write the pointer.
After a break, find your route's pointer rather than starting a new registry in the current worktree. Look in both places.
In `<scratch-root>/gates.md` keep the registry: gate, scope, absolute scratch path, state and
proof of closure. Keep there as well the absolute paths of the spec, the plan and the SDD progress ledger for
transitions between stages. When the worktree changes, keep using this registry and the listed directories;
do not overwrite closed gates, add a new gate as a separate row.
A run that did not happen is an attempt of the same gate. If the reviewer card requires a new scratch for the retry,
keep a reference to the failed attempt and update the active path in the registry, without losing the base and
the ledger.

**A file, not memory:** `<gate-scratch>/ledger.md`, one line per finding — id (your own, running through the gate: `#1`,
`#2`, …) · round · quote · decision
(fixed / rejected + reason / escalated / open) · scope in which it was judged · a **secondary** mark,
if the finding lies in code that a previous round of the same gate added. Conversational memory does not
survive compaction, and the gate cannot be closed while the file has open lines.

The ledger is the source of the "responses to findings" block in the verification prompt: one line for every
**open** ledger line — not only for discovery findings, but also for `REGRESSED` and new ones
raised by verification rounds — its title verbatim and what was done about it.

**Only decisions and technical reasons** go into the ledger. Never "rounds 1–3 already looked, it is clean
here": that is not an argument but suggestion, and it breaks the reviewer.

Next to it lie `base-sha` (for a git gate) or snapshots with a scope description, `thread-id` (the discovery
thread, mandatory), `last-review.txt` (the output of the last round) and the reviewer card's files. A new gate — a new
id; do not mix the threads of different gates and parallel tasks. After a break, read the registry and the
ledgers, including carried-over SDD entries: readiness and the final report are assembled over the whole route.

## Migration of an old scratch

A route scratch of the previous plugin, `.ship/` with its pointers in `<git-common-dir>/ship-routes/`, moves to
`.dopil/` and `dopil-routes/` by the script `<skill dir>/references/migrate.py`, where `<skill dir>` is the directory of
the loaded `SKILL.md`. Run it by that absolute path, `python3 -I "<skill dir>/references/migrate.py" check` (`run` in
place of `check` to move), from the project's directory, as the first step of the startup order. `check` changes
nothing. Both modes print `MOVE <src> -> <dst>`, `LEAVE <path>: <reason>` and `RESTART-LATER <gates.md>: <gates>`
lines; the exit code says what follows.

**Exit 1: moves found.** First the precondition, no live work of the old scratch: no process holds a planned scratch
path (the source of each `MOVE <dir>/.ship -> <dir>/.dopil` line) in its command line. Write those paths, one per line,
to a temporary file in a step of its own, then run `ps -Aww -o pid=,args= | grep -F -f <file>`: it matches each path
literally, and its own command line does not hold them, so it cannot find itself. In Orca, also every dispatch and kept
terminal that the planned routes record (`thread-id`, the cards' terminal files, receipts) is shown finished by
`worker-show` or by the terminal-close proof of `references/adapter-orca.md`. Live work blocks the migration for this
run and is named to the user. Then, because neither check sees every turn, ask the user once to confirm that no
session of the previous plugin runs. Confirmed: `run`. Not confirmed, or a run that cannot take an answer: skip the
migration for this run.

**Exit 0**: nothing to move; name every `LEAVE` path, from `check` or `run`, to the user, whatever work starts. **Exit
2**: refused, `REFUSE <path>: <reason>`, a path that is not the plain case or could not be read while planning; name the
refusal; nothing it changed is kept. **Exit 3**: `run` failed after a write, `PARTIAL <step>, step <n> of 5: <error>;
moved: <the moves done>`; name the interrupted step and the moves done in it and before it, and `run` again. **Exit
64**: a usage error, a `usage:` line; the call was not `check` or `run`, so correct it.

In every outcome new work goes on under `.dopil`. A request to resume an old route that was not moved (skipped,
refused, partial or left) is answered with the reason it waits, and its state stays as it is. After `run`, one message
to the user, in their language: what moved, what was left and why, and the `RESTART-LATER` gates, which restart when
their route is resumed.

**Restart on resume.** A route's gates change only when that route is resumed. When its `gates.md` holds the line
`Migrated <date>: restart on resume: <gates>`, then before any of its gates runs, restart each gate the line names
that has no outcome line `<gate> superseded by <new gate>` yet; for a line that says `unknown` (a registry the script
could not read), read the registry yourself and restart each gate you find not closed. Closed gates stay closed. A
gate whose registry holds the outcome line `<gate> superseded by <new gate>` is closed for every purpose, whatever its
old line or row still says; a resume continues `<new gate>`. For each gate, write an `inputs.json`: `{"scratch": "<old
scratch>", "scope": "<scope>", "header": "<opening lines>", "carry": {"<scratch key>": ["<id> — <location> — <claim>",
…]}, "snapshots": [["<copy>", "<original>"], …], "locked": ["<key>", …]}`. You read each value; the script reads none
of them from the registry. `scratch` is the old attempt's scratch as the gate's row names it, a retry path included,
inside the route root, or `null` for a gate that was never prepared, which has none: nothing is copied then; a path
under the old root, before or after the move, is fine, the script maps it to the moved root. `scope` is the gate's
scope, one line, as the row gives it; it is kept literal, and a table row escapes its `|`. `header` is the opening
lines of the old attempt's `ledger.md` that state the scope, the working directory and the base, as written there, or
empty when it has no ledger. `carry` holds, for each reviewer of the gate, the lines of its own old ledger that it had
not answered RESOLVED in a counted round (a rejection it accepted counts as answered), with their ids and claims, each
id once; a reviewer with none is left out. `snapshots` holds, for a snapshot gate, each snapshot's absolute path and
the original path it maps to. `locked` holds the keys of the locked reviewer set the old row records, read from that
row; when the row records none, leave it out, and the new gate follows the usual rule of
`references/reviewer-choice.md`. Then run `python3 -I "<skill dir>/references/migrate.py" restart <gates.md> <gate>
<inputs.json>` from the project's directory. It prints `RESTART <gate> -> <new gate>`: the assignment `<gate> restarts
as <new gate>` (the next free number of that stage; a name such as `code-02-retry` takes 02), the new scratch `<route
root>/<new gate>` with its saved copy of the inputs, the old attempt's `base-sha` (each reviewer's too) or its
snapshots under `snapshots/` with `snapshots.txt` mapping each to its original, each carried reviewer's
`<key>/known-items.md`, the outcome `carried to <new gate>/<id>` on the old ledger, the new ledger's opening lines
from `header`, the new row `open (restarted from <gate>…)` with `scope` and the old row closed, and last the outcome
line, every path under the old root rewritten to the moved one. Or `NOTHING <gate>: <reason>` (exit 0): there is
nothing to restart. **Exit 2**, `REFUSE <path>: <reason>`: the inputs or the registry cannot be used, a `scratch` that
does not exist or lies outside the route root, one id carried with two claims and a carried reviewer without an old
ledger to mark included, and nothing was written; correct them and run it again. **Exit 3**, `PARTIAL <error>`: run
the same call again; once the inputs are saved, it finishes from its saved copy. What the old gate had not chosen yet
goes through the usual preflight. When the route reaches the new gate, its discovery runs as for any new gate, and
each reviewer's `known-items.md` goes into that reviewer's discovery as the "Known task-review items" block of
`references/prompts.md`. Each id's decision goes into the new gate's ledger; a CONFIRMED item is a normal finding; an
item without a decision keeps the gate open. The report names the cost: one discovery per gate that was not closed at
the move, a gate never dispatched included.