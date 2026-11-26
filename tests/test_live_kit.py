"""Check the live check kit: the sandbox script end to end, and that the case and launch tables are complete."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "tests" / "live"
SCRIPT = LIVE / "make-sandbox.sh"
MARKER = ".ship-live-sandbox"
EXCLUDES = ["/.claude/", "/.agents/", "/" + MARKER, "__pycache__/", "*.pyc"]
GROUPS = ["A", "B", "C", "D", "D3", "E", "R", "F", "H", "I1", "I2"]
# The groups the baseline cannot run (spec, "Verification", step 3): their instances, and only those, are after-only.
AFTER_ONLY_GROUPS = {"D3", "H", "I1", "I2"}
# The case ids of the previous route's sandbox matrix; each maps to new instances or, for G1, to a disposition.
PREVIOUS_IDS = (["A%d" % n for n in range(1, 11)] + ["B1", "B2", "C1", "C2", "C3", "C4", "D1", "D2"]
                + ["E%d" % n for n in range(1, 8)] + ["F1", "F2", "G1"])
VARIANTS = ["Claude Code", "Codex", "Kimi Code", "Antigravity on a Gemini model", "Antigravity on a non-Gemini model"]
# Agents load these as directory instructions; on a case-insensitive filesystem any spelling matches.
INSTRUCTION_FILES = {"agents.md", "claude.md", "gemini.md"}
# An instance line `Request: <name> + <name>` or `Request (<when>): …`, names from the Inputs table.
REQUEST = re.compile(r"^Request(?: \([^)]*\))?: (.+)$", re.M)


def run(args, env, cwd=None):
    return subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)


def section(text, heading):
    return text.split("\n## " + heading + "\n", 1)[1].split("\n## ", 1)[0]


def table_rows(text, heading):
    """First cells of the table under a `## <heading>` section."""
    rows = [line for line in section(text, heading).splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


def instance_bodies(cases):
    """The text of each `### <id> · <tag>` instance, up to the next heading."""
    parts = re.split(r"^(#{2,3} .*)$", cases, flags=re.M)
    bodies = {}
    for heading, body in zip(parts[1::2], parts[2::2]):
        match = re.match(r"### (\S+) · ", heading)
        if match:
            bodies[match.group(1)] = body
    return bodies


def requests(body):
    return [line.split(" + ") for line in REQUEST.findall(body)]


class SandboxTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
        self.target = self.root / "sandbox"
        self.build = self.fake_plugin("build")
        self.superpowers = self.fake_plugin("superpowers")

    def fake_plugin(self, name):
        path = self.root / name
        (path / ".antigravity-plugin").mkdir(parents=True)
        (path / "visible.txt").write_text(name + "\n", encoding="utf-8")
        (path / ".antigravity-plugin" / "plugin.json").write_text('{"name": "%s"}\n' % name, encoding="utf-8")
        (path / ".git").mkdir()
        (path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        return path

    def make(self, superpowers=None, target=None, env=None):
        return run(["bash", str(SCRIPT), str(target or self.target), str(self.build),
                    str(superpowers or self.superpowers)], env or self.env)

    def git(self, *args):
        result = run(["git", "-C", str(self.target)] + list(args), self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_make_sandbox_builds_marked_repo(self):
        result = self.make()
        self.assertEqual(result.returncode, 0, result.stderr)
        sha = result.stdout.splitlines()[-1]
        self.assertEqual(sha, self.git("rev-parse", "HEAD").strip())
        self.assertEqual(self.git("log", "-1", "--format=%an <%ae>").strip(), "ship-live <ship-live@invalid>")
        self.assertEqual((self.target / MARKER).read_text(encoding="utf-8"), sha + "\n")
        tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], self.env, cwd=str(self.target))
        self.assertEqual(tests.returncode, 0, tests.stderr)
        self.assertEqual(self.git("status", "--porcelain"), "")
        settings = json.loads((self.target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIs(settings["enabledPlugins"]["ship@ship"], False)
        for name, source in (("ship", self.build), ("superpowers", self.superpowers)):
            installed = self.target / ".agents" / "plugins" / name
            for rel in ("visible.txt", ".antigravity-plugin/plugin.json"):
                self.assertEqual((installed / rel).read_text(encoding="utf-8"),
                                 (source / rel).read_text(encoding="utf-8"), "%s/%s" % (name, rel))
            self.assertFalse((installed / ".git").exists(), "%s: the source's .git was copied" % name)
        excludes = (self.target / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
        for pattern in EXCLUDES:
            self.assertIn(pattern, excludes)

    def test_make_sandbox_refuses_existing_target(self):
        self.target.mkdir()
        (self.target / "keep.txt").write_text("keep\n", encoding="utf-8")
        result = self.make()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing " + str(self.target), result.stderr)
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ["keep.txt"])
        self.assertEqual((self.target / "keep.txt").read_text(encoding="utf-8"), "keep\n")

    def test_make_sandbox_failure_leaves_no_marker(self):
        result = self.make(superpowers=self.root / "missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(self.root / "missing"), result.stderr)  # the failing command's own error is kept
        self.assertIn("partial sandbox left at " + str(self.target), result.stderr)
        self.assertFalse((self.target / MARKER).exists())

    def test_make_sandbox_failed_mkdir_claims_no_partial_sandbox(self):
        result = self.make(target=self.root / "no-parent" / "sandbox")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(self.root / "no-parent"), result.stderr)  # mkdir's own error
        self.assertNotIn("partial sandbox", result.stderr)

    def test_make_sandbox_unprinted_sha_leaves_no_marker(self):
        # stdout closed: printing the SHA fails, so the sandbox must stay unmarked.
        result = run(["bash", "-c", 'exec bash "$0" "$@" >&-', str(SCRIPT), str(self.target), str(self.build),
                      str(self.superpowers)], self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("partial sandbox left at " + str(self.target), result.stderr)
        self.assertFalse((self.target / MARKER).exists())

    def test_make_sandbox_failed_marker_write_leaves_no_marker(self):
        # The marker's temporary file is created and written, then the write reports failure, as a full disk would.
        # The script prints the SHA with printf only into that file, so this printf fails there and nowhere else.
        bash_env = self.root / "bash-env"
        bash_env.write_text('printf() { builtin printf "$@"; [ "$#" -ne 2 ] || [ "$2" != "${SHA:-}" ] || return 5; }\n',
                            encoding="utf-8")
        result = self.make(env=dict(self.env, BASH_ENV=str(bash_env)))
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertIn("failed (exit 5); partial sandbox left at %s, without the marker" % self.target, result.stderr)
        self.assertFalse((self.target / MARKER).exists())

    def test_make_sandbox_stops_when_git_status_fails(self):
        # A git that fails only for `status`: the clean check must stop the script, not pass as clean.
        real, fake = shutil.which("git"), self.root / "fake-bin"
        fake.mkdir()
        (fake / "git").write_text('#!/bin/sh\n[ "$3" = status ] && exit 7\nexec "%s" "$@"\n' % real, encoding="utf-8")
        (fake / "git").chmod(0o755)
        env = dict(self.env, PATH="%s%s%s" % (fake, os.pathsep, self.env["PATH"]))
        result = self.make(env=env)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse((self.target / MARKER).exists())

    def test_make_sandbox_ignores_inherited_git_variables(self):
        other = self.root / "other"
        self.assertEqual(run(["git", "init", "-q", str(other)], self.env).returncode, 0)
        git_dir = other / ".git"
        env = dict(self.env, GIT_DIR=str(git_dir), GIT_WORK_TREE=str(other), GIT_INDEX_FILE=str(git_dir / "index"),
                   GIT_OBJECT_DIRECTORY=str(git_dir / "objects"), GIT_COMMON_DIR=str(git_dir))
        result = self.make(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[-1], self.git("rev-parse", "HEAD").strip())
        inherited = run(["git", "-C", str(other), "rev-parse", "--verify", "-q", "HEAD"], self.env)
        self.assertNotEqual(inherited.returncode, 0, "the sandbox commit went into the inherited repository")


class KitTest(unittest.TestCase):
    def test_kit_covers_cases_and_variants(self):
        cases = (LIVE / "cases.md").read_text(encoding="utf-8")
        groups = re.findall(r"^## Group (\S+): ", cases, re.M)
        self.assertEqual(groups, GROUPS)
        instances = {}
        for group, body in zip(groups, re.split(r"^## Group \S+: .*$", cases, flags=re.M)[1:]):
            headings = re.findall(r"^### (.+)$", body.split("\n## ", 1)[0], re.M)
            self.assertTrue(headings, "group %s has no instance" % group)
            for heading in headings:
                match = re.match(r"(\S+) · (\S+)$", heading)
                self.assertTrue(match, "untagged instance: %s" % heading)
                self.assertEqual(match.group(2), "after-only" if group in AFTER_ONLY_GROUPS else "baseline", heading)
                self.assertNotIn(match.group(1), instances, "duplicate instance id")
                instances[match.group(1)] = match.group(2)
        mapping = table_rows(cases, "Previous case ids")
        self.assertEqual(sorted(row[0] for row in mapping), sorted(PREVIOUS_IDS))
        for row in mapping:
            named = re.findall(r"`([^`]+)`", row[1])
            if row[0] == "G1":
                self.assertTrue(row[1].startswith("not instantiated"), row[1])
            else:
                self.assertTrue(named and all(name in instances for name in named), row)
        runtimes = (LIVE / "runtimes.md").read_text(encoding="utf-8")
        self.assertEqual([row[0] for row in table_rows(runtimes, "Launch variants")], VARIANTS)

    def test_cases_type_only_the_request_texts_of_inputs(self):
        cases = (LIVE / "cases.md").read_text(encoding="utf-8")
        defined = {row[0].strip("`") for row in table_rows(cases, "Inputs")}
        for name, body in instance_bodies(cases).items():
            if not name.startswith("I1-"):  # I1 runs inside A instances
                self.assertTrue(requests(body), "%s names no request" % name)
            for names in requests(body):
                self.assertTrue(set(names) <= defined, "%s: %s" % (name, names))
        before, rest = cases.split("\n## Inputs\n", 1)
        outside = before + rest.split("\n## ", 1)[1]
        for phrase in ("Review by", " in parallel"):
            self.assertNotIn(phrase, outside, "a request text typed outside Inputs")

    def test_h_separates_the_line_and_the_row(self):
        bodies = instance_bodies((LIVE / "cases.md").read_text(encoding="utf-8"))
        line, row = bodies["H-missing-key-line"], bodies["H-missing-key-row"]
        self.assertIn(["T1", "BY-CODEX-KIMI"], requests(line))
        self.assertEqual(requests(row), [["RESUME"]])
        # The row's fixture: a line without kimi, and an open gate locked to codex and kimi.
        self.assertIn("Reviewers: codex\\n", row)
        self.assertIn("codex, kimi (locked at r01)", row)
        # The line case proves no row was locked; both keep the saved set, and the row case its State cell too.
        self.assertIn("locked no row", line)
        for body in (line, row):
            self.assertNotIn("`gates.md` unchanged", body)
            self.assertNotIn("`gates.md` as session 1 left it", body)
            self.assertIn("the saved set unchanged", body)

    def test_runner_brief_resets_by_short_refnames(self):
        # `branch -D` and `checkout` need short names; `checkout refs/heads/x` detaches HEAD with exit 0.
        brief = (LIVE / "runner-brief.md").read_text(encoding="utf-8")
        for short in ("%(refname:short)", "symbolic-ref -q --short HEAD"):
            self.assertTrue(short in brief, "missing: " + short)
        for full in ("%(refname)", "symbolic-ref -q HEAD", "checkout -q -f refs/heads"):
            self.assertFalse(full in brief, "full refname used: " + full)

    def test_agy_loading_keeps_global_plugin(self):
        runtimes = (LIVE / "runtimes.md").read_text(encoding="utf-8")
        row = [r for r in table_rows(runtimes, "Loading") if r[0] == "Antigravity"][0]
        for cell in row:
            self.assertFalse("agy plugin disable" in cell or "agy plugin enable" in cell, cell)
        self.assertTrue("disabled" in row[2] and "workspace" in row[2], row[2])

    def test_build_proof_probes_agy_registration(self):
        proof = section((LIVE / "runner-brief.md").read_text(encoding="utf-8"), "Build proof, every case")
        for needle in ("/ship:sh", "slash-probe.txt", "/ship:ship", "NOT RUN"):
            self.assertTrue(needle in proof, "missing: " + needle)

    def test_runner_scratch_is_own(self):
        self.assertTrue("scratch" in section((LIVE / "runner-brief.md").read_text(encoding="utf-8"), "Hard rules"))

    def test_kit_has_no_instruction_file_names(self):
        names = [path.relative_to(LIVE).as_posix() for path in LIVE.rglob("*")
                 if path.name.lower() in INSTRUCTION_FILES]
        self.assertEqual(names, [])


if __name__ == "__main__":
    unittest.main()
