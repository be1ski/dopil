Cross-vendor review for Claude Code, Codex, Kimi Code and Antigravity

Your agent writes and fixes. The other vendor only reviews, at every step, until clean. Code gates also run the project's checks.

### Install

Paste into Claude Code, Codex or Antigravity:

```
Install the ship plugin: follow https://github.com/be1ski/ship#readme
```

Or run the commands for your agent yourself. Restart the session afterwards.

Claude Code

```sh
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin marketplace add be1ski/ship
claude plugin install ship@ship
```

Auto-update: set `"autoUpdate": true` on `extraKnownMarketplaces.ship` in `~/.claude/settings.json`.

Codex

```sh
codex plugin marketplace add be1ski/ship
codex plugin add ship@ship
codex plugin add superpowers@openai-curated-remote
```

Kimi Code

Type in Kimi Code, then start a new session with /new

```text
/plugins install https://github.com/obra/superpowers
/plugins install https://github.com/be1ski/ship
```

Antigravity

```sh
agy plugin install https://github.com/obra/superpowers
agy plugin install https://github.com/be1ski/ship
```

To update in Kimi Code or Antigravity, run the same commands again (in Kimi Code, then /new)

### Use

```text
/ship add a --dry-run flag to scripts/deploy.sh    # Claude Code
$ship add CSV export to the reports page           # Codex
/skill:ship:ship fix the flaky login test          # Kimi Code
/ship:ship add pagination to the users API         # Antigravity
```

Ship asks which of your other agents review, or uses the only one you have; name them in the request to skip the question

Feature: spec → plan → code → polish. One-off: code → polish.

Features run in a git worktree. Ship never merges or pushes.
