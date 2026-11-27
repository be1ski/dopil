#!/usr/bin/env bash
# Validate the plugin, install it into an isolated Claude Code profile and assert it loads.
# Usage: bash tests/smoke_claude.sh [<plugin repo dir>]   (default: current directory)
# Needs network and git access to GitHub. The temporary profile is removed on exit.
set -euo pipefail

fail() { echo "smoke_claude: $*" >&2; exit 1; }

REPO="$(cd "${1:-.}" && pwd)"

# Every option review_claude.py passes still opens an option line of `claude --help`.
HELP="$(claude --help)"
for flag in -p --safe-mode --tools --allowedTools --permission-mode --disable-slash-commands \
            --output-format --verbose --model --effort --session-id --resume; do
  grep -qE -- "^[[:space:]]*(-[A-Za-z], )?$flag([[:space:],=<[]|\$)" <<<"$HELP" \
    || fail "claude --help no longer lists $flag"
done
H="$(mktemp -d)"
trap 'rm -rf "$H"' EXIT
export CLAUDE_CONFIG_DIR="$H"

# The plugin validates with no error and no warning but "No version specified".
VALIDATE="$(claude plugin validate "$REPO" --json)" || { printf '%s\n' "$VALIDATE"; fail "claude plugin validate reported errors"; }
printf '%s' "$VALIDATE" \
  | jq -e '[.manifest, (.contents // [])[]] | map(.warnings[]) | all(.message | startswith("No version specified"))' \
  > /dev/null || { printf '%s\n' "$VALIDATE"; fail "claude plugin validate reported unexpected warnings"; }

# The superpowers dependency resolves only from a known marketplace.
claude plugin marketplace add anthropics/claude-plugins-official \
  || fail "adding anthropics/claude-plugins-official failed: this script needs network and git access to GitHub"
claude plugin marketplace add "$REPO"
claude plugin install dopil@dopil

LIST="$(claude plugin list --json)"
ENTRY="$(printf '%s' "$LIST" | jq '.[] | select(.id == "dopil@dopil")')"
[ -n "$ENTRY" ] || fail "dopil@dopil is missing from claude plugin list --json"
ROOT="$(printf '%s' "$ENTRY" | jq -r '.installPath // empty')"
if [ -z "$ROOT" ]; then
  set -- "$H"/plugins/cache/dopil/dopil/*/
  if [ "$#" -eq 1 ]; then ROOT="$1"; fi
fi
[ -n "$ROOT" ] && [ -d "$ROOT" ] || fail "no plugin root for dopil@dopil"

# Every file git tracks under skills/ is in the installed copy.
env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_OBJECT_DIRECTORY -u GIT_COMMON_DIR \
  git -C "$REPO" ls-files -z skills > "$H/tracked"
[ -s "$H/tracked" ] || fail "git ls-files lists no file under skills/ in $REPO"
while IFS= read -r -d '' rel; do
  [ -f "$ROOT/$rel" ] || fail "missing $rel under $ROOT"
done < "$H/tracked"

# Load state: `enabled` and `errors` as named by `claude plugin list --json` in Claude Code 2.1.
printf '%s\n' "$ENTRY"
printf '%s' "$ENTRY" | jq -e 'has("enabled")' > /dev/null || fail "cannot determine load state"
printf '%s' "$ENTRY" | jq -e '.enabled == true and ((.errors // []) | length == 0)' > /dev/null \
  || fail "dopil@dopil is not loaded (entry above)"

SUPERPOWERS="$(printf '%s' "$LIST" | jq -r '.[] | select(.id | startswith("superpowers@")) | "\(.id) \(.version)"')"
[ -n "$SUPERPOWERS" ] || fail "no superpowers@ entry in claude plugin list --json: the dependency was not installed"

echo "superpowers: $SUPERPOWERS"
claude --version
echo "smoke_claude: OK"
