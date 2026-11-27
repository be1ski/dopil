"""Check the repository tree: manifests, references, agent folders, denylist."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
             ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json",
             ".kimi-plugin/plugin.json", ".antigravity-plugin/plugin.json"]
MARKETPLACES = [".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"]
SKILLS = ["skills/dopil/SKILL.md", "skills/pragmatic-engineering/SKILL.md"]
REFERENCES = "skills/dopil/references"
AGENTS = ROOT / REFERENCES / "agents"
REVIEWER_PARTS = ["Contract card", "Requirements", "Preparation and pin", "Calls", "Acceptance", "Prompts",
                  "Orca", "Gate end", "Access", "Pitfalls"]
EXECUTOR_PARTS = ["Identity", "Tools", "Models", "Route skills", "Instructions", "Runs that cannot take an answer",
                  "Orca writing workers", "Follow-ups", "Stop", "Recovery", "Closing", "Pitfalls"]
# A part the generic row covers: one line naming that row of references/executor.md.
DEFERRAL = re.compile(r"As references/executor\.md, (.+)\.")
IDENTITY_SCRIPTS = ["kimi", "antigravity"]
KIMI_SUBAGENT_CHECK = 'python3 -I "<skill-dir>/references/agents/kimi/identity.py" <agent_id>'
INLINE_IDENTITY = "python3 -I - <<'PY'"
# Profile directories a card copies whole, under AGENTS: their required files, and nothing else.
PROFILES = {"antigravity/agy-reviewer": ["settings.json", ".agents/agents/dopil-reviewer.md"]}
# Descriptor fields by role (references/contracts.md); a field outside its role is absent.
ALWAYS = ["Name", "Executor card", "Reviewer card"]
EXECUTOR = ["Invocation", "Default reviewer"]
REVIEWER = ["Binary", "Reviewer name", "Reviewer vendor", "Scratch key", "Finding prefix", "Order"]
FORMATS = {"Scratch key": re.compile(r"[a-z0-9-]+"),
           "Finding prefix": re.compile(r"[A-Z]"),
           "Order": re.compile(r"[1-9][0-9]*")}
ROW = re.compile(r"^\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$")
SEPARATOR = re.compile(r"[-:]+")
# Descriptor fields whose values name an agent; the core names none of them.
AGENT_TOKEN_FIELDS = ["Name", "Reviewer name", "Binary", "Reviewer vendor", "Scratch key"]
FIRST_TOKEN = re.compile(r"[A-Za-z0-9-]+")
# Instruction file names the core may mention although they contain an agent's name.
INSTRUCTION_FILES = re.compile(r"CLAUDE\.md|AGENTS\.md|GEMINI\.md")
# What the repository's .gitignore leaves out of the tree; none of it is part of the skill.
IGNORED = {".DS_Store", "__pycache__", ".dopil"}

# Names under references/ that another tool resolves, each with the sentence that shows it.
EXTERNAL_REFERENCES = {
    # adapter-orca.md: "Read `failedStage` in the receipt and act per
    # `ORCA skills get orchestration --reference references/recovery-and-cleanup.md`."
    "recovery-and-cleanup.md",
}
# Bare backticked names of files the skill creates at run time.
RUNTIME_ARTIFACTS = {
    "gates.md",
    "ledger.md",
    # agents/claude-code/reviewer.md, of the gate scratch: "It holds `round-prompt.md`, `ledger.md`,
    # `reviewer.json`, `thread-id`, `last-review.txt` and the raw responses."
    "round-prompt.md",
    # references/ledger.md, "Migration of an old scratch": a carried reviewer's file in a restarted gate's scratch.
    "known-items.md",
}

# A path under references/: a file, a directory or a glob over them, without trailing punctuation. A `<placeholder>`
# in a segment stands for any name: the path is checked as a glob with `*` in its place.
PLACEHOLDER = r"<[^/<>\s]+>"
REFERENCE = re.compile(r"references/((?:(?:[\w.*-]|{0})+/)*(?:(?:[\w.*-]|{0})*(?:[\w*-]|{0}))?)".format(PLACEHOLDER))
BARE = re.compile(r"`([a-z0-9-]+\.md)`")
DENYLIST = re.compile(r"~/\.agents/skills/dopil|be1ski"
                      r"|claude-(?:opus|sonnet|haiku|fable)-[0-9]|gpt-[0-9]"
                      r"|(?<![.\w])kimi-code/[A-Za-z0-9]"
                      r"|gemini-[0-9]")
DENYLIST_SCOPE = ["skills", "tests/live"]


def has_version(node):
    if isinstance(node, dict):
        return "version" in node or any(has_version(v) for v in node.values())
    if isinstance(node, list):
        return any(has_version(v) for v in node)
    return False


def descriptor_rows(path):
    """Return the (field, value) rows of an agent.md table, without header, separator or backticks."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match and match.group(1) != "Field" and not SEPARATOR.fullmatch(match.group(1)):
            rows.append((match.group(1), match.group(2).strip("`")))
    return rows


