Cross-vendor review for Claude Code, Codex, Kimi Code and Antigravity

Your agent writes and fixes. The other vendor only reviews, at every step, until clean. Code gates also run the project's checks.

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

### Use

```text
/dopil add a --dry-run flag to scripts/deploy.sh   # Claude Code
$dopil add CSV export to the reports page          # Codex
/skill:dopil:dopil fix the flaky login test        # Kimi Code
/dopil:dopil add pagination to the users API       # Antigravity
```

Dopil asks which of your other agents review, or uses the only one you have; name them in the request to skip the question

Feature: spec → plan → code → polish. One-off: code → polish.

Features run in a git worktree. Dopil never merges or pushes.

### Moving from ship

Close every ship session, then paste into each agent that has ship:

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

Kimi Code

Install dopil as Install says before you paste the line, and once the agent is done type /plugins, select ship, press D and choose Remove plugin

Antigravity

```sh
agy plugin uninstall ship
```
