# Executor card: Antigravity CLI

In an Antigravity CLI session, read `references/executor.md` first. This card overrides its rows **Who the executor
is** (by **Identity**), **Subagents with edit permission** and **Models** (by **Subagent model**) and **Structured
question** (by **Tools**). For **Route skills** it adds only the install commands and the runtime's skill names
(**Install and naming**).

**Identity.** Run this block as written during the executor's own turn, never inside a writer's terminal: at the
route's start, with its `VENDOR` recorded in `gates.md` as the executor's vendor, and again before every Orca writer
start or follow-up and every reviewer dispatch, discovery and verification. Measured: verified live in a Gemini and
a Claude session and against recorded conversations.

```bash
( [ -n "${ANTIGRAVITY_AGENT:-}" ] || { echo "BLOCKER: not an Antigravity session"; exit 1; }
python3 -I - <<'PY'
import json, os, sys
def stop(message):
    print("BLOCKER:", message)
    sys.exit(1)
data, conversation = os.environ.get("ANTIGRAVITY_APP_DATA_DIR", ""), os.environ.get("ANTIGRAVITY_CONVERSATION_ID", "")
if not data or not conversation:
    stop("no Antigravity conversation in the environment")
path = os.path.join(data, "brain", conversation, ".system_generated", "logs", "transcript.jsonl")
try:
    lines = open(path, "rb").read().split(b"\n")
except OSError as error:
    stop("cannot read the transcript: %s" % error)
steps = []
for number, line in enumerate(lines, 1):
    if not line.strip():
        continue
    try:
        step = json.loads(line.decode("utf-8"))
    except ValueError:
        if number == len(lines):
            continue  # the record being written: no final newline yet
        stop("transcript line %d is not JSON" % number)
    if isinstance(step, dict):
        steps.append(step)
last = max((i for i, step in enumerate(steps) if step.get("type") == "USER_INPUT"), default=None)
if last is None:
    stop("no user turn in the transcript")
models = [step["model"] for step in steps[last + 1:] if step.get("type") == "PLANNER_RESPONSE"
          and isinstance(step.get("model"), str) and not step["model"].startswith("gemini-pro-orchestrator-")]
if not models:
    stop("no model step in the current turn")
vendor = next((name for prefix, name in (("gemini-", "Google"), ("claude-", "Anthropic"), ("gpt-", "OpenAI"))
               if models[-1].startswith(prefix)), None)
if vendor is None:
    stop("unknown model family: %s" % models[-1])
print("MODEL:", models[-1])
print("VENDOR:", vendor)
PY
)
```

A `BLOCKER` line: blocked. A `VENDOR` equal to that of any reviewer in the gate's set (its locked row,
`reviewer-choice.md`) stops the route and is told to the user, with no reselection. A `VENDOR` other than the recorded
one blocks: no writer start or reuse and no review; tell the user the executor's vendor changed.

**Install and naming.** Superpowers: `agy plugin install https://github.com/obra/superpowers` (agy does not read
`~/.agents/skills`). ship: the README's Antigravity lines. Skills appear as `ship:ship`, typed `/ship:ship`. Update:
the same commands. Never `agy plugin import`: it imports every Claude Code plugin with its hooks into every agy
session.

**Instructions.** Antigravity loads `GEMINI.md` and `AGENTS.md`, not `CLAUDE.md`: the generic **Repository
instructions** row applies.

**Tools.** No skill tool; `read_file` takes absolute paths only; skill and reference files are read with `read_file`,
never through `cat` or another shell command (measured: agy cut the middle of a long `cat` output), and a
partial read is continued from the offset or line range `read_file` returns until the whole file is read, before
acting on it (measured: a read stopped at 46,080 bytes); `run_command` backgrounds after at most 10 s,
completion arrives as a system message, output by `manage_task` or the task log; `invoke_subagent` with
`TypeName: self` for edits; `ask_question` with `is_multi_select`, its options passed in the dialog's order and with
no "(Recommended)" marker (otherwise the model reorders them and adds one). Todo lists are task artifacts. In Orca,
before every turn end while a dispatch of this run is unsettled (after `worker-start`, a follow-up, `send`, a
`reply`, a batch that leaves other workers running, or a non-terminal escalation), the executor starts
`ORCA orchestration check --terminal "$ORCA_TERMINAL_HANDLE" --peek --wait --timeout-ms 1800000 --json` with
`run_command`. One wait at a time. When it completes, inline or in the background, a clean timeout included, or Orca's
own wake arrives, the executor runs the consuming `ORCA orchestration check --terminal "$ORCA_TERMINAL_HANDLE" --json`
and handles that batch as `adapter-orca.md` says. A non-zero exit or an error: stop and tell the user, no new wait.
Measured: Orca did not wake an idle agy executor after its writers; its own task's completion did, and
`--peek --wait` returns on a new message without consuming it.

**Subagent model.** Always `Model: inherit`; the tiers (`flash_lite`, `flash`, `pro`) map to Gemini models whatever
the session runs. Measured: an `inherit` subagent under a Claude session ran that Claude model. An escalation is a
fresh `inherit` subagent, a ledger line.

**Orca writing workers** (task executor, gate fixer, parallel fixer, polisher, escalation). The task executor:
`ORCA orchestration worker-start --spec-file "$W/task-N-dispatch.md" --task-title "ship impl: task N" --worktree
"<the route's tree selector, or current on a one-off route>" --agent antigravity --model <the Identity block's MODEL>
--keep-open --json > "$W/task-N-receipt.json"`; every other role the same, with its own spec file and title. The
model must be one `agy models` lists; otherwise Orca writing workers are unavailable: stop and tell the user. Orca
launches `agy --model <id>` (measured), so the pin holds from the start. On that receipt: `ready` with another
`.result.model`: stop that worker, close its terminal, show the user `git status` of the tree; no replacement without
the user. A `.result.mode` other than `terminal` (a structured session also fills `.result.terminal`): not a usable
start; stop that dispatch and tell the user. A start blocked at a trust prompt (a new worktree), as measured for the
Gemini reviewer (`references/adapter-reviewer-gemini.md`, "Orca"): the user accepts it in that tab, that dispatch is
released as `adapter-orca.md`, "If the worker did not start", requires, the terminal is proven gone (**Closing**),
and the Task is restarted as `adapter-orca.md`, "A card writer lost mid-task", says.
Handles and dispatch ids go into the SDD ledger or the gate scratch.

**Follow-ups.** Never `send`: a reopened worker loses `--model`. After the worker's `worker_done`,
`ORCA terminal wait --terminal <its handle> --for tui-idle`, then
`ORCA orchestration worker-start --spec-file … --terminal <the same handle>`; only a `ready` receipt for that handle
counts. `agent_unconfigured` from `worker-start --terminal`, or a wait that finds no terminal, does not by itself
prove the terminal gone: only after its handle is missing from an untruncated `ORCA terminal list`, or it is closed
with `close.ptyKilled: true` (**Closing**), a replacement worker, a ledger line. A failed follow-up
restarts its Task as `adapter-orca.md`, "A card writer lost mid-task", says; one refused before Orca created a Task
gets a fresh start with the first assignment file plus the brief. `terminal_busy`, an unsatisfied wait on a live
terminal, `outcome_unknown` or any other error: no new writer; `adapter-orca.md`, "If the worker did not start".

**Closing.** As in `adapter-executor-kimi.md`, **Closing**.
