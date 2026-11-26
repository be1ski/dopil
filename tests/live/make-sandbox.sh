#!/usr/bin/env bash
# Create the live check kit's throwaway sandbox repository (tests/live/runner-brief.md).
# Usage: bash tests/live/make-sandbox.sh <target> <build> <superpowers>
#   <target>       a path that does not exist yet
#   <build>        an export of the dopil revision under test (runtimes.md, "Building an export")
#   <superpowers>  the superpowers plugin directory to install next to it for Antigravity
# The last stdout line is the base SHA. On any failure: non-zero, the partial target named on stderr, no marker.
set -euo pipefail

[ "$#" -eq 3 ] || { echo "usage: make-sandbox.sh <target> <build> <superpowers>" >&2; exit 2; }
T="$1"
BUILD="$2"
SUPERPOWERS="$3"
MARKER="$T/.dopil-live-sandbox"
# An inherited repository variable would point the git calls below at another repository.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR

if [ -e "$T" ] || [ -L "$T" ]; then
  echo "make-sandbox: refusing $T: it already exists" >&2
  exit 1
fi

mkdir -- "$T"
# The trap only reports: the marker appears by rename as the last step, so a failure never leaves one to clean up.
trap 'status=$?; [ "$status" -eq 0 ] || echo "make-sandbox: failed (exit $status); partial sandbox left at $T, without the marker" >&2' EXIT
mkdir "$T/wc" "$T/tests"
: > "$T/wc/__init__.py"
: > "$T/tests/__init__.py"
cat > "$T/wc/count.py" <<'PY'
import sys


def count(text):
    return {"lines": text.count("\n"), "words": len(text.split()), "chars": len(text)}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    with open(argv[0], encoding="utf-8") as f:
        result = count(f.read())
    print(result["lines"], result["words"], result["chars"])


if __name__ == "__main__":
    main()
PY
cat > "$T/tests/test_count.py" <<'PY'
import unittest

from wc.count import count


class CountTest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(count("a b\nc\n"), {"lines": 2, "words": 3, "chars": 6})


if __name__ == "__main__":
    unittest.main()
PY

git -C "$T" init -q
git -C "$T" add -A
git -C "$T" -c user.name=dopil-live -c user.email=dopil-live@invalid -c commit.gpgsign=false \
  -c core.hooksPath=/dev/null commit -q -m "Add a word counter"
SHA="$(git -C "$T" rev-parse HEAD)"

mkdir -p "$T/.git/info"
printf '%s\n' '/.claude/' '/.agents/' '/.dopil-live-sandbox' '__pycache__/' '*.pyc' >> "$T/.git/info/exclude"

# Claude Code sessions load the build with --plugin-dir; the installed dopil stays off in this project.
mkdir "$T/.claude"
printf '%s\n' '{' '  "enabledPlugins": {' '    "dopil@dopil": false' '  }' '}' > "$T/.claude/settings.json"

# Antigravity reads workspace plugins; "/." copies hidden files such as .antigravity-plugin/ too. A source's .git
# (an export is a git repository) is not part of the plugin and is dropped.
mkdir -p "$T/.agents/plugins/dopil" "$T/.agents/plugins/superpowers"
cp -R "$BUILD/." "$T/.agents/plugins/dopil"
cp -R "$SUPERPOWERS/." "$T/.agents/plugins/superpowers"
rm -rf "$T/.agents/plugins/dopil/.git" "$T/.agents/plugins/superpowers/.git"

# Verify before marking: a sandbox without the marker is never used.
diff -rq -x .git "$BUILD" "$T/.agents/plugins/dopil" >&2
diff -rq -x .git "$SUPERPOWERS" "$T/.agents/plugins/superpowers" >&2
for plugin in dopil superpowers; do
  [ ! -e "$T/.agents/plugins/$plugin/.git" ]
done
python3 -I -c 'import json, sys; assert json.load(open(sys.argv[1]))["enabledPlugins"]["dopil@dopil"] is False' \
  "$T/.claude/settings.json"
TESTS="$(cd "$T" && python3 -m unittest discover -s tests 2>&1)" || { printf '%s\n' "$TESTS" >&2; exit 1; }
for path in .claude/settings.json .agents/plugins .dopil-live-sandbox wc/__pycache__/count.pyc wc/count.pyc; do
  git -C "$T" check-ignore -q "$path"
done
# On its own line, so a failing status stops the script instead of reading as clean.
STATUS="$(git -C "$T" status --porcelain)"
[ -z "$STATUS" ]
[ "$(git -C "$T" rev-parse HEAD)" = "$SHA" ]

# The SHA first, then the marker by rename: a failure at any step leaves no marker, at most the temporary file.
echo "$SHA"
printf '%s\n' "$SHA" > "$MARKER.tmp"
mv -- "$MARKER.tmp" "$MARKER"
