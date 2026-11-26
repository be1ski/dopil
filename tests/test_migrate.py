"""Run the migration script in temporary repositories: plans, moves, refusals, interruptions and races."""

import errno
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parent.parent / "skills/dopil/references/migrate.py"
SPEC = importlib.util.spec_from_file_location("migrate", str(SCRIPT))
migrate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migrate)

# The old scratch and pointer directory, each an allowlisted literal of tests/test_names.py.
OLD = ".ship"
OLD_ROUTES = "ship-routes"
NEW = ".dopil"
NEW_ROUTES = "dopil-routes"
TODAY = "2026-11-26"
FOREIGN_GIT = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR"]
# No user or system git configuration reaches the tests (signing, hooks, excludes).
HERMETIC = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
R1 = [("spec-01", "closed"), ("code-01", "open (codex)")]
R2 = [("code-01", "closed"), ("polish-01", "not run: no delta")]
# Step boundaries of an uninterrupted run, in its order; the interruption test builds each by hand.
STAGES = ["registries", "half the entries", "no route left to read a marker from",
          "pointer copied, the old one present", "last pointer unlinked, the old directory left",
          "record written", ".gitignore unlinked, before rmdir", "after rmdir, before the record is deleted"]

# Row forms of real registries, reduced to ids, State cells and the notes between rows; paths neutral.
FEEDBACK_FIXES = """\
Executor: one runtime; reviewer: another, through an Orca worker.
Tree: the current checkout /work/project, branch main.

| Gate | Scope | Scratch | State | Proof |
|---|---|---|---|---|
| code-01 | git diff from a1b2c3 to the working tree | /work/project/.ship/2026-11-18-fixes/code-01 | closed | round-03-review.txt: VERDICT: ALL RESOLVED |

Implementer: Orca run run_1, dispatch ctx_1, brief code-01/impl-brief.md.
code-01 round 01: discovery dispatched ctx_2, prompt code-01/round-01-prompt.md.
| polish-01 | snapshot delta from polish-01/base/ | /work/project/.ship/2026-11-18-fixes/polish-01 | closed | round-01-review.txt: VERDICT: NO FINDINGS |
Polisher: dispatch ctx_3, brief polish-01/polish-brief.md.

Continuation: extra reviews led to seven more edits; new gates follow.
| code-02 | git diff from a1b2c3 to the working tree | /work/project/.ship/2026-11-18-fixes/code-02 | closed | round-04-review.txt: VERDICT: ALL RESOLVED |
Fix round 01 for code-02: new dispatch ctx_4, brief code-02/fix-01.md.
| polish-02 | snapshot delta from polish-02/base/ | /work/project/.ship/2026-11-18-fixes/polish-02 | not run | polish changed no line |
Polisher for polish-02: dispatch ctx_5.
"""
UNIFICATION = """\
Scratch root: /work/project/.ship/2026-11-20-unification
Pointer: <git-common-dir>/ship-routes/2026-11-20-unification.txt

| Gate | Scope | Scratch | State | Proof |
|---|---|---|---|---|
| spec-01 | file: /work/project/.ship/2026-11-20-unification/spec.md | /work/project/.ship/2026-11-20-unification/spec-01 | closed (4 rounds; 52 findings in round 01 + 9 new in round 02, all fixed, none rejected) | all three VERDICT: ALL RESOLVED in round 04 |
| plan-01 | file: /work/project/.ship/2026-11-20-unification/plan.md | /work/project/.ship/2026-11-20-unification/plan-01 | closed (5 rounds; 45 findings in round 01 + 9 new later) | all three VERDICT: ALL RESOLVED in round 05 |

spec-01 closed; awaiting the owner's approval of the spec.

## PAUSED (owner: "save the state")

State:
- spec-01 closed, spec approved; plan-01 closed (5 rounds, one stall decided by the owner).
- Tree /work/tree, base a1b2c3. Task 1 complete.

Resume order: ask the open question; then Tasks 2-6 by the plan; code gate; polish; parity.

| code-01 | git diff a1b2c3 to the working tree of /work/tree | /work/project/.ship/2026-11-20-unification/code-01 | closed (4 rounds) | all VERDICT: ALL RESOLVED |

code-01 round 01 counted; triage code-01/triage-01.md; ledgers written.
code-01 closed on f8d1ba. Next: polish-01.
| polish-01 | git diff f8d1ba to the working tree of /work/tree | /work/project/.ship/2026-11-20-unification/polish-01 | closed (2 rounds) | round-02: NO FINDINGS |
- parity done; window restored.
"""
LIVE_LOCKED = """\
Route: one-off (code, gate, polish, gate delta), current checkout /work/sandbox, no own tree.
Reviewers: reviewer-a, reviewer-b, reviewer-c

| Gate | Scope | Scratch | Reviewers (locked) | State | Proof |
|---|---|---|---|---|---|
| code-01 | git diff 54f496 -- wc/count.py tests/test_count.py | /work/sandbox/.ship/2026-11-25-wc-usage/code-01 | reviewer-a, reviewer-b, reviewer-c | closed | r02: all VERDICT: ALL RESOLVED |
| polish-01 | snapshot delta of wc/count.py, tests/test_count.py | /work/sandbox/.ship/2026-11-25-wc-usage/polish-01 | — | not run: no delta | polish pass |

## code-01 reviewer scratches and pins
"""
LIVE_OPEN = """\
| Gate | Scope | Scratch | Reviewers | State | Proof |
|---|---|---|---|---|---|
| code-01 | git diff 54f496 -- wc/count.py | /work/sandbox/.ship/2026-11-25-count-usage/code-01 | reviewer-a | closed | round 2 |
| polish-01 | delta from snapshots | /work/sandbox/.ship/2026-11-25-count-usage/polish-01 | reviewer-a | open (polish pass) | |
"""
LEGACY = """\
Reviewers: reviewer-a

| Gate | Scope | Scratch | State | Proof |
|---|---|---|---|---|
| spec-01 | file: /work/sandbox/.ship/2026-11-01-usage/spec.md | /work/sandbox/.ship/2026-11-01-usage/spec-01 | closed (2 rounds, reviewer-a) | VERDICT |
| spec-02 | file: /work/sandbox/.ship/2026-11-01-usage/spec.md | /work/sandbox/.ship/2026-11-01-usage/spec-02 | open (reviewer-a) | — |

spec-01's closure is unproven, so the spec gate is reopened as spec-02.
"""
WIDE = """\
## Gates

| Gate | Scope | Reviewers (locked) | Scratch | Pins | Thread files | State | Proof |
|---|---|---|---|---|---|---|---|
| code-01 | `wc/count.py` from `54f496` | `reviewer-a`, `reviewer-b` | root: `/work/sandbox/.ship/r/code-01` | pins | files | open (round 1 in flight) | |
"""
HEADERLESS = """\
Reviewers: reviewer-a
Route: one-off; code -> code gate -> polish -> polish delta gate

code-01 | scope: wc/count.py | scratch: /work/sandbox/.ship/20261125-usage/code-01 | state: open
"""


def clean_env(extra=None):
    """The caller's environment without the variables that point git elsewhere, plus the hermetic config."""
    env = {name: value for name, value in os.environ.items() if name not in FOREIGN_GIT}
    env.update(HERMETIC)
    env.update(extra or {})
    return env


def run_git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com"] + list(args),
                          cwd=str(cwd), env=clean_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)


def run_script(cwd, args, env=None):
    return subprocess.run([sys.executable, "-I", str(SCRIPT)] + list(args), cwd=str(cwd), env=clean_env(env),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


def registry(root, states):
    """A gates.md in the 574afe1 registry form, with a note after each row."""
    lines = ["# Route " + root.name, "", "Scratch root: %s" % root, "",
             "| Gate | Scope | Scratch | State | Proof |", "|---|---|---|---|---|"]
    for gate, state in states:
        lines += ["| %s | scope | %s/%s | %s | proof |" % (gate, root, gate, state), "Note after %s." % gate]
    return "\n".join(lines) + "\n"


def rewritten(text, old, new, states):
    """A registry as the migration leaves it: the new prefix, and the line naming the gates that are not closed."""
    waiting = [gate for gate, state in states if not state.startswith(("closed", "not run"))]
    text = text.replace(str(old), str(new))
    return text + ("Migrated %s: restart on resume: %s\n" % (TODAY, ", ".join(waiting)) if waiting else "")


def snapshot(root):
    """Every path under root: a directory, a link with its target, or a file with its bytes."""
    found = {}
    for directory, dirnames, filenames in os.walk(str(root)):
        for name in dirnames + filenames:
            path = os.path.join(directory, name)
            rel = os.path.relpath(path, str(root))
            if os.path.islink(path):
                found[rel] = "link:" + os.readlink(path)
            elif os.path.isdir(path):
                found[rel] = "dir"
            else:
                found[rel] = Path(path).read_bytes()
    return found


class MigrationCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.tmp))
        environment = mock.patch.dict(os.environ, dict(HERMETIC, GIT_CEILING_DIRECTORIES=str(self.tmp)))
        environment.start()
        self.addCleanup(environment.stop)
        for name in FOREIGN_GIT:
            os.environ.pop(name, None)
        self.use(self.tmp / "repo")

    def use(self, top):
        self.top, self.gitdir = top, top / ".git"

    def init(self, top=None):
        top = top or self.top
        top.mkdir(parents=True, exist_ok=True)
        done = run_git(top, "init", "-q")
        self.assertEqual(done.returncode, 0, done.stderr)
        return top

    def scratch(self, where, routes=(("r1", R1),), notes=True, ignore=b"*\n"):
        """An old scratch beside `where`: its .gitignore, routes with registries, and a notes file."""
        old = where / OLD
        old.mkdir(parents=True)
        if ignore is not None:
            (old / ".gitignore").write_bytes(ignore)
        for name, states in routes:
            (old / name).mkdir()
            (old / name / "gates.md").write_text(registry(old / name, states), encoding="utf-8")
            (old / name / "spec.md").write_text("spec of %s\n" % name, encoding="utf-8")
        if notes:
            (old / "notes.md").write_text("notes\n", encoding="utf-8")
        return old

    def pointer(self, target, directory=None):
        directory = directory or self.gitdir / OLD_ROUTES
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (target.name + ".txt")
        path.write_text("%s\n" % target, encoding="utf-8")
        return path

    def cli(self, mode, cwd=None, env=None):
        return run_script(cwd or self.top, [mode], env)

    def assert_prints(self, result, lines, status):
        self.assertEqual((result.stdout.splitlines(), result.returncode), (lines, status), result.stderr)

    def state(self):
        """The work tree and the two pointer directories of the git dir."""
        return {rel: value for rel, value in snapshot(self.top).items()
                if rel.split(os.sep)[0] != ".git" or rel.split(os.sep)[1:2] in ([OLD_ROUTES], [NEW_ROUTES])}

    def assert_empty(self, plan):
        self.assertEqual((plan.scratches, plan.moves, plan.pointers, plan.markers, plan.leaves),
                         ([], [], [], {}, []))


