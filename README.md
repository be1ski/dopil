Cross-vendor review for Claude Code and Codex

Your agent writes and fixes. The other vendor only reviews, at every step, until clean. Code gates also run the project's checks.

### Install

Paste into Claude Code or Codex:

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

### Use

```text
/ship add a --dry-run flag to scripts/deploy.sh    # Claude Code
$ship add CSV export to the reports page           # Codex
```

Gemini and Kimi Code are also available. Request `reviewer gemini`, `reviewers gemini and kimi`, or `all reviewers`; multiple reviewers run in parallel.

Feature: spec → plan → code → polish. One-off: code → polish.

Features run in a git worktree. Ship never merges or pushes.
