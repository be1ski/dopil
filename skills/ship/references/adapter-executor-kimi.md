# Executor card: Kimi Code

In a Kimi Code session, read `references/executor.md` first. This card overrides its rows **Who the executor is**
(by **Identity**), **Subagents with edit permission** and **Models** (by **Subagent model** and **Model rule**) and
**Structured question** (by **Tools**). For **Route skills** it adds only the install commands and the runtime's skill
names (**Install and naming**); the list and the catalog rules stay in `executor.md`.

**Identity.** Run this block as written. Measured: verified live and against recorded sessions, blockers included.

```bash
( SHIP_KIMI_AGENT=main; B() { echo "BLOCKER: $1"; exit 1; }
KP="$(command -v kimi)" || B "no kimi executable in PATH"
case "$KP" in /*) ;; *) KP="$PWD/$KP" ;; esac; [ -f "$KP" ] && [ -x "$KP" ] || B "kimi is not an executable file: $KP"
KH="${KIMI_CODE_HOME:-$HOME/.kimi-code}"; export KIMI_CODE_HOME="$KH"
[ -n "${KIMI_CODE_SESSION_ID:-}" ] || B "not a Kimi Code session"
[ -s "$KH/config.toml" ] || B "Kimi Code is not set up"
python3 -I - "$KP" "$KH" "$KIMI_CODE_SESSION_ID" "$SHIP_KIMI_AGENT" <<'PY'
import glob, json, os, subprocess, sys
kp, home, sid, agent = sys.argv[1:]
def stop(message):
    print("BLOCKER:", message)
    sys.exit(1)
found = glob.glob(os.path.join(glob.escape(home), "sessions", "*", glob.escape(sid), "agents",
                               glob.escape(agent), "wire.jsonl"))
if len(found) != 1:
    stop("no single wire log for agent %s" % agent)
try:
    lines = open(found[0], "rb").read().split(b"\n")
except OSError as error:
    stop("cannot read the wire log: %s" % error.strerror)
binds = []
for number, line in enumerate(lines, 1):
    if not line.strip():
        continue
    try:
        event = json.loads(line.decode("utf-8"))
    except ValueError:
        if number == len(lines):
            continue  # the record being written: no final newline yet
        stop("wire log line %d is not JSON" % number)
    if isinstance(event, dict) and event.get("type") == "profile.bind":
        binds.append(event.get("modelAlias"))
alias = binds[-1] if binds and isinstance(binds[-1], str) else None
if not alias:
    stop("no model binding in the wire log")
try:
    result = subprocess.run([kp, "provider", "list", "--json"], capture_output=True, text=True)
except OSError as error:
    stop("cannot run kimi provider list: %s" % error.strerror)
if result.returncode != 0:
    stop("kimi provider list exited %d" % result.returncode)
try:
    data = json.loads(result.stdout)
    kind = data["providers"][data["models"][alias]["provider"]]["type"]
except (ValueError, KeyError, TypeError):
    stop("alias %s has no readable provider type" % alias)
print("ALIAS:", alias)
print("PROVIDER TYPE:", kind)  # never print the JSON: it carries credentials
PY
)
```

The vendor is Moonshot AI only for `PROVIDER TYPE: kimi`. A `BLOCKER` line or any other type: blocked (a provider
type names a protocol, not a vendor). Never print the output of `kimi provider list --json` yourself.

**Install and naming.** Superpowers: `/plugins install https://github.com/obra/superpowers` in the Kimi TUI, or an
existing superpowers in `~/.agents/skills`, which Kimi reads. ship: the README's Kimi lines. Update: the same install
commands. After installing or updating either, `/new`. The skill is typed `/skill:ship:ship`. The agent cannot run
`/plugins` itself: give the user the command.

**Instructions.** Kimi loads `AGENTS.md` (and `.kimi-code/AGENTS.md`), not `CLAUDE.md` or `GEMINI.md`: the
generic **Repository instructions** row applies.