class MoveTest(MigrationCase):
    def test_run_moves_routes_and_pointers(self):
        self.init()
        old, new = self.scratch(self.top), self.top / NEW
        self.pointer(old / "r1")
        gates = (old / "r1" / "gates.md").read_text(encoding="utf-8")
        lines = ["MOVE %s -> %s" % (old / "notes.md", new / "notes.md"),
                 "MOVE %s -> %s" % (old / "r1", new / "r1"),
                 "MOVE %s -> %s" % (self.gitdir / OLD_ROUTES / "r1.txt", self.gitdir / NEW_ROUTES / "r1.txt"),
                 "MOVE %s -> %s" % (old, new),
                 "RESTART-LATER %s: code-01" % (new / "r1" / "gates.md")]
        before = snapshot(self.top)
        self.assert_prints(self.cli("check"), lines, 1)
        self.assertEqual(snapshot(self.top), before, "check changed the tree or the git dir")
        today = date.today().isoformat()
        self.assert_prints(self.cli("run"), lines, 0)
        moved = (new / "r1" / "gates.md").read_text(encoding="utf-8")
        self.assertEqual(moved, gates.replace(str(old), str(new)) + "Migrated %s: restart on resume: code-01\n" % today)
        self.assertEqual((new / "notes.md").read_text(encoding="utf-8"), "notes\n")
        self.assertEqual((self.gitdir / NEW_ROUTES / "r1.txt").read_text(encoding="utf-8"), "%s\n" % (new / "r1"))
        self.assertEqual((new / ".gitignore").read_bytes(), b"*\n")
        self.assertEqual(sorted(os.listdir(str(new))), [".gitignore", "notes.md", "r1"])
        self.assertFalse(os.path.lexists(str(old)))
        self.assertFalse(os.path.lexists(str(self.gitdir / OLD_ROUTES)))
        for mode in ("run", "check"):
            self.assert_prints(self.cli(mode), [], 0)

    def test_unreadable_registry_moves_with_unknown_marker(self):
        self.init()
        old, new = self.scratch(self.top, notes=False), self.top / NEW
        (old / "r2").mkdir()
        prose = "# Route r2\n\nScratch root: %s\nspec-01: closed\ncode-01: open, codex\n" % (old / "r2")
        (old / "r2" / "gates.md").write_text(prose, encoding="utf-8")
        lines = ["MOVE %s -> %s" % (old / "r1", new / "r1"), "MOVE %s -> %s" % (old / "r2", new / "r2"),
                 "MOVE %s -> %s" % (old, new),
                 "RESTART-LATER %s: code-01" % (new / "r1" / "gates.md"),
                 "RESTART-LATER %s: unknown" % (new / "r2" / "gates.md")]
        self.assert_prints(self.cli("check"), lines, 1)
        today = date.today().isoformat()
        self.assert_prints(self.cli("run"), lines, 0)
        moved = (new / "r2" / "gates.md").read_text(encoding="utf-8")
        self.assertEqual(moved, prose.replace(str(old), str(new)) + "Migrated %s: restart on resume: unknown\n" % today)
        self.assertEqual(sorted(os.listdir(str(new))), [".gitignore", "r1", "r2"])
        self.assertFalse(os.path.lexists(str(old)))
        self.assert_prints(self.cli("run"), [], 0)

    def test_check_from_subdirectory(self):
        self.init()
        sub = self.top / "a" / "b"
        sub.mkdir(parents=True)
        upper = self.scratch(self.top, notes=False)
        lower = self.scratch(sub, routes=(("r2", R2),), notes=False)
        self.pointer(upper / "r1")
        self.pointer(lower / "r2")
        before = snapshot(self.top)
        self.assertEqual(self.cli("check", cwd=sub).returncode, 1)
        self.assertEqual(snapshot(self.top), before, "check changed the tree or the git dir")
        plan = migrate.make_plan(sub)
        self.assertEqual(sorted(plan.scratches), [upper, lower])
        self.assertEqual(sorted(plan.moves), [(upper / "r1", self.top / NEW / "r1"), (lower / "r2", sub / NEW / "r2")])
        migrate.run(sub, TODAY)
        for where, name in ((self.top, "r1"), (sub, "r2")):
            self.assertEqual(sorted(os.listdir(str(where / NEW))), [".gitignore", name])
            self.assertFalse(os.path.lexists(str(where / OLD)))
            self.assertEqual((self.gitdir / NEW_ROUTES / (name + ".txt")).read_text(encoding="utf-8"),
                             "%s\n" % (where / NEW / name))
        self.assertFalse(os.path.lexists(str(self.gitdir / OLD_ROUTES)))
        plain = self.tmp / "plain"
        inner = plain / "inner"
        inner.mkdir(parents=True)
        self.scratch(plain)
        local = self.scratch(inner)
        self.assertEqual(migrate.make_plan(inner).scratches, [local])

    def test_foreign_scratch_is_ignored(self):
        self.init()
        (self.top / OLD).mkdir()
        (self.top / OLD / "cache.bin").write_bytes(b"\0\1")
        before = snapshot(self.tmp)
        self.assert_empty(migrate.make_plan(self.top))
        for mode in ("check", "run"):
            self.assert_prints(self.cli(mode), [], 0)
        self.assertEqual(snapshot(self.tmp), before)

    def test_pointer_through_a_linked_parent_moves(self):
        self.init()
        old = self.scratch(self.top)
        alias = self.tmp / "alias"
        os.symlink(str(self.tmp), str(alias))
        pointer = self.pointer(alias / self.top.name / OLD / "r1")
        result = self.cli("run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MOVE %s -> %s" % (pointer, self.gitdir / NEW_ROUTES / "r1.txt"), result.stdout.splitlines())
        self.assertEqual((self.gitdir / NEW_ROUTES / "r1.txt").read_text(encoding="utf-8"),
                         "%s\n" % (self.top / NEW / "r1"))
        self.assertFalse(os.path.lexists(str(self.gitdir / OLD_ROUTES)))
        self.assertFalse(os.path.lexists(str(old)))

    def test_linked_worktree_plans_remove_the_emptied_pointer_directory(self):
        self.init()
        self.assertEqual(run_git(self.top, "commit", "-q", "--allow-empty", "-m", "init").returncode, 0)
        linked = self.tmp / "linked"
        self.assertEqual(run_git(self.top, "worktree", "add", "-q", "--detach", str(linked)).returncode, 0)
        self.pointer(self.scratch(self.top) / "r1")
        self.pointer(self.scratch(linked, routes=(("r2", R2),), notes=False) / "r2")
        plans = [migrate.make_plan(self.top), migrate.make_plan(linked)]
        for plan in plans:
            self.assertEqual(len(plan.pointers), 1)
            self.assertEqual(len(plan.leaves), 1)  # each sees the other's pointer as not its own
            self.assertEqual(list(migrate.steps(plan, TODAY)), migrate.STEPS)
        self.assertFalse(os.path.lexists(str(self.gitdir / OLD_ROUTES)))
        self.assertEqual(sorted(os.listdir(str(self.gitdir / NEW_ROUTES))), ["r1.txt", "r2.txt"])

    def test_old_pointer_directory_without_a_migration_is_left(self):
        # An empty old pointer directory with no old scratch here: no migration of this worktree, so nothing is
        # planned, even with a read-only git dir.
        self.init()
        (self.gitdir / OLD_ROUTES).mkdir()
        os.chmod(str(self.gitdir), 0o555)
        self.addCleanup(os.chmod, str(self.gitdir), 0o755)
        before = snapshot(self.top)
        for mode in ("check", "run"):
            self.assert_prints(self.cli(mode), [], 0)
        self.assertEqual(snapshot(self.top), before)

    def test_other_worktrees_pointers_do_not_block(self):
        # A local old scratch with no pointer of its own, beside another worktree's pointer, under a read-only git
        # dir: the pointer directory is not this plan's to remove or check, so the scratch moves and it stays.
        self.init()
        self.assertEqual(run_git(self.top, "commit", "-q", "--allow-empty", "-m", "init").returncode, 0)
        linked = self.tmp / "linked"
        self.assertEqual(run_git(self.top, "worktree", "add", "-q", "--detach", str(linked)).returncode, 0)
        old, new = self.scratch(self.top), self.top / NEW
        theirs = self.pointer(linked / OLD / "r2")
        os.chmod(str(self.gitdir), 0o555)
        self.addCleanup(os.chmod, str(self.gitdir), 0o755)
        check = self.cli("check")
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        kinds = [line.split(" ", 1)[0] for line in check.stdout.splitlines()]
        self.assertEqual(sorted(set(kinds)), ["LEAVE", "MOVE", "RESTART-LATER"], check.stdout)
        self.assertIn("LEAVE %s: " % theirs, check.stdout)
        result = self.cli("run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(os.path.lexists(str(old)))
        self.assertEqual(sorted(os.listdir(str(new))), [".gitignore", "notes.md", "r1"])
        self.assertEqual(os.listdir(str(self.gitdir / OLD_ROUTES)), [theirs.name])

    def test_pointer_directory_removed_while_planning(self):
        # An interrupted run left ship-routes empty; another run removes it right after this plan lists it. The plan
        # keeps its first listing, so it neither reads the directory again nor refuses, and the run finishes.
        self.init()
        old = self.scratch(self.top)
        directory = self.gitdir / OLD_ROUTES
        directory.mkdir()
        real, reads = os.listdir, []

        def listed_then_removed(path=".", *args, **kwargs):
            names = real(path, *args, **kwargs)
            if str(path) == str(directory):
                reads.append(names)
                if os.path.isdir(str(directory)):
                    os.rmdir(str(directory))  # the other run's removal
            return names

        with mock.patch.object(migrate.os, "listdir", listed_then_removed):
            plan = migrate.make_plan(self.top)
        self.assertEqual(reads, [[]], "planning lists the directory once")
        self.assertEqual(plan.old_routes, directory)
        migrate.run(self.top, TODAY)
        self.assertFalse(os.path.lexists(str(old)))
        self.assertFalse(os.path.lexists(str(directory)))

    def test_linked_empty_pointer_directory_does_not_block(self):
        # An empty symlinked old pointer directory to a read-only target is not this migration's to remove or check.
        self.init()
        old = self.scratch(self.top)
        target = self.tmp / "read-only-routes"
        target.mkdir()
        os.chmod(str(target), 0o555)
        self.addCleanup(os.chmod, str(target), 0o755)
        os.symlink(str(target), str(self.gitdir / OLD_ROUTES))
        result = self.cli("run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(os.path.lexists(str(old)))
        self.assertEqual(sorted(os.listdir(str(self.top / NEW))), [".gitignore", "notes.md", "r1"])
        self.assertTrue(os.path.islink(str(self.gitdir / OLD_ROUTES)))
        self.assertEqual(os.listdir(str(target)), [])

    def test_aliased_paths_in_the_registry_are_rewritten(self):
        # The registry can name the scratch through an alias of its parent; the pointer that uses it shows it.
        self.init()
        old, new = self.scratch(self.top), self.top / NEW
        alias = self.tmp / "alias"
        os.symlink(str(self.tmp), str(alias))
        aliased = alias / self.top.name / OLD
        gates = old / "r1" / "gates.md"
        text = gates.read_text(encoding="utf-8").replace("| %s/code-01 |" % (old / "r1"),
                                                         "| %s/code-01 |" % (aliased / "r1"))
        self.assertIn(str(aliased), text)
        gates.write_text(text, encoding="utf-8")
        self.pointer(aliased / "r1")
        self.assertEqual(self.cli("run").returncode, 0)
        moved = (new / "r1" / "gates.md").read_text(encoding="utf-8")
        self.assertNotIn("/%s/" % OLD, moved)
        self.assertIn("| %s/code-01 |" % (alias / self.top.name / NEW / "r1"), moved)
        self.assertIn("Scratch root: %s" % (new / "r1"), moved)

    def test_run_merges_into_existing_dopil(self):
        self.init()
        self.scratch(self.top)
        kept = self.top / NEW / "r0"
        kept.mkdir(parents=True)
        (kept / "gates.md").write_text("an earlier route\n", encoding="utf-8")
        before = snapshot(kept)
        migrate.run(self.top, TODAY)
        self.assertEqual(sorted(os.listdir(str(self.top / NEW))), [".gitignore", "notes.md", "r0", "r1"])
        self.assertEqual(snapshot(kept), before)

    def test_root_rule_cannot_unignore(self):
        self.init()
        (self.top / ".gitignore").write_text("!/%s/\n!/%s/x\n" % (NEW, NEW), encoding="utf-8")
        self.scratch(self.top)
        migrate.run(self.top, TODAY)
        self.assertEqual(run_git(self.top, "check-ignore", "-q", NEW + "/x").returncode, 0)

    def test_outside_git(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        old = self.scratch(plain)
        gates = (old / "r1" / "gates.md").read_text(encoding="utf-8")
        calls, real = [], migrate.git

        def recording(args, cwd):
            calls.append(list(args))
            return real(args, cwd)

        with mock.patch.object(migrate, "git", recording):
            plan = migrate.run(plain, TODAY)
        self.assertEqual(calls, [["rev-parse", "--is-inside-work-tree"]])
        self.assertEqual(plan.pointers, [])
        self.assertFalse(os.path.lexists(str(old)))
        self.assertEqual(sorted(os.listdir(str(plain / NEW))), [".gitignore", "notes.md", "r1"])
        self.assertEqual((plain / NEW / "r1" / "gates.md").read_text(encoding="utf-8"),
                         rewritten(gates, old, plain / NEW, R1))


class RegistryTest(unittest.TestCase):
    def test_unclosed_gates_reads_real_registries(self):
        for name, text, expected in [("feedback fixes", FEEDBACK_FIXES, []), ("unification", UNIFICATION, []),
                                     ("live, locked reviewers", LIVE_LOCKED, []),
                                     ("live, open polish", LIVE_OPEN, ["polish-01"]),
                                     ("legacy, reopened spec", LEGACY, ["spec-02"]),
                                     ("wide", WIDE, ["code-01"])]:
            with self.subTest(name):
                self.assertEqual(migrate.unclosed_gates(text), expected)
        with self.assertRaises(migrate.Refused):
            migrate.unclosed_gates(HEADERLESS)


class RefusalTest(MigrationCase):
    def test_refusals_change_nothing(self):
        def no_ignore(old):
            (old / ".gitignore").unlink()
            return old / ".gitignore"

        def commented(old):
            (old / ".gitignore").write_bytes(b"# scratch\n*\n")
            return old / ".gitignore"

        def fallback_pointers(old):
            (old / "routes").mkdir()
            (old / "routes" / "r1.txt").write_text("%s\n" % (old / "r1"), encoding="utf-8")
            return old / "routes"

        def taken_name(old):
            (self.top / NEW / "r1").mkdir(parents=True)
            return self.top / NEW / "r1"

        def other_ignore(old):
            (self.top / NEW).mkdir()
            (self.top / NEW / ".gitignore").write_bytes(b"*.log\n")
            return self.top / NEW / ".gitignore"

        def other_pointer(old):
            self.pointer(old / "r1")
            taken = self.gitdir / NEW_ROUTES / "r1.txt"
            taken.parent.mkdir()
            taken.write_text("/elsewhere/r1\n", encoding="utf-8")
            return taken

        def linked_dopil(old):
            (self.top.parent / "elsewhere").mkdir()
            os.symlink(str(self.top.parent / "elsewhere"), str(self.top / NEW))
            return self.top / NEW

        def linked_directory(old):
            self.pointer(old / "r1", self.top.parent / "routes-elsewhere")
            os.symlink(str(self.top.parent / "routes-elsewhere"), str(self.gitdir / OLD_ROUTES))
            return self.gitdir / OLD_ROUTES

        def read_only_git_dir(old):
            self.pointer(old / "r1")
            os.chmod(str(self.gitdir), 0o555)
            self.addCleanup(os.chmod, str(self.gitdir), 0o755)
            return self.gitdir

        def tracked(old):
            done = run_git(self.top, "add", "-f", OLD)
            self.assertEqual(done.returncode, 0, done.stderr)
            return old

        def dopil_is_a_file(old):
            (self.top / NEW).write_text("not a directory\n", encoding="utf-8")
            return self.top / NEW

        def pointer_directory_is_a_file(old):
            self.pointer(old / "r1")
            (self.gitdir / NEW_ROUTES).write_text("not a directory\n", encoding="utf-8")
            return self.gitdir / NEW_ROUTES

        def unreadable_registry(old):
            if os.geteuid() == 0:
                self.skipTest("root reads a file of mode 0200")
            locked.append(old / "r1" / "gates.md")
            return old / "r1" / "gates.md"

        cases = [no_ignore, commented, fallback_pointers, taken_name, other_ignore, other_pointer, linked_dopil,
                 linked_directory, read_only_git_dir, tracked, dopil_is_a_file, pointer_directory_is_a_file,
                 unreadable_registry]
        for case in cases:
            with self.subTest(case.__name__):
                self.use(self.tmp / case.__name__ / "repo")
                self.init()
                locked = []  # files made unreadable only between the two snapshots, which read every file
                refused = case(self.scratch(self.top))
                env = {"GIT_INDEX_FILE": str(self.tmp / "other-index")} if case is tracked else None
                before = snapshot(self.top.parent)
                for path in locked:
                    os.chmod(str(path), 0o200)
                for mode in ("check", "run"):
                    result = self.cli(mode, env=env)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
                    self.assertTrue(result.stdout.startswith("REFUSE %s: " % refused), result.stdout)
                for path in locked:
                    os.chmod(str(path), 0o644)
                self.assertEqual(snapshot(self.top.parent), before)

    def test_usage_error_has_its_own_code(self):
        self.init()
        for args in [[], ["bogus"], ["check", "run"], ["restart"], ["restart", "gates.md", "code-01"]]:
            with self.subTest(args):
                result = run_script(self.top, args)
                self.assertEqual((result.returncode, result.stdout), (64, ""), result.stderr)
                self.assertTrue(result.stderr.startswith("usage: "), result.stderr)

    def test_foreign_git_env_is_ignored(self):
        self.init()
        other = self.init(self.tmp / "other")
        old = self.scratch(self.top)
        self.pointer(old / "r1")
        before = snapshot(other)
        with mock.patch.dict(os.environ, {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other)}):
            plan = migrate.make_plan(self.top)
            self.assertEqual(plan.scratches, [old])
            self.assertEqual([pointer[:2] for pointer in plan.pointers],
                             [(self.gitdir / OLD_ROUTES / "r1.txt", self.gitdir / NEW_ROUTES / "r1.txt")])
            migrate.run(self.top, TODAY)
        self.assertTrue((self.top / NEW / "r1" / "gates.md").is_file())
        self.assertTrue((self.gitdir / NEW_ROUTES / "r1.txt").is_file())
        self.assertEqual(snapshot(other), before)

    def test_left_pointers_are_named(self):
        self.init()
        self.assertEqual(run_git(self.top, "commit", "-q", "--allow-empty", "-m", "init").returncode, 0)
        linked = self.tmp / "linked"
        done = run_git(self.top, "worktree", "add", "-q", "--detach", str(linked))
        self.assertEqual(done.returncode, 0, done.stderr)
        old = self.scratch(self.top)
        moved = self.pointer(old / "r1")
        there = self.pointer(linked / OLD / "r2")
        outside = self.pointer(self.tmp / "elsewhere" / "r3")
        # Its path starts with the scratch's path as a string, not as a component.
        sibling = self.pointer(self.top / (OLD + "-old") / "r9")
        result = self.cli("run")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertIn("MOVE %s -> %s" % (moved, self.gitdir / NEW_ROUTES / "r1.txt"), lines)
        left = [line for line in lines if line.startswith("LEAVE ")]
        self.assertEqual([line.split(": ", 1)[0] for line in left],
                         ["LEAVE %s" % there, "LEAVE %s" % outside, "LEAVE %s" % sibling])
        self.assertIn(str(linked), left[0])
        self.assertEqual(sibling.read_text(encoding="utf-8"), "%s\n" % (self.top / (OLD + "-old") / "r9"))
        self.assertEqual(there.read_text(encoding="utf-8"), "%s\n" % (linked / OLD / "r2"))
        self.assertEqual(outside.read_text(encoding="utf-8"), "%s\n" % (self.tmp / "elsewhere" / "r3"))

    def test_failed_ignore_check_refuses_before_moving(self):
        self.init()
        old = self.scratch(self.top)
        self.pointer(old / "r1")
        seen = []

        def not_ignored(path):
            seen.append(path)
            return False

        before = snapshot(self.top)
        with self.assertRaises(migrate.Refused):
            migrate.run(self.top, TODAY, not_ignored)
        self.assertEqual(snapshot(self.top), before)
        self.assertEqual([path.parent for path in seen], [self.top / NEW])
        (self.top / NEW).mkdir()
        (self.top / NEW / "keep.txt").write_text("keep\n", encoding="utf-8")
        before = snapshot(self.top)
        with self.assertRaises(migrate.Refused):
            migrate.run(self.top, TODAY, not_ignored)
        self.assertEqual(snapshot(self.top), before)

    def test_ignore_check_failure_refuses_with_its_error(self):
        # Exit 1 of check-ignore means "not ignored"; any other status is git failing, refused with its stderr.
        real, fake = shutil.which("git"), self.tmp / "bin"
        fake.mkdir()
        for status, needle in [(1, "is not reported ignored"), (128, "fatal: planted failure")]:
            with self.subTest(status=status):
                self.use(self.tmp / ("status-%d" % status) / "repo")
                self.init()
                self.scratch(self.top)
                (fake / "git").write_text('#!/bin/sh\nif [ "$1" = check-ignore ]; then\n'
                                          '  echo "fatal: planted failure" >&2; exit %d\nfi\nexec "%s" "$@"\n'
                                          % (status, real), encoding="utf-8")
                (fake / "git").chmod(0o755)
                before = snapshot(self.top)
                result = self.cli("run", env={"PATH": "%s%s%s" % (fake, os.pathsep, os.environ["PATH"])})
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
                self.assertTrue(result.stdout.startswith("REFUSE %s" % (self.top / NEW)), result.stdout)
                self.assertIn(needle, result.stdout)
                self.assertEqual(snapshot(self.top), before)

    def test_failed_cleanup_keeps_the_original_error(self):
        with self.subTest("a temporary file not removed after a failed replace"):
            target = self.tmp / "file.txt"

            def denied(source, destination):
                raise PermissionError(errno.EACCES, "Permission denied", destination)

            def busy(path, *args, **kwargs):
                raise OSError(errno.EBUSY, "Resource busy", path)

            with mock.patch.object(migrate.os, "replace", denied), mock.patch.object(migrate.os, "unlink", busy), \
                    self.assertRaises(OSError) as raised:
                migrate.replace(target, b"data")
            error = raised.exception
            self.assertEqual(error.errno, errno.EACCES, error)
            temporary = [name for name in os.listdir(str(self.tmp)) if name.startswith(".file.txt.")]
            self.assertEqual(len(temporary), 1, temporary)
            self.assertIn(str(self.tmp / temporary[0]), str(error))
            self.assertIn("Resource busy", str(error))
        with self.subTest("a created .dopil not removed after a refusal: partial, not refused"):
            self.init()
            self.scratch(self.top)
            real = os.rmdir

            def busy_dopil(path, *args, **kwargs):
                if str(path) == str(self.top / NEW):
                    raise OSError(errno.EBUSY, "Resource busy", path)
                return real(path, *args, **kwargs)

            with mock.patch.object(migrate.os, "rmdir", busy_dopil), self.assertRaises(migrate.Partial) as raised:
                migrate.run(self.top, TODAY, lambda path: False)
            message = str(raised.exception)
            self.assertTrue(message.startswith("prepare .dopil, step 1 of 5: %s: is not reported ignored by git "
                                               "check-ignore" % (self.top / NEW / "x")), message)
            self.assertIn("%s not removed: Resource busy" % (self.top / NEW), message)

    def test_published_ignore_file_is_undone(self):
        # The .gitignore counts as created the moment it is linked: a failure right after still removes it.
        self.init()
        self.scratch(self.top)
        real, failed = os.unlink, []

        def unlink_once(path, *args, **kwargs):
            if os.path.basename(str(path)).startswith("..gitignore.") and not failed:  # its temporary file
                failed.append(path)
                raise OSError(errno.EBUSY, "Resource busy", path)
            return real(path, *args, **kwargs)

        before = snapshot(self.top)
        with mock.patch.object(migrate.os, "unlink", unlink_once), self.assertRaises(migrate.Refused):
            migrate.run(self.top, TODAY)
        self.assertEqual(len(failed), 1)
        self.assertEqual(snapshot(self.top), before)

    def test_temporary_file_left_behind_is_partial(self):
        # An existing .dopil, and the temporary file of its .gitignore cannot be removed at all: the published file
        # goes, the temporary file stays, so the step did not change nothing and reports PARTIAL with both.
        self.init()
        self.scratch(self.top)
        (self.top / NEW).mkdir()
        real, failed = os.unlink, []

        def stuck(path, *args, **kwargs):
            if os.path.basename(str(path)).startswith("..gitignore."):  # its temporary file
                failed.append(path)
                raise OSError(errno.EBUSY, "Resource busy", path)
            return real(path, *args, **kwargs)

        with mock.patch.object(migrate.os, "unlink", stuck), self.assertRaises(migrate.Partial) as raised:
            migrate.run(self.top, TODAY)
        message = str(raised.exception)
        temporary = failed[0]
        self.assertTrue(message.startswith("prepare .dopil, step 1 of 5: "), message)
        self.assertIn("%s not removed: Resource busy" % temporary, message)
        self.assertEqual(os.listdir(str(self.top / NEW)), [os.path.basename(str(temporary))])

    def test_existing_ignore_file_with_a_stuck_temporary_file_is_partial(self):
        # A valid .gitignore is in place, so the link finds it existing; that is normal only when the temporary file
        # also goes. Here it cannot be removed: PARTIAL with the cause and the leftover, not a silent exit 0.
        self.init()
        self.scratch(self.top)
        (self.top / NEW).mkdir()
        (self.top / NEW / ".gitignore").write_bytes(b"*\n")
        real, failed = os.unlink, []

        def stuck(path, *args, **kwargs):
            if os.path.basename(str(path)).startswith("..gitignore."):  # its temporary file
                failed.append(path)
                raise OSError(errno.EBUSY, "Resource busy", path)
            return real(path, *args, **kwargs)

        with mock.patch.object(migrate.os, "unlink", stuck), self.assertRaises(migrate.Partial) as raised:
            migrate.run(self.top, TODAY)
        message = str(raised.exception)
        self.assertTrue(message.startswith("prepare .dopil, step 1 of 5: "), message)
        self.assertIn("File exists", message)
        self.assertIn("%s not removed: Resource busy" % failed[0], message)
        self.assertEqual(sorted(os.listdir(str(self.top / NEW))),
                         sorted([".gitignore", os.path.basename(str(failed[0]))]))
        self.assertTrue((self.top / OLD).is_dir(), "nothing moved")


class InterruptionTest(MigrationCase):
    def fixture(self):
        """Two routes, a notes file and two pointers, rebuilt at the same paths each time."""
        if self.top.exists():
            shutil.rmtree(str(self.top))
        self.init()
        old = self.scratch(self.top, routes=(("r1", R1), ("r2", R2)))
        self.pointer(old / "r1")
        self.pointer(old / "r2")
        return old

    def end_state(self):
        self.fixture()
        migrate.run(self.top, TODAY)
        return self.state()

    def record(self, old, inode_offset=0, path=None):
        st = os.lstat(str(old))
        (self.top / NEW / ".migrating").write_text(json.dumps(
            {"path": str(path or old), "dev": st.st_dev, "ino": st.st_ino + inode_offset}), encoding="utf-8")

    def interrupted(self, stage):
        """The tree as a run interrupted after `stage` leaves it, built by hand."""
        old, new = self.fixture(), self.top / NEW
        reached = STAGES[:STAGES.index(stage) + 1]
        for name, states in (("r1", R1), ("r2", R2)):
            gates = old / name / "gates.md"
            gates.write_text(rewritten(gates.read_text(encoding="utf-8"), old, new, states), encoding="utf-8")
        if "half the entries" in reached:
            new.mkdir()
            (new / ".gitignore").write_bytes(b"*\n")
            os.rename(str(old / "r1"), str(new / "r1"))
        if "no route left to read a marker from" in reached:
            for name in ("notes.md", "r2"):
                os.rename(str(old / name), str(new / name))
        if "pointer copied, the old one present" in reached:
            copy = self.gitdir / NEW_ROUTES / "r1.txt"
            copy.parent.mkdir()
            copy.write_text("%s\n" % (new / "r1"), encoding="utf-8")
        if "last pointer unlinked, the old directory left" in reached:
            for name in ("r1", "r2"):
                (self.gitdir / NEW_ROUTES / (name + ".txt")).write_text("%s\n" % (new / name), encoding="utf-8")
                (self.gitdir / OLD_ROUTES / (name + ".txt")).unlink()
        if "record written" in reached:
            (self.gitdir / OLD_ROUTES).rmdir()
            self.record(old)
        if ".gitignore unlinked, before rmdir" in reached:
            (old / ".gitignore").unlink()
        if "after rmdir, before the record is deleted" in reached:
            old.rmdir()
        return old

    def test_interruption_is_finished_by_next_run(self):
        end = self.end_state()
        for stage in STAGES:
            with self.subTest(stage):
                self.interrupted(stage)
                self.assertEqual(self.cli("check").returncode, 1)
                result = self.cli("run")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.state(), end)
        with self.subTest("a neighbour of the record"):
            self.interrupted("record written")
            (self.top / NEW / ".removed-notes").write_text("someone's\n", encoding="utf-8")
            self.assertEqual(self.cli("run").returncode, 0)
            self.assertEqual((self.top / NEW / ".removed-notes").read_text(encoding="utf-8"), "someone's\n")
            state = self.state()
            del state[os.path.join(NEW, ".removed-notes")]
            self.assertEqual(state, end)
        for name in ["empty, no record", "another identity"]:
            with self.subTest(name):
                self.use(self.tmp / name.replace(" ", "-").replace(",", "") / "repo")
                self.init()
                old = self.top / OLD
                old.mkdir()
                if name == "another identity":
                    (self.top / NEW).mkdir()
                    self.record(old, inode_offset=1)
                before = snapshot(self.top)
                for mode in ("check", "run"):
                    result = self.cli(mode)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual([line.split(": ", 1)[0] for line in result.stdout.splitlines()],
                                     ["LEAVE %s" % old])
                self.assertEqual(snapshot(self.top), before)
        with self.subTest("a record of another path"):
            self.use(self.tmp / "foreign-record" / "repo")
            self.init()
            old = self.scratch(self.top)
            (self.top / NEW).mkdir()
            self.record(old, path=self.tmp / "other" / OLD)
            before = snapshot(self.top)
            for mode in ("check", "run"):
                result = self.cli(mode)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertTrue(result.stdout.startswith("REFUSE %s: " % (self.top / NEW / ".migrating")),
                                result.stdout)
            self.assertEqual(snapshot(self.top), before)

    def test_failure_after_a_write_is_partial(self):
        end = self.end_state()
        old = self.fixture()

        def lock_old_scratch(path):
            os.chmod(str(old), 0o555)
            return True

        self.addCleanup(lambda: old.exists() and os.chmod(str(old), 0o755))
        with self.assertRaises(migrate.Partial) as raised:
            migrate.run(self.top, TODAY, lock_old_scratch)
        message = str(raised.exception)
        self.assertTrue(message.startswith("move the entries, step 3 of 5: "), message)
        self.assertTrue(message.endswith("; moved: nothing"), message)
        os.chmod(str(old), 0o755)
        self.assertEqual(self.cli("run").returncode, 0)
        self.assertEqual(self.state(), end)

    def test_partial_names_the_moves_done(self):
        end = self.end_state()
        old, new = self.fixture(), self.top / NEW
        real = migrate.replace

        def failing(path, data, *args, **kwargs):
            if path.name == "r2.txt":
                raise PermissionError(errno.EACCES, "Permission denied", str(path))
            return real(path, data, *args, **kwargs)

        with mock.patch.object(migrate, "replace", failing), self.assertRaises(migrate.Partial) as raised:
            migrate.run(self.top, TODAY)
        message = str(raised.exception)
        self.assertTrue(message.startswith("move the pointers, step 4 of 5: "), message)
        moved = [(old / "notes.md", new / "notes.md"), (old / "r1", new / "r1"), (old / "r2", new / "r2"),
                 (self.gitdir / OLD_ROUTES / "r1.txt", self.gitdir / NEW_ROUTES / "r1.txt")]
        self.assertTrue(message.endswith("; moved: " + ", ".join("%s -> %s" % pair for pair in moved)), message)
        self.assertEqual(self.cli("run").returncode, 0)
        self.assertEqual(self.state(), end)

    def test_interrupted_ignore_file_does_not_block(self):
        # A run killed while it writes .dopil/.gitignore leaves no empty file in its place for the next run to refuse.
        end = self.end_state()
        self.fixture()

        def killed(descriptor, *args, **kwargs):
            os.close(descriptor)
            raise Stop()

        with mock.patch.object(migrate.os, "fdopen", killed), self.assertRaises(Stop):
            migrate.run(self.top, TODAY)
        self.assertFalse(os.path.lexists(str(self.top / NEW / ".gitignore")))
        self.assertEqual(self.cli("check").returncode, 1)
        result = self.cli("run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.state(), end)

    def test_interleaved_marks_leave_nothing_behind(self):
        end = self.end_state()
        self.fixture()
        first, second = [migrate.steps(migrate.make_plan(self.top), TODAY) for _ in range(2)]
        next(first)
        next(second)
        real, moved = os.replace, []

        def move_first(source, target):
            # The second run's temporary registry is written; before it replaces the file, the first run marks
            # and moves every route.
            if os.path.basename(str(target)) == "gates.md" and not moved:
                moved.append(target)
                next(first)
                next(first)
            return real(source, target)

        with mock.patch.object(migrate.os, "replace", move_first):
            next(second)
        self.assertEqual(len(moved), 1)
        self.assertEqual(list(first), migrate.STEPS[3:])
        self.assertEqual(list(second), migrate.STEPS[2:])
        self.assertEqual(self.state(), end)

    def test_interleaved_runs_end_in_the_same_state(self):
        end = self.end_state()
        self.fixture()
        plans = [migrate.make_plan(self.top), migrate.make_plan(self.top)]
        runs = [migrate.steps(plan, TODAY) for plan in plans]
        for _ in range(5):
            for steps in runs:
                next(steps)
        for steps in runs:
            self.assertEqual(list(steps), [])
        self.assertEqual(self.state(), end)
        self.fixture()
        plans = [migrate.make_plan(self.top), migrate.make_plan(self.top)]
        first, second = [migrate.steps(plan, TODAY) for plan in plans]
        for _ in range(3):
            next(first)
            next(second)
        next(first)
        (self.gitdir / NEW_ROUTES / "r1.txt").write_text("/elsewhere/r1\n", encoding="utf-8")
        with self.assertRaises(migrate.Refused):
            next(second)


CARRY = {"codex": ["C1 — wc/count.py:3 — counts a trailing newline twice",
                   "C2 — tests/test_count.py — no case for an empty file"]}
BASE_LINE = "Scope: git diff from a1b2c3 to the working tree. Working directory: /work/project. Base: a1b2c3."
PARALLEL = {"code-01/ledger.md": "# code-01 ledger\n" + BASE_LINE + "\n| id | round | quote | decision |\n",
            "code-01/codex/base-sha": "a1b2c3\n", "code-01/codex/thread-id": "ctx_1\n",
            "code-01/codex/ledger.md": "Pin: codex\n| C1 | 01 | newline | open |\n| C2 | 01 | empty | open |\n",
            "code-01/kimi/base-sha": "a1b2c3\n", "code-01/kimi/ledger.md": "Pin: kimi\n| K1 | 01 | name | fixed |\n"}
PROSE = "# Route r1\n\nspec-01: closed\ncode-01: open, codex\nMigrated %s: restart on resume: unknown\n" % TODAY


class Stop(Exception):
    """An interruption between two writes."""


class RestartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.tmp))
        self.project = self.tmp / "project"
        self.root = self.project / NEW / "r1"
        self.gates = self.root / "gates.md"
        self.given = self.tmp / "inputs.json"

    def route(self, rows=(("spec-01", "closed"), ("code-01", "open (codex, kimi)")), head="", waiting="code-01",
              text=None, files=None, **given):
        """A route as the migration leaves it, with code-01/ and an abandoned code-02/ directory, and the executor's
        inputs."""
        if self.project.exists():
            shutil.rmtree(str(self.project))
        (self.root / "code-01").mkdir(parents=True)
        (self.root / "code-02").mkdir()
        if text is None:
            text = head + registry(self.root, rows)
            if waiting:
                text += "Migrated %s: restart on resume: %s\n" % (TODAY, waiting)
        self.gates.write_text(text, encoding="utf-8")
        for rel, content in (files or {}).items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.inputs(**given)
        return text

    def inputs(self, carry=None, snapshots=(), locked=None, scratch=None, scope="scope", header=BASE_LINE, drop=()):
        """The executor's inputs.json: the old attempt's scratch (code-01/ by default), scope and header, the carried
        items and snapshots, and the lock when given; `drop` leaves keys out."""
        data = {"carry": carry or {}, "snapshots": [list(pair) for pair in snapshots],
                "scratch": str(scratch or self.root / "code-01"), "scope": scope, "header": header}
        if locked is not None:
            data["locked"] = locked
        for key in drop:
            del data[key]
        self.given.write_text(json.dumps(data), encoding="utf-8")

    def restart(self, old="code-01"):
        return migrate.restart(self.gates, old, self.given)

    def cli(self, old):
        return run_script(self.project, ["restart", str(self.gates), old, str(self.given)])

    def text(self, path):
        return path.read_text(encoding="utf-8")

    def row(self, gate):
        """The registry's row of a gate, as a line."""
        found = [line for line in self.text(self.gates).splitlines() if line.startswith("| %s |" % gate)]
        self.assertEqual(len(found), 1, found)
        return found[0]

    def test_restart_assigns_next_free_number(self):
        before = self.route()
        writes, real = [], migrate.replace

        def recording(path, data, like=None):
            writes.append((path, data))
            return real(path, data, like)

        with mock.patch.object(migrate, "replace", recording):
            self.assertEqual(self.restart(), "code-03")
        self.assertEqual(writes[0], (self.gates, (before + "code-01 restarts as code-03\n").encode("utf-8")))
        self.assertTrue((self.root / "code-03").is_dir())

    def test_restart_copies_saved_inputs(self):
        with self.subTest("git gate"):
            self.route(rows=[("code-01", "open (codex)")],
                       files={"code-01/base-sha": "c0ffee\n", "code-01/thread-id": "ctx_1\n"})
            self.assertEqual(self.restart(), "code-03")
            new = self.root / "code-03"
            self.assertEqual(sorted(os.listdir(str(new))), ["base-sha", "inputs.json", "ledger.md"])
            self.assertEqual(self.text(new / "base-sha"), "c0ffee\n")
            self.assertEqual((new / "inputs.json").read_bytes(), self.given.read_bytes())
        with self.subTest("parallel gate"):
            self.route(files={"code-01/codex/base-sha": "a1\n", "code-01/kimi/base-sha": "b2\n",
                              "code-01/codex/thread-id": "ctx_1\n"})
            self.assertEqual(self.restart(), "code-03")
            new = self.root / "code-03"
            self.assertEqual(sorted(os.listdir(str(new))), ["codex", "inputs.json", "kimi", "ledger.md"])
            self.assertEqual(os.listdir(str(new / "codex")), ["base-sha"])
            self.assertEqual((self.text(new / "codex" / "base-sha"), self.text(new / "kimi" / "base-sha")),
                             ("a1\n", "b2\n"))
        with self.subTest("snapshot gate"):
            stale = self.project / OLD / "r1" / "polish-01" / "base" / "wc" / "count.py"
            original = self.project / "notes.txt"
            self.route(rows=[("code-01", "closed"), ("polish-01", "open (codex)")], waiting="polish-01",
                       files={"polish-01/base/wc/count.py": "old count\n", "polish-01/base/notes.txt": "old notes\n",
                              "polish-01/base/spec.md": "old spec\n", "polish-01/thread-id": "ctx_1\n"},
                       scratch=self.root / "polish-01",
                       snapshots=[(str(stale), "wc/count.py"),
                                  (str(self.root / "polish-01" / "base" / "notes.txt"), str(original)),
                                  (str(self.root / "polish-01" / "base" / "spec.md"),
                                   str(self.project / OLD / "r1" / "spec.md"))])
            self.assertEqual(self.restart("polish-01"), "polish-02")
            new = self.root / "polish-02"
            self.assertEqual(sorted(os.listdir(str(new))), ["inputs.json", "ledger.md", "snapshots", "snapshots.txt"])
            pairs = [line.split(" -> ") for line in self.text(new / "snapshots.txt").splitlines()]
            # An original under the old root is mapped to its place under the moved one, like a copy.
            self.assertEqual([original for _, original in pairs],
                             ["wc/count.py", str(original), str(self.root / "spec.md")])
            self.assertEqual([Path(copy).parent for copy, _ in pairs], [new / "snapshots"] * 3)
            self.assertEqual([self.text(Path(copy)) for copy, _ in pairs], ["old count\n", "old notes\n", "old spec\n"])
            self.assertEqual(len(os.listdir(str(new / "snapshots"))), 3)

    def test_restart_writes_known_items_and_outcomes(self):
        self.route(files=PARALLEL, carry=CARRY, locked=["codex", "kimi"])
        self.assertEqual(self.restart(), "code-03")
        new = self.root / "code-03"
        self.assertEqual(self.text(new / "codex" / "known-items.md"), "\n".join(CARRY["codex"]) + "\n")
        self.assertFalse(os.path.lexists(str(new / "kimi" / "known-items.md")))
        self.assertEqual(self.text(self.root / "code-01" / "codex" / "ledger.md"),
                         PARALLEL["code-01/codex/ledger.md"] + "carried to code-03/C1\ncarried to code-03/C2\n")
        self.assertEqual(self.text(self.root / "code-01" / "kimi" / "ledger.md"), PARALLEL["code-01/kimi/ledger.md"])
        self.assertEqual(self.text(self.root / "code-01" / "ledger.md"), PARALLEL["code-01/ledger.md"])
        self.assertEqual(self.text(new / "ledger.md"), BASE_LINE + "\n")
        self.assertEqual(self.row("code-03"),
                         "| code-03 | scope | %s | open (restarted from code-01; codex, kimi) | |" % new)
        self.assertEqual(self.row("code-01"), "| code-01 | scope | %s | closed: superseded by code-03 (migration) "
                                              "| proof |" % (self.root / "code-01"))
        self.assertEqual(self.text(self.gates).splitlines()[-1], "code-01 superseded by code-03")
        self.assertEqual(migrate.unclosed_gates(self.text(self.gates)), ["code-03"])
        with self.subTest("one reviewer, its ledger at the gate's root"):
            self.route(rows=[("code-01", "open (codex)")], carry={"codex": CARRY["codex"][:1]},
                       files={"code-01/ledger.md": BASE_LINE + "\n| C1 | 01 | newline | open |\n"})
            self.restart()
            self.assertEqual(self.text(self.root / "code-01" / "ledger.md"),
                             BASE_LINE + "\n| C1 | 01 | newline | open |\ncarried to code-03/C1\n")
            self.assertEqual(self.text(new / "codex" / "known-items.md"), CARRY["codex"][0] + "\n")

    def test_restart_resumes_after_each_step(self):
        self.route(files=PARALLEL, carry=CARRY)
        writes, real = [], migrate.replace

        def counting(path, data, like=None):
            writes.append(path)
            return real(path, data, like)

        with mock.patch.object(migrate, "replace", counting):
            self.restart()
        end = snapshot(self.project)
        changed = {"codex": ["C9 — elsewhere — another claim"]}

        def finish(variant):
            if variant == "deleted":
                self.given.unlink()
            elif variant == "changed":
                self.inputs(changed)
            self.assertEqual(self.restart(), "code-03")
            self.assertEqual(snapshot(self.project), end)

        for done in range(1, len(writes)):
            for variant in ["given"] if done == 1 else ["deleted", "changed"]:
                with self.subTest(writes=done, inputs=variant):
                    self.route(files=PARALLEL, carry=CARRY)
                    count = []

                    def interrupting(path, data, like=None):
                        if len(count) == done:
                            raise Stop()
                        count.append(path)
                        return real(path, data, like)

                    with mock.patch.object(migrate, "replace", interrupting), self.assertRaises(Stop):
                        self.restart()
                    finish(variant)
        for variant in ["deleted", "changed"]:
            with self.subTest("half the carried-to marks", inputs=variant):
                text = self.route(files=PARALLEL, carry=CARRY)
                self.gates.write_text(text + "code-01 restarts as code-03\n", encoding="utf-8")
                (self.root / "code-03").mkdir()
                shutil.copyfile(str(self.given), str(self.root / "code-03" / "inputs.json"))
                with (self.root / "code-01" / "codex" / "ledger.md").open("a", encoding="utf-8") as handle:
                    handle.write("carried to code-03/C1\n")
                finish(variant)
            with self.subTest("the rows updated, no outcome line", inputs=variant):
                self.route(files=PARALLEL, carry=CARRY)
                self.restart()
                lines = self.text(self.gates).splitlines(True)
                self.assertEqual(lines[-1], "code-01 superseded by code-03\n")
                self.gates.write_text("".join(lines[:-1]), encoding="utf-8")
                finish(variant)

    def test_restart_keeps_the_locked_set(self):
        column = ("| Gate | Scope | Scratch | Reviewers (locked) | State | Proof |\n|---|---|---|---|---|---|\n"
                  "| code-01 | scope | %s | `codex`, `kimi` | open (codex, kimi) | |\n"
                  "Migrated %s: restart on resume: code-01\n" % (self.root / "code-01", TODAY))
        new = self.root / "code-03"
        for name, kwargs, expected in [
                ("the inputs' set over the line", {"head": "Reviewers: codex\n\n", "rows": [("code-01", "open")],
                                                    "locked": ["codex", "kimi"]},
                 "| code-03 | scope | %s | open (restarted from code-01; codex, kimi) | |" % new),
                ("none given, keys in the old State", {},
                 "| code-03 | scope | %s | open (restarted from code-01) | |" % new),
                ("none given, a locked column", {"text": "Reviewers: codex\n\n" + column},
                 "| code-03 | scope | %s | | open (restarted from code-01) | |" % new)]:
            with self.subTest(name):
                self.route(**kwargs)
                self.restart()
                self.assertEqual(self.row("code-03"), expected)

    def test_restart_reads_the_given_scratch(self):
        # The old attempt's scratch is what the executor read from the row, a retry path with a space included;
        # the default code-01/ holds another base, so a fallback to it shows.
        new = self.root / "code-03"
        files = {"code-01/base-sha": "r0\n", "code-01 retry/base-sha": "r1\n", "code-01 retry/kimi/base-sha": "b2\n",
                 "code-01 retry/codex/ledger.md": PARALLEL["code-01/codex/ledger.md"]}
        for name, scratch in [("after the move", self.root / "code-01 retry"),
                              ("before the move", self.project / OLD / "r1" / "code-01 retry")]:
            with self.subTest(name):
                self.route(files=files, carry=CARRY, scratch=scratch)
                result = self.cli("code-01")
                self.assertEqual((result.stdout.splitlines(), result.returncode),
                                 (["RESTART code-01 -> code-03"], 0), result.stderr)
                self.assertEqual(sorted(os.listdir(str(self.root))),
                                 ["code-01", "code-01 retry", "code-02", "code-03", "gates.md"])
                self.assertEqual([self.text(new / rel) for rel in ["base-sha", "kimi/base-sha"]], ["r1\n", "b2\n"])
                self.assertEqual(self.text(self.root / "code-01 retry" / "codex" / "ledger.md"),
                                 PARALLEL["code-01/codex/ledger.md"] + "carried to code-03/C1\ncarried to code-03/C2\n")
                self.assertEqual(self.row("code-03"),
                                 "| code-03 | scope | %s | open (restarted from code-01) | |" % new)

    def test_restart_skips_numbers_taken_by_retries(self):
        # A name that starts with code-03 and goes on with a non-digit takes 03: a directory or a registry token.
        for name in ["directory", "registry token"]:
            with self.subTest(name):
                text = self.route()
                if name == "directory":
                    (self.root / "code-03-retry").mkdir()
                else:
                    self.gates.write_text(text + "Retry scratch: %s/code-03-retry\n" % self.root, encoding="utf-8")
                self.assertEqual(self.restart(), "code-04")
                self.assertTrue((self.root / "code-04" / "inputs.json").is_file())

    def test_restart_writes_the_given_header(self):
        # The old ledger's three opening lines, as the executor read them, with the old root's paths rewritten.
        header = ("Base: a1b2c3.\nScope: file: %s/spec.md.\nWorking directory: %s.\n"
                  % (self.project / OLD / "r1", self.project))
        self.route(files={"code-01/ledger.md": "Scope: elsewhere.\n| #1 | 01 | quote | open |\n"}, header=header)
        self.restart()
        self.assertEqual(self.text(self.root / "code-03" / "ledger.md"),
                         header.replace(str(self.project / OLD), str(self.project / NEW)))

    def test_restart_without_a_header_writes_no_ledger(self):
        # A gate never dispatched has no ledger to read a header from: the new gate gets none either.
        self.route(rows=[("code-01", "open")], header="")
        self.assertEqual(self.restart(), "code-03")
        self.assertEqual(sorted(os.listdir(str(self.root / "code-03"))), ["inputs.json"])

    def test_restart_of_a_gate_never_prepared(self):
        # An open gate whose scratch was never made: the executor gives null, nothing is copied, it is renumbered.
        self.route(rows=[("plan-01", "open")], waiting="plan-01", header="")
        data = json.loads(self.given.read_text(encoding="utf-8"))
        data["scratch"] = None
        self.given.write_text(json.dumps(data), encoding="utf-8")
        result = self.cli("plan-01")
        self.assertEqual((result.stdout.splitlines(), result.returncode), (["RESTART plan-01 -> plan-02"], 0),
                         result.stderr)
        self.assertEqual(os.listdir(str(self.root / "plan-02")), ["inputs.json"])
        self.assertEqual(self.row("plan-02"),
                         "| plan-02 | scope | %s | open (restarted from plan-01) | |" % (self.root / "plan-02"))

    def test_restart_refuses_a_scratch_outside_the_route(self):
        # A scratch read from the wrong row or folder: nothing of it is copied and its ledger is not marked.
        another = self.project / "another"
        for scratch in [another, self.root / "code-01" / ".." / ".." / ".." / "another", self.root]:
            with self.subTest(str(scratch)):
                self.route(files=PARALLEL, carry=CARRY, scratch=scratch)
                (another / "codex").mkdir(parents=True)
                (another / "base-sha").write_text("f00d\n", encoding="utf-8")
                (another / "codex" / "ledger.md").write_text(PARALLEL["code-01/codex/ledger.md"], encoding="utf-8")
                before = snapshot(self.project)
                result = self.cli("code-01")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertTrue(result.stdout.startswith("REFUSE "), result.stdout)
                self.assertIn("outside the route root", result.stdout)
                self.assertEqual(snapshot(self.project), before)

    def test_restart_keeps_a_scope_with_a_pipe(self):
        # The scope stays literal; only a table cell escapes its `|`.
        new = self.root / "code-03"
        with self.subTest("prose registry"):
            self.route(text=PROSE, scope="file a|b.md")
            self.assertEqual(self.restart(), "code-03")
            self.assertIn("code-03: open (restarted from code-01); scope: file a|b.md; scratch: %s\n" % new,
                          self.text(self.gates))
        with self.subTest("table registry"):
            self.route(scope="file a|b.md")
            self.assertEqual(self.restart(), "code-03")
            self.assertEqual(self.row("code-03"),
                             "| code-03 | file a\\|b.md | %s | open (restarted from code-01) | |" % new)
            self.assertEqual(migrate.unclosed_gates(self.text(self.gates)), ["code-03"])
            _, rows = migrate.table(self.text(self.gates).splitlines())
            self.assertEqual([cells[1] for _, cells in rows if cells[0] == "code-03"], ["file a\\|b.md"])

    def test_restart_carries_each_id_once(self):
        carry = {"codex": [CARRY["codex"][0], CARRY["codex"][0], CARRY["codex"][1]]}
        self.route(files=PARALLEL, carry=carry)
        self.restart()
        new = self.root / "code-03"
        self.assertEqual(self.text(new / "codex" / "known-items.md"), "\n".join(CARRY["codex"]) + "\n")
        self.assertEqual(self.text(self.root / "code-01" / "codex" / "ledger.md"),
                         PARALLEL["code-01/codex/ledger.md"] + "carried to code-03/C1\ncarried to code-03/C2\n")

    def test_restart_finds_the_scratch_under_a_root_with_a_space(self):
        self.project = self.tmp / "My Project"
        self.root = self.project / NEW / "r1"
        self.gates = self.root / "gates.md"
        new = self.root / "code-03"
        files = {"code-01/base-sha": "r0\n", "code-01/ledger.md": "# code-01 ledger\n" + BASE_LINE + "\n",
                 "code-01/codex/ledger.md": PARALLEL["code-01/codex/ledger.md"]}
        annotated = ("| Gate | Scope | Scratch | State | Proof |\n|---|---|---|---|---|\n"
                     "| code-01 | scope | %s (codex/, kimi/) | open (codex, kimi) | |\n"
                     "Migrated %s: restart on resume: code-01\n" % (self.root / "code-01", TODAY))
        for name, kwargs, extra in [("plain", {"rows": [("code-01", "open (codex)")]}, []),
                                    ("reviewer scratches named", {"text": annotated, "carry": CARRY}, ["codex"])]:
            with self.subTest(name):
                self.route(files=files, **kwargs)
                result = self.cli("code-01")
                self.assertEqual((result.stdout.splitlines(), result.returncode),
                                 (["RESTART code-01 -> code-03"], 0), result.stderr)
                self.assertEqual(sorted(os.listdir(str(new))), sorted(["base-sha", "inputs.json", "ledger.md"] + extra))
                self.assertEqual((self.text(new / "base-sha"), self.text(new / "ledger.md")),
                                 ("r0\n", BASE_LINE + "\n"))
                self.assertEqual(self.row("code-03"),
                                 "| code-03 | scope | %s | open (restarted from code-01) | |" % new)

    def test_restart_reports_nothing(self):
        self.route(carry=CARRY, files=PARALLEL)
        self.restart()
        before = snapshot(self.project)
        for gate in ["code-01", "spec-01", "code-03", "plan-04"]:
            with self.subTest(gate):
                result = self.cli(gate)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
                self.assertTrue(result.stdout.startswith("NOTHING %s: " % gate), result.stdout)
                self.assertEqual(snapshot(self.project), before)
        with self.subTest("the restart itself"):
            self.route(carry=CARRY, files=PARALLEL)
            result = self.cli("code-01")
            self.assertEqual((result.stdout.splitlines(), result.returncode), (["RESTART code-01 -> code-03"], 0),
                             result.stderr)
        with self.subTest("no marker"):
            self.route(waiting="")
            before = snapshot(self.project)
            result = self.cli("code-01")
            self.assertEqual((result.stdout.splitlines(), result.returncode),
                             (["NOTHING code-01: no migration marker"], 0), result.stderr)
            self.assertEqual(snapshot(self.project), before)

    def test_two_resumes_pick_the_same_attempt(self):
        self.route(files=PARALLEL, carry=CARRY)
        self.assertEqual(self.restart(), "code-03")
        (self.root / "code-03" / "thread-id").write_text("ctx_9\n", encoding="utf-8")
        before = snapshot(self.project)
        self.assertEqual(migrate.unclosed_gates(self.text(self.gates)), ["code-03"])
        for gate in ["code-01", "code-03"]:
            result = self.cli(gate)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith("NOTHING %s: " % gate), result.stdout)
        self.assertEqual(snapshot(self.project), before)

    def test_restart_reads_an_unknown_registry(self):
        new = self.root / "code-03"
        table = ("| id | what | where | status |\n| code-01 | wc | %s | open |\n"
                 "Migrated %s: restart on resume: unknown\n" % (self.root / "code-01", TODAY))
        for name, text, added in [
                ("prose", PROSE, "code-03: open (restarted from code-01); scope: scope; scratch: %s" % new),
                ("a table without the header", table,
                 "| code-03 | scope | %s | open (restarted from code-01) | |" % new)]:
            with self.subTest(name):
                self.route(text=text, files={"code-01/base-sha": "c0ffee\n"})
                result = self.cli("code-01")
                self.assertEqual((result.stdout.splitlines(), result.returncode),
                                 (["RESTART code-01 -> code-03"], 0), result.stderr)
                self.assertEqual(self.text(self.gates), text + "code-01 restarts as code-03\n%s\n"
                                 "code-01 superseded by code-03\n" % added)
                self.assertEqual(self.text(new / "base-sha"), "c0ffee\n")
                before = snapshot(self.project)
                for gate in ["code-03", "code-05"]:
                    result = self.cli(gate)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue(result.stdout.startswith("NOTHING %s: " % gate), result.stdout)
                self.assertEqual(snapshot(self.project), before)
        with self.subTest("prose, with the lock the executor read"):
            self.route(text=PROSE, locked=["codex"])
            self.assertEqual(self.restart(), "code-03")
            self.assertIn("code-03: open (restarted from code-01; codex); scope: scope; scratch: %s\n" % new,
                          self.text(self.gates))

    def test_restart_refuses_bad_inputs(self):
        missing = str(self.root / "polish-01" / "base" / "gone.py")
        no_ledger = {"code-01/codex/base-sha": "a1\n", "code-01/kimi/ledger.md": PARALLEL["code-01/kimi/ledger.md"]}
        for name, given, gate, files in [
                ("not json", "{", "code-01", PARALLEL),
                ("carry not a map", '{"carry": [], "snapshots": []}', "code-01", PARALLEL),
                ("a key that is not a scratch key", {"carry": {"../x": CARRY["codex"]}}, "code-01", PARALLEL),
                ("a line without its parts", {"carry": {"codex": ["C1 off by one"]}}, "code-01", PARALLEL),
                ("a missing snapshot copy", {"snapshots": [[missing, "gone.py"]]}, "code-01", PARALLEL),
                ("a lock that is not a key list", {"locked": "codex, kimi"}, "code-01", PARALLEL),
                ("carried items with no ledger to mark", {"carry": CARRY}, "code-01", no_ledger),
                ("no inputs file", None, "code-01", PARALLEL),
                ("not a gate id", {}, "code-1", PARALLEL),
                ("no scratch", {"drop": ["scratch"]}, "code-01", PARALLEL),
                ("a scratch that does not exist", {"scratch": self.root / "code-01 gone"}, "code-01", PARALLEL),
                ("no scope", {"drop": ["scope"]}, "code-01", PARALLEL),
                ("no header", {"drop": ["header"]}, "code-01", PARALLEL),
                ("a scope of two lines", {"scope": "wc/count.py\ntests"}, "code-01", PARALLEL),
                ("one id with two claims",
                 {"carry": {"codex": [CARRY["codex"][0], "C1 — elsewhere — another claim"]}}, "code-01", PARALLEL)]:
            with self.subTest(name):
                self.route(files=files)
                if given is None:
                    self.given.unlink()
                elif isinstance(given, str):
                    self.given.write_text(given, encoding="utf-8")
                else:
                    self.inputs(**given)
                before = snapshot(self.project)
                result = self.cli(gate)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
                self.assertTrue(result.stdout.startswith("REFUSE "), result.stdout)
                self.assertEqual(snapshot(self.project), before)


