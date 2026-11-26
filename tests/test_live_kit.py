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
MIGRATE = ROOT / "skills" / "dopil" / "references" / "migrate.py"
MARKER = ".dopil-live-sandbox"
OLD = "sh" + "ip"  # the previous plugin's name, built from parts as in tests/test_names.py
EXCLUDES = ["/.claude/", "/.agents/", "/" + MARKER, "__pycache__/", "*.pyc"]
GROUPS = ["A", "B", "C", "D", "D3", "M", "E", "R", "F", "H", "I1", "I2"]
# The groups the baseline cannot run (spec, "Verification", step 3): their instances, and only those, are after-only.
AFTER_ONLY_GROUPS = {"D3", "M", "H", "I1", "I2"}
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


def m_settings_rows(loading):
    """The rows of the Loading table that give the coordinator case M's in-sandbox settings edit."""
    return [line for line in loading.splitlines() if line.startswith("|") and "settings.json" in line
            and re.search(r"\b[Cc]ase M\b|\$MSB", line)]


def snapshot(root):
    """Every path under root with its bytes, a directory as None."""
    return {path: None if path.is_dir() else path.read_bytes() for path in sorted(Path(root).rglob("*"))}


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
        self.assertEqual(self.git("log", "-1", "--format=%an <%ae>").strip(), "dopil-live <dopil-live@invalid>")
        self.assertEqual((self.target / MARKER).read_text(encoding="utf-8"), sha + "\n")
        tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], self.env, cwd=str(self.target))
        self.assertEqual(tests.returncode, 0, tests.stderr)
        self.assertEqual(self.git("status", "--porcelain"), "")
        settings = json.loads((self.target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIs(settings["enabledPlugins"]["dopil@dopil"], False)
        for name, source in (("dopil", self.build), ("superpowers", self.superpowers)):
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

    def test_m_old_layout_plans_the_move(self):
        # Case M's precondition: its old route, written into a fresh sandbox, is a scratch `check` plans to move.
        self.assertEqual(self.make().returncode, 0)
        layout = run(["bash", "-c", m_layout_block()], dict(self.env, MSB=str(self.target)))
        self.assertEqual(layout.returncode, 0, layout.stderr)
        check = run([sys.executable, "-I", str(MIGRATE), "check"], self.env, cwd=str(self.target))
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        lines = check.stdout.splitlines()
        # The route, its pointer and the scratch itself; the open code gate, and not the closed spec gate, restarts.
        self.assertEqual(len([line for line in lines if line.startswith("MOVE ")]), 3, check.stdout)
        restart = [line for line in lines if line.startswith("RESTART-LATER ")]
        self.assertEqual(len(restart), 1, check.stdout)
        self.assertTrue(restart[0].startswith("RESTART-LATER %s/.dopil/" % self.target), restart[0])
        self.assertTrue(restart[0].endswith("/gates.md: code-01"), restart[0])
        self.assertFalse([line for line in lines if line.startswith("LEAVE ")], check.stdout)
        self.assertEqual(self.git("status", "--porcelain"), "", "the old layout is ignored")

    def test_m_old_layout_refuses_an_unmarked_target(self):
        # Without a marked sandbox at an absolute MSB, the block stops before any write, wherever the runner stands:
        # MSB unset in a repository, MSB at a repository without the marker, MSB relative to a marked sandbox, and a
        # marked linked worktree, whose git dir is not its own `.git`.
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

    def test_m_old_layout_ignores_inherited_git_variables(self):
        # The runner's shell may point git at another repository; the block reads MSB's own git paths.
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

    def test_skill_files_map_migration_to_m(self):
        rows = table_rows((LIVE / "cases.md").read_text(encoding="utf-8"), "Skill files and their cases")

        def row_of(path):
            found = [row for row in rows if path in re.findall(r"`([^`]+)`", row[0])]
            self.assertEqual(len(found), 1, path)
            return found[0][1]

        self.assertRegex(row_of("references/migrate.py"), r"\bgroup M\b")
        ledger = row_of("references/ledger.md")
        self.assertRegex(ledger, r"\bgroup M\b")
        # Its earlier instances are kept.
        self.assertTrue(ledger.startswith("all except C-claude-several, C-codex-several, E-claude-cancel, E-agy-cancel, "
                                          "E-claude-none and group I2"), ledger)

    def test_m_writes_its_own_sandbox_settings(self):
        # The runner may not edit configuration, so the brief names M's sandbox settings as case setup, once, and
        # the coordinator's "Loading" table does not claim that step.
        case_m = " ".join(m_brief().split())
        for needle in (".claude/settings.json", "not a change to any CLI's configuration"):
            self.assertIn(needle, case_m)
        brief = (LIVE / "runner-brief.md").read_text(encoding="utf-8")
        for heading in ("Roles", "Hard rules"):
            self.assertIn("case M paragraph", section(brief, heading), heading)
        loading = section((LIVE / "runtimes.md").read_text(encoding="utf-8"), "Loading")
        self.assertEqual(m_settings_rows(loading), [])
        planted = loading + "| Claude Code (case M) | the coordinator writes `$MSB/.claude/settings.json` | none |\n"
        self.assertEqual(len(m_settings_rows(planted)), 1, "a planted coordinator row for M's settings")

    def test_m_trust_entries_are_recorded_with_their_undo(self):
        # Case M's sandbox is a second folder each CLI is started in, so its trust entries are recorded and undone.
        rows = table_rows((LIVE / "runtimes.md").read_text(encoding="utf-8"), "Loading")
        trust = [row for row in rows if row[0] == "Trust, every CLI"][0]
        self.assertIn("`$MSB`", trust[1])
        self.assertIn("before M runs", trust[1])
        # The path may have been trusted before: its value is recorded and restored, and only a new entry goes.
        self.assertIn("absent, or the saved value", trust[1])
        self.assertIn("Claude Code's for `$MSB` (recorded before M: absent, or the saved value)", trust[2])
        self.assertIn("for `$MSB`, restore exactly the value recorded before M: remove the entry only when it was "
                      "absent then, an entry this run created, otherwise write the saved value back", trust[3])
        self.assertNotIn("untrusted before", " ".join(trust))

    def test_m_uses_its_own_sandbox_pair(self):
        case_m = m_brief()
        self.assertIn('[ "$MSB" != "$SB" ]', case_m)
        self.assertIn('rm -rf "$MSB"', case_m)
        self.assertNotIn('rm -rf "$SB"', case_m)
        group = m_group()
        self.assertIn("`MSB`", group)
        self.assertIn("`MBASE`", group)
        self.assertIsNone(re.search(r"\$\{?SB\b|<SB>", group), "group M names the kit's sandbox as its own")
        settings = " ".join(group.split("\n2. ", 1)[1].split("\n3. ", 1)[0].split())
        self.assertIn("`$E/M-claude/plugins.json`", settings)
        self.assertIn("any other value makes the case NOT RUN, with that listing kept", settings)

    def test_m_delete_guard_needs_the_marker_and_a_sha(self):
        # The guard lets M's sandbox go only when its marker reads, MBASE is a SHA, they match and it is not SB. The
        # guard and the delete are two commands, so a refusal before the delete and a failed delete stay apart.
        case_m = " ".join(m_brief().split())
        guards = re.findall(r"`(marker=[^`]*)`", case_m)
        self.assertEqual(len(guards), 1, case_m)
        self.assertNotIn("rm ", guards[0])
        self.assertIn('then, only when it exits 0, `rm -rf "$MSB"`', case_m)
        self.assertIn("A guard step that fails deletes nothing: record the step in `$E/M-claude/cleanup.txt`, and the "
                      "case is NOT RUN.", case_m)
        self.assertIn("An `rm -rf` that fails after the guard passed leaves the case's result as observed: record the "
                      "failure in `cleanup.txt` on its own, with what is left of `$MSB` on disk.", case_m)
        sha = "0123456789abcdef0123456789abcdef01234567"
        with tempfile.TemporaryDirectory() as temp:
            for name, marker, mbase, same, passes in [
                    ("marked with its base", sha, sha, False, True),
                    ("no marker, MBASE empty", None, "", False, False),
                    ("empty marker, MBASE empty", "", "", False, False),
                    ("a base that is not a SHA", "base", "base", False, False),
                    ("the kit's sandbox", sha, sha, True, False)]:
                with self.subTest(name):
                    msb = Path(temp) / name.replace(" ", "-").replace(",", "").replace("'", "")
                    msb.mkdir()
                    if marker is not None:
                        (msb / MARKER).write_text(marker + "\n", encoding="utf-8")
                    env = dict(os.environ, MSB=str(msb), SB=str(msb if same else Path(temp) / "kit"), MBASE=mbase)
                    self.assertEqual(run(["bash", "-c", guards[0]], env).returncode == 0, passes)
                    self.assertTrue(msb.exists(), "the guard itself deletes nothing")

    def test_m_keeps_the_registry_at_restart(self):
        group = " ".join(m_group().split())
        self.assertIn("as soon as `RESTART code-01 -> code-02` appears, copy", group)
        assertions = group.split("Assert:", 1)[1]
        self.assertIn("`$E/M-claude/gates-at-restart.md`", group.split("Assert:", 1)[0])
        self.assertIn("in `gates-at-restart.md`, the row `code-02` `open (restarted from code-01", assertions)

    def test_baseline_is_an_earlier_dopil_export(self):
        # Every standard pair's baseline is an earlier dopil export; the old plugin's layout belongs to case M alone.
        cases = (LIVE / "cases.md").read_text(encoding="utf-8")
        before, group_m = cases.split("\n## Group M: ", 1)
        outside_m = before + "\n## " + group_m.split("\n## ", 1)[1]
        self.assertNotIn("574afe1", outside_m)
        intro = cases.split("\n## ", 1)[0]
        self.assertIn("an earlier dopil export", intro)
        self.assertNotIn("adapter", intro)
        note = section(cases, "Skill files and their cases").split("\n|", 1)[0]
        self.assertIn("an earlier dopil export", note)
        self.assertNotIn("adapter", note)
        proof = section((LIVE / "runner-brief.md").read_text(encoding="utf-8"), "Build proof, every case")
        self.assertIn("an earlier dopil export", proof)
        self.assertNotIn("adapter", proof)

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
        for needle in ("/dopil:do", "slash-probe.txt", "/dopil:dopil", "NOT RUN"):
            self.assertTrue(needle in proof, "missing: " + needle)

    def test_runner_scratch_is_own(self):
        self.assertTrue("scratch" in section((LIVE / "runner-brief.md").read_text(encoding="utf-8"), "Hard rules"))

    def test_kit_has_no_instruction_file_names(self):
        names = [path.relative_to(LIVE).as_posix() for path in LIVE.rglob("*")
                 if path.name.lower() in INSTRUCTION_FILES]
        self.assertEqual(names, [])


if __name__ == "__main__":
    unittest.main()
