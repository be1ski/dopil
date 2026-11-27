#!/usr/bin/env bash
# Install the plugin into an isolated Codex profile and assert the skill catalogue.
# Usage: bash tests/smoke_codex.sh [<plugin repo dir>]   (default: current directory)
# The temporary home is removed on exit.
set -euo pipefail

REPO="$(cd "${1:-.}" && pwd)"

# Every option references/agents/codex/reviewer.md passes still opens an option line of its subcommand's --help.
require_flags() {
  local flags="$1" help flag; shift
  help="$("$@" --help)"
  for flag in $flags; do
    grep -qE -- "^[[:space:]]*(-[A-Za-z], )?$flag([[:space:],=<[]|\$)" <<<"$help" \
      || { echo "smoke_codex: '$*' no longer lists $flag" >&2; exit 1; }
  done
}
require_flags "-s -c --skip-git-repo-check --model --json -o" codex exec
require_flags "--model -c --json -o" codex exec review
require_flags "--skip-git-repo-check --model -c -o" codex exec resume
H="$(mktemp -d)"
trap 'rm -rf "$H"' EXIT
# CODEX_HOME alone still reads ~/.agents/skills, so HOME is overridden too.
export HOME="$H"
export CODEX_HOME="$H/.codex"
mkdir -p "$CODEX_HOME"

codex plugin marketplace add "$REPO"
codex plugin add dopil@dopil
codex debug prompt-input hi > "$H/prompt.txt"

# The catalogue lines sit inside JSON strings with escaped newlines: decode before matching.
python3 - "$H/prompt.txt" <<'PY'
import json
import re
import sys


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


raw = open(sys.argv[1], encoding="utf-8").read()
try:
    text = "\n".join(strings(json.loads(raw)))
except ValueError:
    text = raw
for name, pattern, present in [("dopil:dopil", r"^- dopil:dopil: ", True),
                               ("dopil:pragmatic-engineering", r"^- dopil:pragmatic-engineering: ", True),
                               ("no plain dopil entry", r"^- dopil: ", False)]:
    if bool(re.search(pattern, text, re.MULTILINE)) != present:
        sys.exit("smoke_codex: assertion failed: " + name)
PY

fail() { echo "smoke_codex: $*" >&2; exit 1; }
set -- "$CODEX_HOME"/plugins/cache/dopil/dopil/*/
[ "$#" -eq 1 ] && [ -d "$1" ] || fail "expected one installed copy, found: $*"
INSTALLED="$1"
# Every file git tracks under skills/ is in the installed copy.
env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_OBJECT_DIRECTORY -u GIT_COMMON_DIR \
  git -C "$REPO" ls-files -z skills > "$H/tracked"
[ -s "$H/tracked" ] || fail "git ls-files lists no file under skills/ in $REPO"
while IFS= read -r -d '' rel; do
  [ -f "$INSTALLED/$rel" ] || fail "missing $rel under $INSTALLED"
done < "$H/tracked"
codex --version
echo "smoke_codex: OK"
