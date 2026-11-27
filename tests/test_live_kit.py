"""Check the live kit's sandbox script, case M's layout block and the guard before case M's delete."""

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
MIGRATE = ROOT / "skills" / "dopil" / "references" / "migrate.py"
MARKER = ".dopil-live-sandbox"
OLD = "ship"  # the previous plugin's name
# Paths the sandbox must keep out of git; CPython writes a cache through a temporary `<cache>.pyc.<id>` file.
IGNORED = [".claude/settings.json", ".agents/plugins", MARKER, "wc/__pycache__/count.cpython-38.pyc.1", "wc/count.pyc"]


def run(args, env, cwd=None):
    return subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)


def section(text, heading):
    return text.split("\n## " + heading + "\n", 1)[1].split("\n## ", 1)[0]


def m_group():
    return (LIVE / "cases.md").read_text(encoding="utf-8").split("\n## Group M: ", 1)[1].split("\n## ", 1)[0]


def m_brief():
    """The case M paragraph of the runner brief's "After each case"."""
    brief = (LIVE / "runner-brief.md").read_text(encoding="utf-8")
    return section(brief, "After each case, pass or fail").split("\nCase M ", 1)[1].split("\n\n", 1)[0]


def m_layout_block():
    """The one bash block of group M: it writes the old layout into `$MSB`."""
    blocks = re.findall(r"^```bash\n(.*?)^```$", m_group(), re.M | re.S)
    assert len(blocks) == 1, "case M writes its old layout in one block"
    return blocks[0]


def snapshot(root):
    """Every path under root with its bytes, a directory as None."""
    return {path: None if path.is_dir() else path.read_bytes() for path in sorted(Path(root).rglob("*"))}