class RunThenRestartTest(MigrationCase):
    def test_new_row_stays_in_a_table_that_ends_the_file(self):
        self.init()
        old, new = self.scratch(self.top), self.top / NEW
        header = "| Gate | Scope | Scratch | State | Proof |"
        rows = ["| %s | scope | %s/%s | %s | proof |" % (gate, old / "r1", gate, state) for gate, state in R1]
        text = "\n".join(["# Route r1", "", header, "|---|---|---|---|---|"] + rows) + "\n"
        (old / "r1" / "gates.md").write_text(text, encoding="utf-8")
        (old / "r1" / "code-01").mkdir()
        self.assertEqual(self.cli("run").returncode, 0)
        gates, given = new / "r1" / "gates.md", self.tmp / "inputs.json"
        given.write_text(json.dumps({"carry": {}, "snapshots": [], "scratch": str(old / "r1" / "code-01"),
                                     "scope": "scope", "header": BASE_LINE}), encoding="utf-8")
        result = run_script(self.top, ["restart", str(gates), "code-01", str(given)])
        self.assert_prints(result, ["RESTART code-01 -> code-02"], 0)
        text = gates.read_text(encoding="utf-8")
        lines = text.splitlines()
        last = max(index for index, line in enumerate(lines) if line.startswith("|"))
        table = lines[lines.index(header):last + 1]
        self.assertTrue(all(line.startswith("|") for line in table), text)
        self.assertTrue(any(line.startswith("| code-02 |") for line in table), text)
        self.assertEqual(migrate.unclosed_gates(text), ["code-02"])


if __name__ == "__main__":
    unittest.main()