def descriptors():
    """Return {folder name: {field: value}} for every references/agents/*/agent.md."""
    return {path.parent.name: dict(descriptor_rows(path)) for path in sorted(AGENTS.glob("*/agent.md"))}


def scanned_files():
    """Return SKILL.md and every file under references/ that is not of a kind the repository ignores."""
    files = sorted(path for path in (ROOT / REFERENCES).rglob("*")
                   if not IGNORED.intersection(path.relative_to(ROOT).parts) and path.is_file())
    return [ROOT / SKILLS[0]] + files


def agent_folder(path):
    """Return AGENTS/<folder> for a file inside an agent folder, else None."""
    parts = path.relative_to(AGENTS).parts if AGENTS in path.parents else ()
    return AGENTS / parts[0] if len(parts) > 1 else None


def named_cards(values):
    """Return the card file names a descriptor's fields name."""
    return sorted({values.get(field, "none") for field in ["Executor card", "Reviewer card"]} - {"none"})


def card_parts(path):
    """Return [(heading, body)] for the "## " headings of a card, outside fenced blocks."""
    parts, fenced = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        fenced = fenced != line.startswith("```")
        if not fenced and line.startswith("## "):
            parts.append((line[3:].strip(), []))
        elif parts:
            parts[-1][1].append(line)
    return [(heading, "\n".join(body).strip()) for heading, body in parts]


def deferral(body):
    """Return the executor.md row a one-line deferral names, else None."""
    match = DEFERRAL.fullmatch(body.replace("`", "").replace("*", ""))
    return match.group(1) if match and "\n" not in body else None


def executor_cards():
    """Return {folder: path} for every descriptor whose Executor card is not none."""
    return {folder: AGENTS / folder / values["Executor card"] for folder, values in descriptors().items()
            if values.get("Executor card", "none") != "none"}


def agent_tokens():
    """Return the words and phrases that name an agent, lowercased: per descriptor, its folder and naming fields."""
    tokens = set()
    for folder, values in descriptors().items():
        tokens.add(folder)
        tokens.update(values[field] for field in AGENT_TOKEN_FIELDS if field in values)
        tokens.update(FIRST_TOKEN.match(values[field]).group(0) for field in ["Name", "Reviewer name"]
                      if FIRST_TOKEN.match(values.get(field, "")))
    return sorted({token.lower() for token in tokens})


def in_checkout(path):
    """Whether a manifest's declared path is a non-empty relative path to a directory inside the checkout."""
    if not (isinstance(path, str) and path and not Path(path).is_absolute()):
        return False
    resolved = (ROOT / path).resolve()
    return resolved.is_dir() and (resolved == ROOT or ROOT in resolved.parents)