def tree(root):
    """Every file under root but its .git, by relative path, with its bytes."""
    return {path.relative_to(root): path.read_bytes() for path in Path(root).rglob("*")
            if path.is_file() and ".git" not in path.relative_to(root).parts}


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
        self.assertEqual((self.target / MARKER).read_text(encoding="utf-8"), sha + "\n")
        tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], self.env, cwd=str(self.target))
        self.assertEqual(tests.returncode, 0, tests.stderr)
        self.assertRegex(tests.stderr, r"(?m)^Ran [1-9][0-9]* tests? in ", "the sandbox's own tests are not found")
        self.assertEqual(self.git("status", "--porcelain"), "")
        settings = json.loads((self.target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIs(settings["enabledPlugins"]["dopil@dopil"], False)
        for name, source in (("dopil", self.build), ("superpowers", self.superpowers)):
            installed = self.target / ".agents" / "plugins" / name
            self.assertEqual(tree(installed), tree(source), name)
            self.assertFalse((installed / ".git").exists(), "%s: the source's .git was copied" % name)
        for path in IGNORED:
            ignored = run(["git", "-C", str(self.target), "check-ignore", "-q", path], self.env)
            self.assertEqual(ignored.returncode, 0, "%s is not ignored" % path)

    def test_make_sandbox_refuses_existing_target(self):
        self.target.mkdir()
        (self.target / "keep.txt").write_text("keep\n", encoding="utf-8")
        result = self.make()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing " + str(self.target), result.stderr)
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ["keep.txt"])
        self.assertEqual((self.target / "keep.txt").read_text(encoding="utf-8"), "keep\n")

    def test_make_sandbox_failure_leaves_no_marker(self):
        # A failing step, a closed stdout, a failed marker write or a failed git status leaves the sandbox unmarked.
        real, fake = shutil.which("git"), self.root / "fake-bin"
        fake.mkdir()
        (fake / "git").write_text('#!/bin/sh\n[ "$3" = status ] && exit 7\nexec "%s" "$@"\n' % real, encoding="utf-8")
        (fake / "git").chmod(0o755)
        bash_env = self.root / "bash-env"
        bash_env.write_text('printf() { builtin printf "$@"; [ "$#" -ne 2 ] || [ "$2" != "${SHA:-}" ] || return 5; }\n',
                            encoding="utf-8")
        with self.subTest("a failing step"):
            target = self.root / "failing-step"
            result = self.make(superpowers=self.root / "missing", target=target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(self.root / "missing"), result.stderr)
            self.assertIn("partial sandbox left at " + str(target), result.stderr)
            self.assertFalse((target / MARKER).exists())
        with self.subTest("stdout closed, so the SHA is not printed"):
            target = self.root / "closed-stdout"
            result = run(["bash", "-c", 'exec bash "$0" "$@" >&-', str(SCRIPT), str(target), str(self.build),
                          str(self.superpowers)], self.env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("partial sandbox left at " + str(target), result.stderr)
            self.assertFalse((target / MARKER).exists())
        with self.subTest("the marker write fails"):
            target = self.root / "marker-write"
            result = self.make(target=target, env=dict(self.env, BASH_ENV=str(bash_env)))
            self.assertEqual(result.returncode, 5, result.stderr)
            self.assertIn("failed (exit 5); partial sandbox left at %s, without the marker" % target, result.stderr)
            self.assertFalse((target / MARKER).exists())
        with self.subTest("git status fails"):
            target = self.root / "git-status"
            result = self.make(target=target, env=dict(self.env, PATH="%s%s%s" % (fake, os.pathsep, self.env["PATH"])))
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertFalse((target / MARKER).exists())

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

    def test_m_old_layout_plans_the_move(self):
        # Case M's old route, written under a foreign git environment, lands in its sandbox alone and plans the move.
        self.assertEqual(self.make().returncode, 0)
        other = self.root / "other"
        self.assertEqual(run(["git", "init", "-q", str(other)], self.env).returncode, 0)
        git_dir = other / ".git"
        foreign = dict(self.env, MSB=str(self.target), GIT_DIR=str(git_dir), GIT_WORK_TREE=str(other),
                       GIT_INDEX_FILE=str(git_dir / "index"), GIT_OBJECT_DIRECTORY=str(git_dir / "objects"),
                       GIT_COMMON_DIR=str(git_dir))
        before = snapshot(other)
        layout = run(["bash", "-c", m_layout_block()], foreign)
        self.assertEqual(layout.returncode, 0, layout.stderr)
        self.assertEqual(snapshot(other), before, "the block wrote into the inherited repository")
        pointer = self.target / ".git" / (OLD + "-routes") / "2026-11-20-usage.txt"
        self.assertTrue(pointer.is_file(), "the pointer is not in the sandbox's own git dir")
        base = (self.target / ("." + OLD) / "2026-11-20-usage" / "code-01" / "base-sha").read_text(encoding="utf-8")
        self.assertEqual(base, self.git("rev-parse", "HEAD"))
        check = run([sys.executable, "-I", str(MIGRATE), "check"], self.env, cwd=str(self.target))
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        lines = check.stdout.splitlines()
        self.assertEqual(len([line for line in lines if line.startswith("MOVE ")]), 3, check.stdout)
        restart = [line for line in lines if line.startswith("RESTART-LATER ")]
        self.assertEqual(len(restart), 1, check.stdout)
        self.assertTrue(restart[0].startswith("RESTART-LATER %s/.dopil/" % self.target), restart[0])
        self.assertTrue(restart[0].endswith("/gates.md: code-01"), restart[0])
        self.assertFalse([line for line in lines if line.startswith("LEAVE ")], check.stdout)
        self.assertEqual(self.git("status", "--porcelain"), "", "the old layout is ignored")

    def test_m_old_layout_refuses_an_unmarked_target(self):
        # The block writes nothing unless MSB is the absolute path of a marked standalone sandbox.
        self.assertEqual(self.make().returncode, 0)
        other = self.root / "other"
        self.assertEqual(run(["git", "init", "-q", str(other)], self.env).returncode, 0)
        linked = self.root / "linked"
        self.git("worktree", "add", "-q", "--detach", str(linked))
        (linked / MARKER).write_text(self.git("rev-parse", "HEAD"), encoding="utf-8")
        unset = {name: value for name, value in self.env.items() if name != "MSB"}
        for env, cwd in ((unset, self.target), (dict(self.env, MSB=str(other)), self.root),
                         (dict(self.env, MSB=self.target.name), self.root),
                         (dict(self.env, MSB=str(linked)), self.root)):
            before = snapshot(self.root)
            result = run(["bash", "-c", m_layout_block()], env, cwd=str(cwd))
            self.assertNotEqual(result.returncode, 0, env.get("MSB"))
            self.assertEqual(snapshot(self.root), before, "written for MSB=%s" % env.get("MSB"))


class KitTest(unittest.TestCase):
    def test_m_delete_guard_needs_the_marker_and_a_sha(self):
        # The guard before case M's rm -rf passes only for a sandbox marked with MBASE, a SHA, that is not SB.
        case_m = " ".join(m_brief().split())
        guards = re.findall(r"`(marker=[^`]*)`", case_m)
        self.assertEqual(len(guards), 1, case_m)
        self.assertNotIn("rm ", guards[0])
        self.assertEqual(re.findall(r"`(rm -rf [^`]+)`", case_m), ['rm -rf "$MSB"'], "the delete targets MSB alone")
        sha = "0123456789abcdef0123456789abcdef01234567"
        with tempfile.TemporaryDirectory() as temp:
            for name, marker, mbase, same, passes in [
                    ("marked with its base", sha, sha, False, True),
                    ("no marker, MBASE empty", None, "", False, False),
                    ("empty marker, MBASE empty", "", "", False, False),
                    ("a base that is not a SHA", "base", "base", False, False),
                    ("another valid SHA as MBASE", sha, sha[::-1], False, False),
                    ("the kit's sandbox", sha, sha, True, False)]:
                with self.subTest(name):
                    msb = Path(temp) / name.replace(" ", "-").replace(",", "").replace("'", "")
                    msb.mkdir()
                    if marker is not None:
                        (msb / MARKER).write_text(marker + "\n", encoding="utf-8")
                    env = dict(os.environ, MSB=str(msb), SB=str(msb if same else Path(temp) / "kit"), MBASE=mbase)
                    self.assertEqual(run(["bash", "-c", guards[0]], env).returncode == 0, passes)
                    self.assertTrue(msb.exists(), "the guard itself deletes nothing")


if __name__ == "__main__":
    unittest.main()
