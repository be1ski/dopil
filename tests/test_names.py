"""Check that the plugin's old name is gone: the matcher over every tracked file, and the renamed markers agree."""

import importlib.util
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Set
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
# The old name is built from parts, so this file is scanned like any other.
OLD = "sh" + "ip"
NEW = "dopil"
PATTERN = re.compile(r"(?<![a-z])" + OLD + r"(?![a-z])", re.I)
# Tracked path -> exact literals that may still hold the old name there, each only as a whole path component.
# The migration script, its tests and the migration rule's text name the old scratch and its pointer directory;
# a path below the scratch, such as its routes/ or .gitignore, passes as a whole component of the first.
MIGRATION = ["." + OLD, OLD + "-routes"]
ALLOWLIST: Dict[str, Set[str]] = {
    "skills/dopil/references/migrate.py": set(MIGRATION),
    "tests/test_migrate.py": set(MIGRATION),
    "skills/dopil/references/ledger.md": set(MIGRATION),
    "tests/live/cases.md": set(MIGRATION),
}
# A path whose literals are allowed only in one `## ` section, from its heading to the next `## ` heading:
# the live kit's case M writes the old layout, and no other case may name it.
SECTIONS = {"tests/live/cases.md": "## Group M: "}
BEFORE = set("/\"'`(")
AFTER = set("/\"'`),;:")
AGENTS = ROOT / "skills" / NEW / "references" / "agents"


def is_component(line, start, end):
    """Whether line[start:end] stands as a whole path component."""
    if start > 0 and not (line[start - 1] in BEFORE or line[start - 1].isspace()):
        return False
    if end == len(line) or line[end] in AFTER or line[end].isspace():
        return True
    return line[end] == "." and not (end + 1 < len(line) and line[end + 1].isalnum())


def allowed(line, start, end, literals):
    """Whether the hit line[start:end] lies inside an allowed literal that is a whole component of the line."""
    for literal in literals:
        at = line.find(literal)
        while at != -1:
            if at <= start and end <= at + len(literal) and is_component(line, at, at + len(literal)):
                return True
            at = line.find(literal, at + 1)
    return False


def bad_hits(line, literals):
    return [hit for hit in PATTERN.finditer(line) if not allowed(line, hit.start(), hit.end(), literals)]


def find_old_names(path: str, text: str) -> List[str]:
    """Every hit of the old name in the path or its text outside the path's allowlist, as `path:line: text`."""
    literals = ALLOWLIST.get(path, set())
    heading = SECTIONS.get(path)
    inside = heading is None  # the path itself is outside every section
    found = []
    if bad_hits(path, literals if inside else set()):
        found.append("%s:path: %s" % (path, path))
    for number, line in enumerate(text.split("\n"), 1):
        if heading is not None and line.startswith("## "):
            inside = line.startswith(heading)
        if bad_hits(line, literals if inside else set()):
            found.append("%s:%d: %s" % (path, number, line.strip()))
    return found


FOREIGN_GIT = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR"]


def tracked_files(root: Path) -> List[str]:
    """The paths git tracks under root, listed without the caller's variables that point git at another repository
    or index, as the migration script runs git."""
    env = {name: value for name, value in os.environ.items() if name not in FOREIGN_GIT}
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=str(root), env=env, check=True,
                            stdout=subprocess.PIPE).stdout.decode("utf-8")
    return [rel for rel in listed.split("\0") if rel]


def scan(root: Path) -> List[str]:
    """Every old-name hit in the tracked paths under root and in their content, as find_old_names reports it."""
    found = []
    for rel in tracked_files(root):
        path = root / rel
        text = path.read_bytes().decode("utf-8", "replace") if path.is_file() else ""
        found.extend(find_old_names(rel, text))
    return found