def front_matter_name(path):
    match = re.search(r"\A---\n(?:.*\n)*?name: (\S+)\n", path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


class RepoTest(unittest.TestCase):
    def test_manifests_required_and_discovered(self):
        problems = []
        discovered = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.glob(".*-plugin/plugin.json"))
        for rel in MANIFESTS + [rel for rel in discovered if rel not in MANIFESTS]:
            try:
                data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                problems.append("%s: invalid JSON (%s)" % (rel, error))
                continue
            name = data.get("name") if isinstance(data, dict) else None
            if name != "dopil":
                problems.append("%s: name is %r, expected 'dopil'" % (rel, name))
            if has_version(data):
                problems.append('%s: has a "version" key' % rel)
            declared = [data["skills"]] if isinstance(data, dict) and "skills" in data else []
            if rel in MARKETPLACES:
                plugins = data.get("plugins") if isinstance(data, dict) else None
                if not (isinstance(plugins, list) and len(plugins) == 1 and isinstance(plugins[0], dict)
                        and plugins[0].get("name") == "dopil"):
                    problems.append("%s: plugins must be exactly one entry named 'dopil'" % rel)
                else:
                    source = plugins[0].get("source")
                    declared.append(source.get("path") if isinstance(source, dict) else source)
            problems.extend("%s: declared path %r is not a relative directory inside the checkout" % (rel, path)
                            for path in declared if not in_checkout(path))
        self.assertEqual(problems, [])

    def test_references_resolve(self):
        refs, found, problems, texts = ROOT / REFERENCES, descriptors(), [], {}
        scanned = scanned_files()
        for path in scanned:
            rel = path.relative_to(ROOT).as_posix()
            try:
                texts[path] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as error:
                problems.append("%s: not valid UTF-8 at byte %d" % (rel, error.start))
                continue
            folder = agent_folder(path)
            for number, line in enumerate(texts[path].splitlines(), 1):
                for name in REFERENCE.findall(line):
                    pattern = re.sub(PLACEHOLDER, "*", name)
                    exists = any(refs.glob(pattern)) if "*" in pattern else (refs / name).exists()
                    if not exists and name not in EXTERNAL_REFERENCES:
                        problems.append("%s:%d: references/%s does not exist" % (rel, number, name))
                if folder is not None and path == folder / "agent.md":
                    continue  # its cells are validated by the descriptor tests
                for name in BARE.findall(line):
                    if name in RUNTIME_ARTIFACTS:
                        continue
                    if folder is None:
                        if not (refs / name).is_file() and name != "agent.md":
                            problems.append("%s:%d: `%s` is neither a reference file, the descriptor nor a run-time"
                                            " artifact" % (rel, number, name))
                    elif (refs / name).is_file():
                        problems.append("%s:%d: `%s` names a core file bare; write references/%s"
                                        % (rel, number, name, name))
                    elif not (folder / name).is_file():
                        problems.append("%s:%d: `%s` is neither in %s nor a run-time artifact"
                                        % (rel, number, name, folder.name))
        for profile, required in sorted(PROFILES.items()):
            directory, folder = AGENTS / profile, AGENTS / profile.split("/")[0]
            inside = sorted(path.relative_to(directory).as_posix() for path in scanned if directory in path.parents)
            for name in required:
                if name not in inside:
                    problems.append("%s/%s: required profile file missing" % (profile, name))
            for name in inside:
                if name not in required:
                    problems.append("%s/%s: not a profile file" % (profile, name))
            for card in named_cards(found.get(folder.name, {})):
                text = texts.get(folder / card, "")
                if directory.name in text:
                    problems.extend("%s/%s: names %s but not %s" % (folder.name, card, directory.name, name)
                                    for name in inside if name not in text)
        for path in scanned:
            folder = agent_folder(path)
            if folder is None:
                continue
            name, cards = path.relative_to(folder).as_posix(), named_cards(found.get(folder.name, {}))
            if name == "agent.md" or name in cards:
                continue
            head, _, rest = name.partition("/")
            if not any(name in text or rest and head in text and rest in text
                       for text in (texts.get(folder / card, "") for card in cards)):
                problems.append("%s: named by neither its descriptor nor one of its cards"
                                % path.relative_to(ROOT).as_posix())
        for path in scanned:
            if path.parent != refs:
                continue
            reference, bare = "references/" + path.name, "`%s`" % path.name
            if not any(reference in text or agent_folder(other) is None and bare in text
                       for other, text in texts.items() if other != path):
                problems.append("%s: named by no other scanned file" % path.relative_to(ROOT).as_posix())
        self.assertEqual(problems, [])

    def test_reviewer_cards_have_parts(self):
        problems = []
        for folder, values in descriptors().items():
            card = values.get("Reviewer card", "none")
            if card == "none":
                continue
            path = AGENTS / folder / card
            if not path.is_file():
                problems.append("%s/%s does not exist" % (folder, card))
                continue
            parts = card_parts(path)
            if [heading for heading, _ in parts] != REVIEWER_PARTS:
                problems.append("%s/%s: parts are %r" % (folder, card, [heading for heading, _ in parts]))
            problems.extend("%s/%s: %s is empty; write None." % (folder, card, heading)
                            for heading, body in parts if not body)
        self.assertEqual(problems, [])

    def test_executor_cards_have_parts(self):
        rows = set(re.findall(r"^\*\*(.+?)\.\*\*", (ROOT / REFERENCES / "executor.md").read_text(encoding="utf-8"),
                              re.MULTILINE))
        problems = []
        for folder, path in sorted(executor_cards().items()):
            if not path.is_file():
                problems.append("%s/%s does not exist" % (folder, path.name))
                continue
            parts = card_parts(path)
            if [heading for heading, _ in parts] != EXECUTOR_PARTS:
                problems.append("%s/%s: parts are %r" % (folder, path.name, [heading for heading, _ in parts]))
            for heading, body in parts:
                if not body:
                    problems.append("%s/%s: %s is empty; write None. or a deferral" % (folder, path.name, heading))
                elif body.replace("`", "").startswith("As references/executor.md"):
                    row = deferral(body)
                    if row not in rows:
                        problems.append("%s/%s: %s defers to %r, not a row of references/executor.md"
                                        % (folder, path.name, heading, row))
            bodies = dict(parts)
            for heading in ["Stop", "Recovery"]:
                body = bodies.get(heading, "")
                if body in ("", "None.") or deferral(body) is not None:
                    problems.append("%s/%s: %s is %r" % (folder, path.name, heading, body))
        self.assertEqual(problems, [])

    def test_identity_cards_run_the_scripts(self):
        problems = []
        for folder in IDENTITY_SCRIPTS:
            path = executor_cards().get(folder)
            if path is None or not path.is_file():
                problems.append("%s: no executor card" % folder)
                continue
            parts = dict(card_parts(path))
            launch = 'python3 -I "<skill-dir>/references/agents/%s/identity.py"' % folder
            if launch not in " ".join(parts.get("Identity", "").split()):
                problems.append("%s: Identity lacks %r" % (folder, launch))
            if folder == "kimi" and KIMI_SUBAGENT_CHECK not in " ".join(parts.get("Models", "").split()):
                problems.append("%s: Models lacks %r" % (folder, KIMI_SUBAGENT_CHECK))
            if INLINE_IDENTITY in path.read_text(encoding="utf-8"):
                problems.append("%s: the card holds an inline identity block" % folder)
        self.assertEqual(problems, [])

    def test_core_names_no_agent(self):
        # A phrase matches across any whitespace, line breaks included, so a wrapped name is still found.
        words = [(token, re.compile(r"(?<!\w)%s(?!\w)" % r"\s+".join(re.escape(part) for part in token.split()),
                                    re.IGNORECASE))
                 for token in agent_tokens()]
        problems = []
        for path in scanned_files():
            if path.parent != ROOT / REFERENCES and path != ROOT / SKILLS[0]:
                continue
            rel = path.relative_to(ROOT).as_posix()
            masked = INSTRUCTION_FILES.sub(" ", path.read_text(encoding="utf-8"))
            for token, word in words:
                problems.extend("%s:%d: %s" % (rel, masked.count("\n", 0, match.start()) + 1, token)
                                for match in word.finditer(masked))
        self.maxDiff = None
        self.assertEqual(problems, [])

    def test_executor_never_prints_environment(self):
        # executor.md keeps its bans on printing the environment, whole or filtered through grep.
        text = (ROOT / REFERENCES / "executor.md").read_text(encoding="utf-8")
        for token in ["`printenv`", "`env | grep`"]:
            self.assertIn(token, text)

    def test_known_items_slot_in_every_discovery_framework(self):
        text = (ROOT / REFERENCES / "prompts.md").read_text(encoding="utf-8")
        slot = '<only if present: block "Known task-review items">'
        for name in ["file mode", "diff mode", "polish delta", "snapshot delta"]:
            prompt = text.split("\n## Discovery framework: %s\n" % name, 1)[1].split("```", 2)[1]
            self.assertEqual(prompt.count(slot), 1, name)

    def test_no_cross_folder_paths(self):
        folders = sorted(path.name for path in AGENTS.iterdir() if path.is_dir())
        problems = []
        for path in scanned_files():
            folder = agent_folder(path)
            if folder is None:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for other in folders:
                for token in ["references/agents/%s/" % other, "../%s/" % other]:
                    if other != folder.name and token in text:
                        problems.append("%s: contains %s" % (path.relative_to(ROOT).as_posix(), token))
        self.assertEqual(problems, [])

    def test_skills_and_live_kit_have_no_model_ids_or_author_paths(self):
        problems, scanned = [], set()
        for top in DENYLIST_SCOPE:
            for path in sorted((ROOT / top).rglob("*")):
                # __pycache__ is git-ignored and its .pyc files embed the local absolute path.
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                scanned.add(top)
                rel = path.relative_to(ROOT).as_posix()
                text = path.read_text(encoding="utf-8", errors="replace")
                for number, line in enumerate(text.splitlines(), 1):
                    for match in DENYLIST.finditer(line):
                        problems.append("%s:%d: %s" % (rel, number, match.group(0)))
        self.assertEqual(sorted(scanned), sorted(DENYLIST_SCOPE), "a scanned directory has no files")
        self.assertEqual(problems, [])

    def test_descriptors_have_fields_by_role(self):
        folders = [path for path in sorted(AGENTS.glob("*")) if path.is_dir()]
        self.assertTrue(folders, "no agent folder under %s" % AGENTS.relative_to(ROOT).as_posix())
        problems = ["%s: no agent.md" % path.name for path in folders if not (path / "agent.md").is_file()]
        for path in sorted(AGENTS.glob("*/agent.md")):
            folder, rows = path.parent.name, descriptor_rows(path)
            fields = [field for field, _ in rows]
            for field in sorted(set(fields)):
                if fields.count(field) > 1:
                    problems.append("%s: field %r appears %d times" % (folder, field, fields.count(field)))
            values = dict(rows)
            executor, reviewer = values.get("Executor card"), values.get("Reviewer card")
            if executor not in ("executor.md", "none"):
                problems.append("%s: Executor card is %r, expected 'executor.md' or 'none'"
                                % (folder, executor))
            if reviewer not in ("reviewer.md", "none"):
                problems.append("%s: Reviewer card is %r, expected 'reviewer.md' or 'none'"
                                % (folder, reviewer))
            if executor == reviewer == "none":
                problems.append("%s: both cards are none" % folder)
            expected = (ALWAYS + (EXECUTOR if executor not in (None, "none") else [])
                        + (REVIEWER if reviewer not in (None, "none") else []))
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.startswith("|") and not ROW.match(line):
                    problems.append("%s:%d: not a two-cell row" % (folder, number))
            for field in expected:
                if not values.get(field):
                    problems.append("%s: missing field %r" % (folder, field))
            for field in fields:
                if field not in expected:
                    problems.append("%s: field %r is outside its role" % (folder, field))
            for field, pattern in FORMATS.items():
                if field in values and not pattern.fullmatch(values[field]):
                    problems.append("%s: %s %r does not match %s"
                                    % (folder, field, values[field], pattern.pattern))
        self.assertEqual(problems, [])

    def test_descriptors_are_unique(self):
        found, problems = descriptors(), []
        for field in ["Name", "Scratch key", "Finding prefix", "Order"]:
            owners = {}
            for folder, values in found.items():
                if field in values:
                    owners.setdefault(values[field], []).append(folder)
            for value, folders in sorted(owners.items()):
                if len(folders) > 1:
                    problems.append("%s %r is shared by %s" % (field, value, ", ".join(folders)))
        self.assertEqual(problems, [])

    def test_default_reviewer_names_another_folder(self):
        # The default reviewer is another folder's reviewer, of another vendor than the executor's own.
        found, problems = descriptors(), []
        for folder, values in found.items():
            default = values.get("Default reviewer", "none")
            reviewers = {other.get("Scratch key"): other for name, other in found.items()
                         if name != folder and other.get("Reviewer card") == "reviewer.md"}
            if default == "none":
                continue
            if default not in reviewers:
                problems.append("%s: Default reviewer %r is no other folder's reviewer Scratch key"
                                % (folder, default))
            elif reviewers[default].get("Reviewer vendor") == values.get("Reviewer vendor"):
                problems.append("%s: Default reviewer %r has the executor's own vendor" % (folder, default))
        self.assertEqual(problems, [])

    def test_descriptor_values_of_the_four(self):
        # Released Scratch keys and Finding prefixes never change: saved routes name them.
        expected = {"claude-code": ("claude", "A"), "codex": ("codex", "C"), "kimi": ("kimi", "K"),
                    "antigravity": ("gemini", "G")}
        found = descriptors()
        released = {folder: tuple(found.get(folder, {}).get(field) for field in ["Scratch key", "Finding prefix"])
                    for folder in expected}
        self.assertEqual(released, expected)

    def test_antigravity_reviewer_names_agree(self):
        # The Antigravity card runs its one profile by its declared name; its rm -rf guards take its mktemp's shape.
        profiles = AGENTS / "antigravity" / "agy-reviewer" / ".agents" / "agents"
        files = sorted(path.name for path in profiles.iterdir())
        self.assertEqual(len(files), 1, files)
        card = (AGENTS / "antigravity" / "reviewer.md").read_text(encoding="utf-8")
        launched = re.findall(r"agy_iso --agent (\S+)", card)
        self.assertTrue(launched, "the card launches the profile")
        checked = re.findall(r'init\.get\("agent"\) == "([^"]+)"', card)
        self.assertTrue(checked, "the card checks the profile it ran")
        self.assertEqual(set(launched) | set(checked), {front_matter_name(profiles / files[0])})
        hashed = re.findall(r"\.agents/agents/(\S+\.md)", card)
        self.assertTrue(hashed, "the card pins the profile file")
        self.assertEqual(set(hashed), set(files))
        created = re.findall(r'mktemp -d "\$\{TMPDIR:-/tmp\}/([\w-]+)\.(X+)"', card)
        accepted = re.findall(r"\*/([\w-]+)\.(\?+)\)", card)
        self.assertEqual(len(created), 1, created)
        self.assertEqual(len(accepted), 2, "the blocker removal and the gate end accept the shape")
        self.assertEqual({(name, len(mark)) for name, mark in accepted}, {(created[0][0], len(created[0][1]))})


if __name__ == "__main__":
    unittest.main()
