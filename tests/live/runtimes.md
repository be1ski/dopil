# Live check kit: launch variants

How each runtime starts in the sandbox, how the coordinator loads a build into it and undoes that, and how to hide a
binary from it. Runners use only the rows the coordinator gives them (`runner-brief.md`). Placeholders: `$SB` the
sandbox (`make-sandbox.sh`), `$B` the build under test (an export, "Building an export"), `$SEL` the sandbox's Orca
worktree selector, `<agy-gemini-model>` and `<agy-other-model>` from "Model ids", `<Codex home>` (`$CODEX_HOME`, else
`~/.codex`) and `<Kimi home>` (`$KIMI_CODE_HOME`, else `~/.kimi-code`).

## Launch variants

"In Orca" is `orca terminal create --worktree "$SEL" --title "live <case>" --command "<start>" --json`; Orca types
the command into a login shell in the sandbox, so the shell stays when the CLI exits. "Outside Orca" is the same
terminal with `<start>` prefixed by `env -u ORCA_TERMINAL_HANDLE `: that variable is ship's Orca switch, so the
reviewers run headless. Print mode runs in the runner's own shell, `cd "$SB" && env -u ORCA_TERMINAL_HANDLE <print>
> "$E/<case>/events.jsonl" 2> "$E/<case>/stderr.txt"`, in the background.

| Variant | Start in Orca | Outside Orca | Invocation | Print mode | Load, config change, undo | PATH without a binary | Loaded `SKILL.md` |
|---|---|---|---|---|---|---|---|
| Claude Code | `claude --plugin-dir $B --dangerously-skip-permissions` | the start, prefixed | `/ship <task>` | `claude --plugin-dir $B --dangerously-skip-permissions -p --output-format stream-json --verbose "/ship <task>"` | "Loading", Claude Code | "PATH without a binary" | `$B/skills/ship/SKILL.md` |
| Codex | `codex --dangerously-bypass-approvals-and-sandbox` | the start, prefixed | `$ship <task>` | `codex exec --json --dangerously-bypass-approvals-and-sandbox '$ship <task>'` | "Loading", Codex | "PATH without a binary", plus `--disable shell_snapshot -c allow_login_shell=false` after the start or print command | `<Codex home>/plugins/cache/ship/ship/local/skills/ship/SKILL.md` |
| Kimi Code | `kimi --auto` | the start, prefixed | `/skill:ship:ship <task>` | none | "Loading", Kimi Code | "PATH without a binary" | `<Kimi home>/plugins/managed/ship/skills/ship/SKILL.md` |
| Antigravity on a Gemini model | `agy --dangerously-skip-permissions --model <agy-gemini-model>` | the start, prefixed | `/ship:ship <task>` | none | "Loading", Antigravity | "PATH without a binary" | `$SB/.agents/plugins/ship/skills/ship/SKILL.md` |
| Antigravity on a non-Gemini model | `agy --dangerously-skip-permissions --model <agy-other-model>` | the start, prefixed | `/ship:ship <task>` | none | "Loading", Antigravity | "PATH without a binary" | `$SB/.agents/plugins/ship/skills/ship/SKILL.md` |

Kimi Code and Antigravity have no print mode in the kit: their cards list no run that cannot take an answer. A fresh
agy TUI may show an "esc to dismiss" banner that swallows typed text: send Escape (`$'\x1b'`) before the task.

## Transcripts

Where each executor's transcript is, for the build proof and the I cases (the runner asks the executor to print the
named variables, one by one, never the environment):

| Runtime | Transcript |
|---|---|
| Claude Code | `~/.claude/projects/<the sandbox path with / as ->/<session id>.jsonl`; print mode: the events file |
| Codex | the rollout file of `$CODEX_THREAD_ID` under `<Codex home>/sessions/`; `codex exec`: the events file |
| Kimi Code | `<Kimi home>/sessions/*/$KIMI_CODE_SESSION_ID/agents/main/wire.jsonl` |
| Antigravity | `$ANTIGRAVITY_APP_DATA_DIR/brain/$ANTIGRAVITY_CONVERSATION_ID/.system_generated/logs/transcript.jsonl` |

## Model ids

None is written in the kit; the coordinator resolves them before a window and gives them to the runners.
`<agy-gemini-model>`: a `gemini-` entry of `agy models` with its highest effort level. `<agy-other-model>`: a
non-Gemini entry of `agy models` with its lowest effort level, where a weak model shows whether the cards' commands
are followed as written. The after run uses the ids the baseline used while `agy models` lists them; otherwise the
nearest, recorded. Claude Code, Codex and Kimi Code start on the model their configuration selects, and reviewers on
the model ship pins: both are recorded from receipts and transcripts, never compared.

## Loading

The coordinator does all of this, inside a config window the owner approved, and records the state before and after
(`pre-window.md`). "Pre-window" below means what that record shows.

| Runtime | Load a build | Config change | Undo |
|---|---|---|---|
| Claude Code | `--plugin-dir $B` in the start command; `$SB/.claude/settings.json` turns the installed `ship@ship` off for this project | none | none |
| Codex | `codex plugin marketplace remove ship` (if pre-window has one), `codex plugin marketplace add $B`, `codex plugin add ship@ship` | the marketplace `ship` and the installed `ship@ship` (pre-window: `codex plugin marketplace list`, the source of `ship`, whether `ship@ship` is installed, and its `plugins."ship@ship".enabled` value in `<Codex home>/config.toml`, which no `codex plugin` command sets) | `codex plugin remove ship@ship`, then `codex plugin marketplace remove ship`; then, if pre-window had a source, `codex plugin marketplace add <pre-window source>`, and `codex plugin add ship@ship` only if pre-window had it installed, followed by its pre-window `plugins."ship@ship".enabled` value written back to `<Codex home>/config.toml` |
| Kimi Code | in a Kimi TUI the coordinator starts in `$SB` for this only: `/plugins install $B`, "Trust and install" when asked, quit; every case starts a fresh session | the `ship` entry of Kimi's installed plugins (pre-window: its source in `/plugins`) | `/plugins install <pre-window source>`, or remove `ship` in `/plugins` when there was none |
| Antigravity | the workspace plugin `$SB/.agents/plugins/ship` (`make-sandbox.sh`); a new build: `rm -rf "$SB/.agents/plugins/ship" && mkdir "$SB/.agents/plugins/ship" && cp -R "$B/." "$SB/.agents/plugins/ship" && rm -rf "$SB/.agents/plugins/ship/.git"` | none; the global `ship` plugin, if pre-window has one, stays enabled: a disabled same-named global plugin hides the workspace copy as well, and with it enabled the workspace copy registers | none |
| Trust, every CLI | the owner accepts the trust prompt for `$SB` on each CLI's first start there, and the coordinator accepts a prompt a case pauses on (`runner-brief.md`) | each CLI's trust entry for that folder (pre-window: trusted or not) | remove the entries in each CLI's trust settings, or keep them on the owner's word |
| Orca | `orca repo add --path "$SB" --kind git --json`; `$SEL` is `id:<repo id>::$SB` | the sandbox's repository registration (pre-window: `orca repo list --json`) | only for a registration the window added: `orca repo hide --repo id:<repo id>` (Orca has no repository removal); one pre-window lists stays as it was |

Before a runtime's batch, the coordinator proves the build it loaded: `diff -r $B/skills <installed>/skills` is empty,
where `<installed>` is the directory above the `skills/` of the runtime's "Loaded `SKILL.md`" (Claude Code loads `$B`
itself). A mutant is loaded and proven the same way, and the main export again after it.

## Building an export

An export is a single-commit git repository of one ship revision; Codex and Kimi accept it as a local source.

```bash
X=<live root>/build/ship-<sha7>                       # must not exist yet
(
  set -e -o pipefail                                  # any failed step stops the recipe before the commit
  mkdir -p "$(dirname "$X")"
  mkdir "$X"
  git -C <ship repo> archive <sha> | tar -x -C "$X"
  # A mutant (cases.md): apply its change here, before the commit.
  git -C "$X" init -q
  git -C "$X" add -A
  git -C "$X" -c user.name=ship-live -c user.email=ship-live@invalid -c commit.gpgsign=false \
    -c core.hooksPath=/dev/null commit -q -m "Export of <sha>"
)
```

Record the source SHA (the commit message carries it) and `git -C "$X" rev-parse HEAD`; for a mutant also
`diff -r -x .git <export> <mutant>`.

## PATH without a binary

For each `PATH` entry that holds a hidden binary, a shim directory of its own replaces it in the same slot, so the
order of `PATH` stays; the shim holds symlinks to every executable of that entry except the hidden binaries. Run
this in the runner's shell with a fresh shim directory per case:

```bash
NEWPATH="$(python3 -I - "$PATH" "<start dir>" "$E/<case>/path-shims" kimi agy <<'PY'
import os, sys
entries, start, shims, hidden = sys.argv[1].split(os.pathsep), sys.argv[2], sys.argv[3], set(sys.argv[4:])
os.mkdir(shims)
for index, entry in enumerate(entries):
    entry = os.path.join(start, entry)  # an empty entry is the start directory, a relative one lies under it
    names = os.listdir(entry) if os.path.isdir(entry) else []
    if hidden.isdisjoint(names):
        continue
    shim = os.path.join(shims, str(index))
    os.mkdir(shim)
    for name in names:
        source = os.path.join(entry, name)
        if name not in hidden and os.path.isfile(source) and os.access(source, os.X_OK):
            os.symlink(source, os.path.join(shim, name))
    entries[index] = shim
print(os.pathsep.join(entries))
PY
)"
```

`PATH` goes in as an argument because an interpreter shim (pyenv, for one) changes the child's own `PATH`.
`<start dir>` is the absolute directory the executor starts in (`$SB`, or the case's worktree): an empty entry stands
for it and a relative one is resolved under it, so no link dangles and no entry is skipped. The arguments after the
shim directory are the binaries to hide. Start with `env PATH="$NEWPATH" <start>` (outside Orca:
`env -u ORCA_TERMINAL_HANDLE PATH="$NEWPATH" <start>`), quoted for `--command` with `printf '%q'`. Codex runs its
commands through a login shell and a shell snapshot that restore the full `PATH`, so a Codex start or `codex exec`
also takes `--disable shell_snapshot -c allow_login_shell=false`. Both sides are proven inside the executor, not in the
runner's shell: every hidden binary absent, the executor's own binary and every remaining reviewer binary present
(`runner-brief.md`, "PATH precondition").
