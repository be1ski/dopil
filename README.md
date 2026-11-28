Cross-vendor review for Claude Code, Codex, Kimi Code and Antigravity

The agent running dopil writes and fixes; an agent from another vendor only reviews. In Claude Code, with Codex as the reviewer:

```text
/dopil add a --dry-run flag to scripts/deploy.sh with codex
```

Claude Code makes the change and runs your project's checks; Codex returns one list of findings. You see what Claude Code fixes and what it rejects with proof, and Codex rechecks that list in the same thread until every finding is closed.

### Use

| Agent | Example request |
| --- | --- |
| Claude Code | `/dopil add CSV headers with codex` |
| Codex | `$dopil add CSV headers with claude` |
| Kimi Code | `/skill:dopil:dopil add CSV headers with claude` |
| Antigravity | `/dopil:dopil add CSV headers with kimi` |

Codex, Claude Code and Kimi Code can review once installed and signed in, with no plugin. Name several, as in `with codex and kimi` in Claude Code, and they review in parallel. Name none, and dopil uses the only one available or asks.

A feature goes spec → plan → code → polish. The reviewed spec waits for your approval, then your agent implements the plan, tests first, in a git worktree. A one-off, such as a script or a single-file fix, goes code → polish in your current tree.

Scope and taste decisions and stalled disputes come to you. The final table lists every finding and its outcome. Dopil never merges or pushes.

### Install

Paste into Claude Code, Codex or Antigravity:

```
Install the dopil plugin: follow https://github.com/be1ski/dopil#readme
```

Or run the commands for your agent yourself. Restart the session afterwards.

Claude Code

```sh
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin marketplace add be1ski/dopil
claude plugin install dopil@dopil
```

Auto-update: set `"autoUpdate": true` on `extraKnownMarketplaces.dopil` in `~/.claude/settings.json`.

Codex

```sh
codex plugin marketplace add be1ski/dopil
codex plugin add dopil@dopil
```

Codex picks up a new version of dopil when you start a new session.

Kimi Code

Type in Kimi Code, then start a new session with /new

```text
/plugins install https://github.com/be1ski/dopil
```

To update, run the same command again, then start a new session with /new.

Antigravity

```sh
agy plugin install https://github.com/be1ski/dopil
```

To update, run the same command again, then start a new session.

### Moving from ship

Dopil used to be called ship. Close every ship session.

In Kimi Code, install dopil as Install says before you paste the line, and once the agent is done type /plugins, select ship, press D and choose Remove plugin.

Then paste into each agent that has ship:

```
Move from ship to dopil: follow https://github.com/be1ski/dopil#moving-from-ship
```

The agent installs dopil as Install says and finds every `.ship` folder in your projects. From the folder that holds each, it runs the installed plugin's `skills/dopil/references/migrate.py` as the rule "Migration of an old scratch" in its `skills/dopil/references/ledger.md` says: `check`, shows you what would move and, where you agree, `run`. It names every `.ship` it left and why, then removes ship.

Claude Code

```sh
claude plugin uninstall ship@ship
claude plugin marketplace remove ship
```

Codex

```sh
codex plugin remove ship@ship
codex plugin marketplace remove ship
```

Antigravity

```sh
agy plugin uninstall ship
```
