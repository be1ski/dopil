"""Print the Kimi Code session's model alias and its provider type, or one BLOCKER line and exit 1.

Run as `python3 -I identity.py [agent id]`; the agent id is `main` unless given (a coder subagent's
`agent_id`). Never prints the output of `kimi provider list --json`: it carries credentials.
"""

import glob
import json
import os
import shutil
import subprocess
import sys


def stop(message):
    print("BLOCKER:", message)
    sys.exit(1)


if len(sys.argv) > 2:
    stop("more than one argument; usage: identity.py [agent id]")
agent = sys.argv[1] if len(sys.argv) == 2 else "main"
kp = shutil.which("kimi")
if not kp:
    stop("no kimi executable in PATH")
home = os.environ.get("KIMI_CODE_HOME")
if not home:
    if not os.environ.get("HOME"):
        stop("neither KIMI_CODE_HOME nor HOME is set")
    home = os.path.join(os.environ["HOME"], ".kimi-code")
sid = os.environ.get("KIMI_CODE_SESSION_ID")
if not sid:
    stop("not a Kimi Code session")
config = os.path.join(home, "config.toml")
if not (os.path.isfile(config) and os.path.getsize(config) > 0):
    stop("Kimi Code is not set up")
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
    result = subprocess.run([kp, "provider", "list", "--json"], capture_output=True, text=True,
                            env=dict(os.environ, KIMI_CODE_HOME=home))
except OSError as error:
    stop("cannot run kimi provider list: %s" % error.strerror)
if result.returncode != 0:
    stop("kimi provider list exited %d" % result.returncode)
try:
    data = json.loads(result.stdout)
    kind = data["providers"][data["models"][alias]["provider"]]["type"]
except (ValueError, KeyError, TypeError):
    kind = None
if not isinstance(kind, str) or kind.splitlines() != [kind]:  # a non-empty single line of text
    stop("alias %s has no readable provider type" % alias)
print("ALIAS:", alias)
print("PROVIDER TYPE:", kind)  # never print the JSON: it carries credentials
