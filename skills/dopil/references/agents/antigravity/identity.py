"""Print the Antigravity session's current model and its vendor, or one BLOCKER line and exit 1.

Run as `python3 -I identity.py`. The model is the latest planner step of the conversation's last user turn.
"""

import json
import os
import sys


def stop(message):
    print("BLOCKER:", message)
    sys.exit(1)


if not os.environ.get("ANTIGRAVITY_AGENT"):
    stop("not an Antigravity session")
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