**Tools.** `Bash` with `run_in_background` (foreground at most 300 s; background with `disable_timeout`, completion
by notification, output by `TaskOutput`); `Agent` with `subagent_type: coder` for edits; `AskUserQuestion` (2–4
options, `multi_select`, "Other" added by the runtime). Under Never Ask (`--auto`) Kimi refuses `AskUserQuestion`
("Cannot call AskUserQuestion while auto permission mode is active"), so there every structured question,
escalations and the dialog alike, is plain text. In Orca, before every turn end while a dispatch of this run is
unsettled (after `worker-start`, a follow-up, `send`, a `reply`, a batch that leaves other workers running, or a
non-terminal escalation), the executor starts
`ORCA orchestration check --terminal "$ORCA_TERMINAL_HANDLE" --peek --wait --timeout-ms 1800000 --json` with
`run_in_background` and `disable_timeout`. One wait at a time. When it completes, a clean timeout included, or Orca's
own wake arrives, the executor runs the consuming `ORCA orchestration check --terminal "$ORCA_TERMINAL_HANDLE" --json`
and handles that batch as `adapter-orca.md` says. A non-zero exit or an error: stop and tell the user, no new wait.
Measured: Orca did not wake an idle Kimi executor on `worker_done`; its own task's completion did, and `--peek --wait`
returns on a new message without consuming it.

**Subagent model.** Before the first in-session `coder` edit assignment of a route (not for Orca writers), dispatch
one `Agent` with `subagent_type: coder` and the prompt "Reply with exactly OK. Do not read, create or edit any file
and run no command." Then run the **Identity** block with the `main` of `SHIP_KIMI_AGENT=main;` in its first line
replaced by the agent_id that Agent call returned, the only change: it must print the session's `ALIAS`. Measured: the
`Agent` result carries `agent_id: agent-0`, the name of its wire directory. Another alias, a `BLOCKER` line, or no
`agent_id`: no in-session edit subagents for the route; the work they would do runs inline (`references/executor.md`),
a line in the report.

**Model rule.** The session's alias for every role; an escalation is a fresh subagent or worker on the same alias
where the route has one (see **Subagent model**), otherwise it stays inline; a ledger line.

**Orca writing workers** (task executor, gate fixer, parallel fixer, polisher, escalation). Never
`worker-start --agent kimi`: its first prompt is not delivered. One terminal per writer:
`ORCA terminal create --worktree <the route's tree selector, or current on a one-off route> --command "<launch>"`,
where `<launch>` is built per argument as `printf '%q ' KIMI_CODE_HOME="<the parent's Kimi home>"
"<the parent's resolved kimi path>" --auto -m "<alias>"`, with `KIMI_MODEL_THINKING_EFFORT="<the parent's value>"`
after the Kimi home only if the parent's shell has it set. No `--skills-dir`, unlike the Kimi reviewer's launch: the
writer keeps the user's skills (it needs the TDD skill). Invoking ship in Orca authorizes `--auto` (Never Ask)
for these writers, as Codex workers run in Orca's own mode. The launch command is the writer's pin; it is not
re-checked inside the same terminal. Then `ORCA terminal wait --terminal <handle> --for tui-idle`: a `blockedReason`
of `agent-trust-workspace` means the user accepts the folder in that tab, then the same wait again; any other
unsatisfied wait: show the user the screen, close the terminal, the start did not happen. Only after a satisfied
wait, `ORCA orchestration worker-start --spec-file … --terminal <handle>`; only a `ready` receipt counts. Any other:
`adapter-orca.md`, "If the worker did not start"; a writer lost mid-task: `adapter-orca.md`, "A card writer lost
mid-task". The handle and every dispatch id go into the SDD ledger or the gate scratch.

**Follow-ups** (fix rounds, later gate-fixer rounds, polish follow-ups) go as a new task into the same terminal,
never as `send`: after the writer's `worker_done`, `ORCA terminal wait --terminal <its handle> --for tui-idle`, then
`ORCA orchestration worker-start --spec-file … --terminal <the same handle> --json`; only a `ready` receipt for that
handle counts. Measured: this continues the same Kimi session; on a closed terminal it fails `agent_unconfigured`
with no new terminal. `agent_unconfigured` or any other failure: no new writer until the old one is proven gone
(**Closing**); then a fresh pinned terminal, a ledger line. A failed follow-up restarts its Task there as
`adapter-orca.md`, "A card writer lost mid-task", says; one refused before Orca created a Task gets a fresh start
there with the first assignment file plus the brief.

**Closing.** A writer's terminal stays through interim `worker_done` messages and is closed when its role is accepted
or abandoned: task done, gate closed, polish accepted, escalation, failed start, user stop (the terminal close is the
stop). The close is `ORCA terminal close --terminal <handle> --json` returning `close.ptyKilled: true`, or else the
handle missing from `ORCA terminal list --json` with `truncated: false`. Only these prove a writer gone: liveness
`exited` or `lost` alone does not, and a terminal still listed is closed first.

**Pitfalls.** "Trust this folder?" in a new worktree.