def front_matter_name(path):
    match = re.search(r"\A---\n(?:.*\n)*?name: (\S+)\n", path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


class NamesTest(unittest.TestCase):
    def test_no_old_name_outside_allowlist(self):
        self.assertIn("skills/dopil/SKILL.md", tracked_files(ROOT), "the listing misses the plugin's files")
        found = scan(ROOT)
        self.assertEqual(found, [], "\n".join(found))

    def test_scan_ignores_inherited_git_variables(self):
        # A hook or a wrapper may hand down an index or git dir of its own; the listing must stay this repository's,
        # so a planted name still fails the scan.
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            clean = {name: value for name, value in os.environ.items() if name not in FOREIGN_GIT}
            subprocess.run(["git", "init", "-q", str(repo)], check=True, env=clean, stdout=subprocess.DEVNULL)
            (repo / "notes.md").write_text("run $" + OLD + " <task>\n", encoding="utf-8")
            subprocess.run(["git", "add", "notes.md"], cwd=str(repo), check=True, env=clean)
            foreign = {"GIT_INDEX_FILE": str(repo / "empty-index"), "GIT_DIR": str(repo / "elsewhere")}
            with mock.patch.dict(os.environ, foreign):
                self.assertIn("skills/dopil/SKILL.md", tracked_files(ROOT))
                self.assertEqual(scan(repo), ["notes.md:1: run $" + OLD + " <task>"])

    def test_matcher_ignores_words_containing_the_letters(self):
        self.assertEqual(find_old_names("notes.md", "ships with ownership relationship shipped"), [])
        for form in ["$" + OLD + " <task>", "a/." + OLD + "/r1", OLD.upper() + "_GATE",
                     "/" + OLD + ":" + OLD, OLD + "-routes/id.txt"]:
            self.assertEqual(find_old_names("notes.md", form), ["notes.md:1: " + form], form)

    def test_matcher_allows_whole_components_of_allowlisted_literals(self):
        path = "skills/dopil/references/migrate.py"
        for form in ["<top>/." + OLD + "/r1", "a/b/." + OLD, "It moves ." + OLD + ".", "`" + OLD + "-routes`",
                     "(." + OLD + "/.gitignore)"]:
            self.assertEqual(find_old_names(path, form), [], form)

    def test_matcher_rejects_planted_names(self):
        path = "skills/dopil/references/migrate.py"
        self.assertEqual(find_old_names(path, "x = 1\n" + OLD.upper() + "_ROOT=/tmp\n"),
                         [path + ":2: " + OLD.upper() + "_ROOT=/tmp"])
        self.assertEqual(find_old_names(path, "d=" + OLD + "-gemini.x"), [path + ":1: d=" + OLD + "-gemini.x"])
        for form in ["." + OLD + ".backup", OLD + "-routes.bak", "." + OLD + "/" + OLD + "-gemini.x"]:
            self.assertEqual(find_old_names(path, form), [path + ":1: " + form], form)
        moved = "tests/" + OLD + "_notes.md"
        self.assertEqual(find_old_names(moved, "clean\n"), [moved + ":path: " + moved])

    def test_cases_allow_the_migration_literals_only_in_case_m(self):
        path = "tests/live/cases.md"
        dotted, routes = "a/." + OLD + "/r1", "`" + OLD + "-routes`"
        text = "\n".join(["## Group D3: x", dotted, "## Group M: y", "### M-claude · after-only", dotted, routes,
                          "## Group E: z", routes])
        self.assertEqual(find_old_names(path, text), [path + ":2: " + dotted, path + ":8: " + routes])

    def test_antigravity_reviewer_names_agree(self):
        profiles = AGENTS / "antigravity" / "agy-reviewer" / ".agents" / "agents"
        self.assertEqual(sorted(path.name for path in profiles.iterdir()), [NEW + "-reviewer.md"])
        self.assertEqual(front_matter_name(profiles / (NEW + "-reviewer.md")), NEW + "-reviewer")
        card = (AGENTS / "antigravity" / "reviewer.md").read_text(encoding="utf-8")
        launched = re.findall(r"agy_iso --agent (\S+)", card)
        self.assertTrue(launched, "the card launches the profile")
        self.assertEqual(set(launched), {NEW + "-reviewer"})
        self.assertEqual(set(re.findall(r'init\.get\("agent"\) == "([^"]+)"', card)), {NEW + "-reviewer"})
        self.assertEqual(set(re.findall(r"init\.agent is not (\S+)\"", card)), {NEW + "-reviewer"})
        hashed = re.findall(r"\.agents/agents/(\S+\.md)", card)
        self.assertTrue(hashed, "the card pins the profile file")
        self.assertEqual(set(hashed), {NEW + "-reviewer.md"})

    def test_kimi_reviewer_name_agrees(self):
        self.assertEqual(front_matter_name(AGENTS / "kimi" / "kimi-reviewer.md"), NEW + "-reviewer")
        card = (AGENTS / "kimi" / "reviewer.md").read_text(encoding="utf-8")
        files = re.findall(r'--agent-file "([^"]+)"', card)
        self.assertTrue(files, "the card launches the agent file")
        self.assertEqual(set(files), {"<skill-dir>/references/agents/kimi/kimi-reviewer.md"})

    def test_claude_review_owner_agrees(self):
        script = AGENTS / "claude-code" / "review_claude.py"
        spec = importlib.util.spec_from_file_location("review_claude", script)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        self.assertEqual(runner.OWNER, NEW + "-claude-review-v1")
        source = script.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'"owner": (\S+?),', source), ["OWNER"])
        self.assertIn('state.get("owner") != OWNER', source)

    def test_gemini_neutral_directory_agrees(self):
        card = (AGENTS / "antigravity" / "reviewer.md").read_text(encoding="utf-8")
        created = re.findall(r'mktemp -d "\$\{TMPDIR:-/tmp\}/([\w-]+)\.(X+)"', card)
        self.assertEqual(created, [(NEW + "-gemini", "XXXXXXXX")])
        accepted = re.findall(r"\*/([\w-]+)\.(\?+)\)", card)
        self.assertEqual(len(accepted), 2, "the blocker removal and the gate end accept the shape")
        self.assertEqual(set(accepted), {(NEW + "-gemini", "????????")})
        self.assertIn("`" + NEW + "-gemini.<8 characters>`", card)
