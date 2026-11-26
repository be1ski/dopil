"""Run the Kimi Code and Antigravity identity scripts against fake sessions, as the cards run them."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


AGENTS = Path(__file__).resolve().parent.parent / "skills/dopil/references/agents"
KIMI = AGENTS / "kimi/identity.py"
ANTIGRAVITY = AGENTS / "antigravity/identity.py"
SECRET = "SECRET-123"
SESSION = "session_s1"


class ScriptCase(unittest.TestCase):
    """A temporary HOME and a fake bin directory; no real kimi or agy is on PATH."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.tmp))
        self.bin = self.tmp / "bin"
        self.home = self.tmp / "home"
        self.bin.mkdir()
        self.home.mkdir()

    def run_script(self, script, env, *args):
        """Run the script under -I with only PATH, HOME and the case's variables; None removes one."""
        full = {"PATH": "%s:/usr/bin:/bin" % self.bin, "HOME": str(self.home)}
        full.update(env)
        full = {name: value for name, value in full.items() if value is not None}
        result = subprocess.run([sys.executable, "-I", str(script)] + list(args), env=full,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertNotIn(SECRET, result.stdout)
        self.assertNotIn(SECRET, result.stderr)
        return result

    def assert_prints(self, result, lines, status):
        self.assertEqual((result.stdout, result.returncode), ("".join(line + "\n" for line in lines), status),
                         result.stderr)


def jsonl(events, final_newline=True):
    text = "\n".join(event if isinstance(event, str) else json.dumps(event) for event in events)
    return text + "\n" if final_newline else text


def bind(alias):
    return {"type": "profile.bind", "modelAlias": alias}


class KimiIdentityTest(ScriptCase):
    def setUp(self):
        super().setUp()
        self.kimi_home = self.tmp / "kimi-home"
        self.make_home(self.kimi_home)
        self.fake_kimi(self.kimi_home)
        self.env = {"KIMI_CODE_HOME": str(self.kimi_home), "KIMI_CODE_SESSION_ID": SESSION}

    def make_home(self, home):
        home.mkdir(parents=True)
        (home / "config.toml").write_text("[models]\n")
        self.write_wire(home, "main", jsonl([{"type": "turn.begin"}, bind("kimi-x"), {"type": "turn.end"}]))
        self.write_wire(home, "agent-0", jsonl([bind("kimi-z")]))

    def write_wire(self, home, agent, text, top="s1"):
        path = home / "sessions" / top / SESSION / "agents" / agent / "wire.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def fake_kimi(self, expected_home, kind="kimi", status=0):
        """A kimi that requires KIMI_CODE_HOME and prints provider JSON carrying a credential."""
        data = {"providers": {"p1": {"type": kind, "api_key": SECRET}},
                "models": {"kimi-x": {"provider": "p1"}, "kimi-z": {"provider": "p1"}}}
        path = self.bin / "kimi"
        path.write_text("#!/bin/sh\n"
                        '[ "$KIMI_CODE_HOME" = \'%s\' ] || exit 9\n'
                        '[ "$*" = "provider list --json" ] || exit 8\n'
                        "echo 'api_key: %s' >&2\n"
                        "printf '%%s\\n' '%s'\n"
                        "exit %d\n" % (expected_home, SECRET, json.dumps(data), status))
        path.chmod(0o755)

    def assert_blocker(self, message, env=None, args=()):
        merged = dict(self.env)
        merged.update(env or {})
        self.assert_prints(self.run_script(KIMI, merged, *args), ["BLOCKER: " + message], 1)

    def test_prints_alias_and_provider_type(self):
        self.assert_prints(self.run_script(KIMI, self.env), ["ALIAS: kimi-x", "PROVIDER TYPE: kimi"], 0)

    def test_default_home_is_used_and_forwarded(self):
        default = self.home / ".kimi-code"
        self.make_home(default)
        self.fake_kimi(default)
        self.env["KIMI_CODE_HOME"] = None
        self.assert_prints(self.run_script(KIMI, self.env), ["ALIAS: kimi-x", "PROVIDER TYPE: kimi"], 0)

    def test_other_provider_type_is_printed(self):
        self.fake_kimi(self.kimi_home, kind="openai")
        self.assert_prints(self.run_script(KIMI, self.env), ["ALIAS: kimi-x", "PROVIDER TYPE: openai"], 0)

    def test_agent_argument_reads_that_agents_wire_log(self):
        self.assert_prints(self.run_script(KIMI, self.env, "agent-0"), ["ALIAS: kimi-z", "PROVIDER TYPE: kimi"], 0)

    def test_final_line_without_newline_is_read(self):
        self.write_wire(self.kimi_home, "main", jsonl([bind("kimi-x"), bind("kimi-z")], final_newline=False))
        self.assert_prints(self.run_script(KIMI, self.env), ["ALIAS: kimi-z", "PROVIDER TYPE: kimi"], 0)

    def test_final_fragment_is_ignored(self):
        self.write_wire(self.kimi_home, "main", jsonl([bind("kimi-x"), '{"type": "profile.bi'], final_newline=False))
        self.assert_prints(self.run_script(KIMI, self.env), ["ALIAS: kimi-x", "PROVIDER TYPE: kimi"], 0)

    def test_extra_arguments_block(self):
        self.assert_blocker("more than one argument; usage: identity.py [agent id]", args=("agent-0", "main"))

    def test_no_kimi_on_path_blocks(self):
        (self.bin / "kimi").unlink()
        self.assert_blocker("no kimi executable in PATH")

    def test_no_kimi_home_and_no_home_blocks(self):
        self.assert_blocker("neither KIMI_CODE_HOME nor HOME is set", env={"KIMI_CODE_HOME": None, "HOME": None})

    def test_no_session_blocks(self):
        self.assert_blocker("not a Kimi Code session", env={"KIMI_CODE_SESSION_ID": None})

    def test_missing_config_blocks(self):
        (self.kimi_home / "config.toml").unlink()
        self.assert_blocker("Kimi Code is not set up")

    def test_empty_config_blocks(self):
        (self.kimi_home / "config.toml").write_text("")
        self.assert_blocker("Kimi Code is not set up")

    def test_no_wire_log_blocks(self):
        self.assert_blocker("no single wire log for agent agent-7", args=("agent-7",))

    def test_two_wire_logs_block(self):
        self.write_wire(self.kimi_home, "main", jsonl([bind("kimi-x")]), top="s2")
        self.assert_blocker("no single wire log for agent main")

    def test_unreadable_wire_log_blocks(self):
        path = self.write_wire(self.kimi_home, "agent-1", "")
        path.unlink()
        path.mkdir()
        self.assert_blocker("cannot read the wire log: Is a directory", args=("agent-1",))

    def test_malformed_middle_line_blocks(self):
        self.write_wire(self.kimi_home, "main", jsonl([bind("kimi-x"), "not json", bind("kimi-x")]))
        self.assert_blocker("wire log line 2 is not JSON")

    def test_no_binding_blocks(self):
        self.write_wire(self.kimi_home, "main", jsonl([{"type": "turn.begin"}]))
        self.assert_blocker("no model binding in the wire log")

    def test_failing_provider_list_blocks(self):
        self.fake_kimi(self.kimi_home, status=3)
        self.assert_blocker("kimi provider list exited 3")

    def test_alias_without_provider_type_blocks(self):
        self.write_wire(self.kimi_home, "main", jsonl([bind("kimi-q")]))
        self.assert_blocker("alias kimi-q has no readable provider type")

    def test_provider_type_that_is_not_one_line_of_text_blocks(self):
        for kind in [None, "", "kimi\nopenai", {"api_key": SECRET}]:
            with self.subTest(kind=kind):
                self.fake_kimi(self.kimi_home, kind=kind)
                self.assert_blocker("alias kimi-x has no readable provider type")


def user():
    return {"type": "USER_INPUT"}


def planner(model):
    return {"type": "PLANNER_RESPONSE", "model": model}


class AntigravityIdentityTest(ScriptCase):
    def setUp(self):
        super().setUp()
        data = self.tmp / "agy-data"
        self.transcript = data / "brain" / "conv-1" / ".system_generated" / "logs" / "transcript.jsonl"
        self.transcript.parent.mkdir(parents=True)
        self.env = {"ANTIGRAVITY_AGENT": "1", "ANTIGRAVITY_APP_DATA_DIR": str(data),
                    "ANTIGRAVITY_CONVERSATION_ID": "conv-1"}

    def prints(self, text, lines, status=0, env=None):
        self.transcript.write_text(text)
        merged = dict(self.env)
        merged.update(env or {})
        self.assert_prints(self.run_script(ANTIGRAVITY, merged), lines, status)

    def test_vendor_by_family(self):
        for model, vendor in [("gemini-x", "Google"), ("claude-x", "Anthropic"), ("gpt-x", "OpenAI")]:
            with self.subTest(model=model):
                self.prints(jsonl([user(), planner(model)]), ["MODEL: " + model, "VENDOR: " + vendor])

    def test_latest_step_of_the_last_turn_wins(self):
        steps = [user(), planner("claude-x"), user(), planner("gpt-x"), planner("gemini-x"),
                 planner("gemini-pro-orchestrator-x")]
        self.prints(jsonl(steps), ["MODEL: gemini-x", "VENDOR: Google"])

    def test_final_line_without_newline_is_read(self):
        self.prints(jsonl([user(), planner("claude-x"), planner("gemini-x")], final_newline=False),
                    ["MODEL: gemini-x", "VENDOR: Google"])

    def test_final_fragment_is_ignored(self):
        self.prints(jsonl([user(), planner("claude-x"), '{"type": "PLANNER_RESP'], final_newline=False),
                    ["MODEL: claude-x", "VENDOR: Anthropic"])

    def test_no_agent_blocks(self):
        self.prints(jsonl([user(), planner("gemini-x")]), ["BLOCKER: not an Antigravity session"], 1,
                    env={"ANTIGRAVITY_AGENT": None})

    def test_no_conversation_blocks(self):
        for name in ["ANTIGRAVITY_APP_DATA_DIR", "ANTIGRAVITY_CONVERSATION_ID"]:
            with self.subTest(missing=name):
                self.prints(jsonl([user(), planner("gemini-x")]),
                            ["BLOCKER: no Antigravity conversation in the environment"], 1, env={name: None})

    def test_unreadable_transcript_blocks(self):
        self.env["ANTIGRAVITY_CONVERSATION_ID"] = "conv-2"
        missing = Path(self.env["ANTIGRAVITY_APP_DATA_DIR"], "brain", "conv-2", ".system_generated", "logs",
                       "transcript.jsonl")
        self.prints("", ["BLOCKER: cannot read the transcript: [Errno 2] No such file or directory: '%s'" % missing],
                    1)

    def test_malformed_middle_line_blocks(self):
        self.prints(jsonl([user(), "not json", planner("gemini-x")]), ["BLOCKER: transcript line 2 is not JSON"], 1)

    def test_no_user_turn_blocks(self):
        self.prints(jsonl([planner("gemini-x")]), ["BLOCKER: no user turn in the transcript"], 1)

    def test_no_model_step_blocks(self):
        for steps in [[planner("gemini-x"), user()], [user(), planner("gemini-pro-orchestrator-x")]]:
            with self.subTest(steps=steps):
                self.prints(jsonl(steps), ["BLOCKER: no model step in the current turn"], 1)

    def test_unknown_family_blocks(self):
        self.prints(jsonl([user(), planner("llama-x")]), ["BLOCKER: unknown model family: llama-x"], 1)


if __name__ == "__main__":
    unittest.main()
