"""Check the repository tree: manifests, skill sizes, references, denylist."""

import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
             ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json",
             ".kimi-plugin/plugin.json", ".antigravity-plugin/plugin.json"]
MARKETPLACES = [".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"]
SKILLS = ["skills/ship/SKILL.md", "skills/pragmatic-engineering/SKILL.md"]
REFERENCES = "skills/ship/references"
AGENTS = ROOT / REFERENCES / "agents"
REVIEWER_PARTS = ["Contract card", "Requirements", "Preparation and pin", "Calls", "Acceptance", "Prompts",
                  "Orca", "Gate end", "Access", "Pitfalls"]
EXECUTOR_PARTS = ["Identity", "Tools", "Models", "Route skills", "Instructions", "Runs that cannot take an answer",
                  "Orca writing workers", "Follow-ups", "Stop", "Recovery", "Closing", "Pitfalls"]
# A part the generic row covers: one line naming that row of references/executor.md.
DEFERRAL = re.compile(r"As references/executor\.md, (.+)\.")
ROUTE_SKILLS = ["brainstorming", "writing-plans", "test-driven-development", "using-git-worktrees",
                "subagent-driven-development", "receiving-code-review", "verification-before-completion",
                "finishing-a-development-branch"]
# The spec's override map for Claude Code and Codex: per overriding part, text the card's part must hold.
OVERRIDES = {
    "claude-code": {"Identity": ["CLAUDECODE", "CODEX_THREAD_ID"],
                    "Tools": ["run_in_background", "Agent", "Workflow", "simplify", "ponytail:ponytail-review",
                              "AskUserQuestion"],
                    "Models": ["sonnet", "opus", "fable"],
                    "Route skills": ROUTE_SKILLS + ["/plugin install superpowers@claude-plugins-official"],
                    "Instructions": []},
    "codex": {"Identity": ["CODEX_THREAD_ID", "system context"],
              "Tools": ["exec_command", "write_stdin", "functions.wait", "spawn_agent", "request_user_input",
                        "reviewer-choice.md", "plain text", "External CLI access", "**Access**"],
              "Models": ["user's instructions"],
              "Route skills": ROUTE_SKILLS + ["How to read dependencies"],
              "Instructions": ["AGENTS.md"]},
}
IDENTITY_SCRIPTS = ["kimi", "antigravity"]
KIMI_SUBAGENT_CHECK = 'python3 -I "<skill-dir>/references/agents/kimi/identity.py" <agent_id>'
INLINE_IDENTITY = "python3 -I - <<'PY'"
LAUNCH_FAILURE = ("A launch that prints none of these lines, a missing script, a missing interpreter or a crash:"
                  " blocked; name it and stop before any dispatch; never run an improvised check instead.")
# Profile directories a card copies whole, under AGENTS: their required files, and nothing else.
PROFILES = {"antigravity/agy-reviewer": ["settings.json", ".agents/agents/ship-reviewer.md"]}
# Descriptor fields by role (spec, "Agent folder"); a field outside its role is absent.
ALWAYS = ["Name", "Executor card", "Reviewer card"]
EXECUTOR = ["Invocation", "Default reviewer"]
REVIEWER = ["Binary", "Reviewer name", "Reviewer vendor", "Scratch key", "Finding prefix", "Order"]
FORMATS = {"Scratch key": re.compile(r"[a-z0-9-]+"),
           "Finding prefix": re.compile(r"[A-Z]"),
           "Order": re.compile(r"[1-9][0-9]*")}
ROW = re.compile(r"^\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$")
SEPARATOR = re.compile(r"[-:]+")
# The four folders the spec describes; the naming-hint test builds its roster from them alone, so a new folder
# does not change its expected keys.
ORIGINAL_FOLDERS = ["claude-code", "codex", "kimi", "antigravity"]
# Descriptor fields whose values name an agent; the core names none of them (spec, "Tests").
AGENT_TOKEN_FIELDS = ["Name", "Reviewer name", "Binary", "Reviewer vendor", "Scratch key"]
FIRST_TOKEN = re.compile(r"[A-Za-z0-9-]+")
# The naming hint's keys (reviewer-choice.md, "Dialog form"); for both executors with a default the baseline
# printed `with kimi and gemini`, and the Kimi Code executor `with codex and gemini`, named by its card.
NAMING_HINT = ("the keys of the last two cross-vendor roster entries in roster order (default first, then Order),"
               " or the one key when only one exists")
CARD_HINT = ("the keys the executor card names for this example, when each is the key of a cross-vendor entry of the"
             " current roster")
# Instruction file names the core may mention although they contain an agent's name.
INSTRUCTION_FILES = re.compile(r"CLAUDE\.md|AGENTS\.md|GEMINI\.md")
LINE_LIMIT = 500
BYTE_LIMIT = 20000

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
}

# A path under references/: a file, a directory or a glob over them, without trailing punctuation. A `<placeholder>`
# in a segment stands for any name: the path is checked as a glob with `*` in its place.
PLACEHOLDER = r"<[^/<>\s]+>"
REFERENCE = re.compile(r"references/((?:(?:[\w.*-]|{0})+/)*(?:(?:[\w.*-]|{0})*(?:[\w*-]|{0}))?)".format(PLACEHOLDER))
BARE = re.compile(r"`([a-z0-9-]+\.md)`")
DENYLIST = re.compile(r"~/\.agents/skills/ship|be1ski"
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
    """Return SKILL.md and every tracked or untracked, non-ignored file under references/."""
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", REFERENCES],
                            cwd=str(ROOT), check=True, stdout=subprocess.PIPE).stdout.decode("utf-8")
    files = sorted({ROOT / rel for rel in listed.split("\0") if rel})
    return [ROOT / SKILLS[0]] + [path for path in files if path.is_file()]


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


def naming_hint_keys(card):
    """Return the keys a card's **Tools** names for the naming hint's example, or None when it names none."""
    tools = " ".join(dict(card_parts(card)).get("Tools", "").split())
    sentences = [s for s in re.split(r"(?<=\.)\s+", tools) if "naming hint" in s]
    return re.findall(r"`([a-z0-9-]+)`", sentences[0]) if sentences else None


def hint_keys(found, executor):
    """Return the naming hint's keys for an executor folder over the descriptors `found` (reviewer-choice.md,
    "Dialog form"). The executor runs its own vendor's model, so its Reviewer vendor is the executor's vendor."""
    own = found[executor]
    roster = sorted((values for values in found.values() if values.get("Reviewer card") == "reviewer.md"),
                    key=lambda values: (values["Scratch key"] != own["Default reviewer"], int(values["Order"])))
    cross = [values["Scratch key"] for values in roster if values["Reviewer vendor"] != own["Reviewer vendor"]]
    named = naming_hint_keys(AGENTS / executor / own["Executor card"])
    return named if named and set(named) <= set(cross) else cross[-2:]


def agent_tokens():
    """Return the words and phrases that name an agent, lowercased: per descriptor, its folder and naming fields."""
    tokens = set()
    for folder, values in descriptors().items():
        tokens.add(folder)
        tokens.update(values[field] for field in AGENT_TOKEN_FIELDS if field in values)
        tokens.update(FIRST_TOKEN.match(values[field]).group(0) for field in ["Name", "Reviewer name"]
                      if FIRST_TOKEN.match(values.get(field, "")))
    return sorted({token.lower() for token in tokens})


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
            if name != "ship":
                problems.append("%s: name is %r, expected 'ship'" % (rel, name))
            if has_version(data):
                problems.append('%s: has a "version" key' % rel)
            if rel in MARKETPLACES:
                plugins = data.get("plugins") if isinstance(data, dict) else None
                if not (isinstance(plugins, list) and len(plugins) == 1 and isinstance(plugins[0], dict)
                        and plugins[0].get("name") == "ship"):
                    problems.append("%s: plugins must be exactly one entry named 'ship'" % rel)
        self.assertEqual(problems, [])

    def test_skill_cores_fit_the_size_limit(self):
        problems = []
        for rel in SKILLS:
            data = (ROOT / rel).read_bytes()
            lines = len(data.splitlines())
            if lines >= LINE_LIMIT:
                problems.append("%s: %d lines, limit is under %d" % (rel, lines, LINE_LIMIT))
            if len(data) >= BYTE_LIMIT:
                problems.append("%s: %d bytes, limit is under %d" % (rel, len(data), BYTE_LIMIT))
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
        self.assertEqual(problems, [])

    def test_claude_and_codex_override_map(self):
        problems = []
        for folder, markers in sorted(OVERRIDES.items()):
            path = executor_cards().get(folder)
            if path is None or not path.is_file():
                problems.append("%s: no executor card" % folder)
                continue
            parts = dict(card_parts(path))
            for heading, needed in sorted(markers.items()):
                body = parts.get(heading, "")
                if not body or deferral(body) is not None or body == "None.":
                    problems.append("%s: %s does not override" % (folder, heading))
                problems.extend("%s: %s lacks %r" % (folder, heading, marker) for marker in needed
                                if marker not in " ".join(body.split()))
            if "executing-plans" in parts.get("Route skills", ""):
                problems.append("%s: Route skills names executing-plans" % folder)
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
            for needed in [launch, LAUNCH_FAILURE]:
                if needed not in " ".join(parts.get("Identity", "").split()):
                    problems.append("%s: Identity lacks %r" % (folder, needed))
            if folder == "kimi" and KIMI_SUBAGENT_CHECK not in " ".join(parts.get("Models", "").split()):
                problems.append("%s: Models lacks %r" % (folder, KIMI_SUBAGENT_CHECK))
            if INLINE_IDENTITY in path.read_text(encoding="utf-8"):
                problems.append("%s: the card holds an inline identity block" % folder)
        self.assertEqual(problems, [])

    def test_executor_cards_have_stop_and_recovery(self):
        problems = []
        for folder, path in sorted(executor_cards().items()):
            parts = dict(card_parts(path)) if path.is_file() else {}
            for heading in ["Stop", "Recovery"]:
                body = parts.get(heading, "")
                if body in ("", "None.") or deferral(body) is not None:
                    problems.append("%s/%s: %s is %r" % (folder, path.name, heading, body))
        self.assertEqual(problems, [])

    def test_claude_print_mode_is_recognizable(self):
        card = AGENTS / "claude-code" / "executor.md"
        body = dict(card_parts(card)).get("Runs that cannot take an answer", "")
        self.assertIn("AskUserQuestion", body)
        self.assertIn("non-interactive", body)

    def test_default_waits_for_the_run_check(self):
        text = (ROOT / REFERENCES / "reviewer-choice.md").read_text(encoding="utf-8")
        section = next(part for part in text.split("\n## ") if "Without a default" in part)
        sentences = re.split(r"(?<=[.:])\s+", " ".join(section.split()))
        self.assertTrue([s for s in sentences if "before" in s.lower() and "Runs that cannot take an answer" in s])

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
        text = (ROOT / REFERENCES / "executor.md").read_text(encoding="utf-8")
        paragraphs = [" ".join(p.split()) for p in text.split("\n\n")]
        self.assertTrue([p for p in paragraphs if all(w in p for w in ("`env`", "`printenv`", "`grep`"))
                         and ("named variable" in p or "single variable" in p)])

    def test_key_leads_to_folder_by_descriptor(self):
        text = " ".join((ROOT / REFERENCES / "reviewer-choice.md").read_text(encoding="utf-8").split())
        sentences = re.split(r"(?<=[.:])\s+", text)
        self.assertTrue([s for s in sentences if "Scratch key" in s and "folder" in s and " not " in s])

    def test_naming_hint_keys_are_pinned(self):
        text = " ".join((ROOT / REFERENCES / "reviewer-choice.md").read_text(encoding="utf-8").split())
        self.assertIn(NAMING_HINT, text)
        self.assertIn(CARD_HINT, text)
        found = {folder: values for folder, values in descriptors().items() if folder in ORIGINAL_FOLDERS}
        for executor in ["claude-code", "codex"]:
            self.assertIsNone(naming_hint_keys(AGENTS / executor / found[executor]["Executor card"]), executor)
            self.assertEqual(hint_keys(found, executor), ["kimi", "gemini"], executor)

    def test_reviewers_line_is_written_bare_and_read_as_list_or_bold(self):
        text = (ROOT / REFERENCES / "reviewer-choice.md").read_text(encoding="utf-8")
        recording = " ".join(text.split("\n## Recording\n", 1)[1].split("\n## ", 1)[0].split())
        self.assertIn("written bare, at the start of the line, with no list marker or emphasis", recording)
        self.assertIn("on read, a `- ` list item or a bold form of the same line counts as the line", recording)

    def test_kimi_naming_hint_example(self):
        found = descriptors()
        kimi = found["kimi"]
        # The card's keys, each a cross-vendor entry of the roster the descriptors build, so they are the hint's.
        self.assertEqual(naming_hint_keys(AGENTS / "kimi" / kimi["Executor card"]), ["codex", "gemini"])
        self.assertEqual("%s with %s" % (kimi["Invocation"], " and ".join(hint_keys(found, "kimi"))),
                         "/skill:ship:ship <task> with codex and gemini")
        # A build without the codex folder: the card's keys are not all in the roster, so the generic pick applies.
        without_codex = {folder: values for folder, values in found.items()
                         if folder in ORIGINAL_FOLDERS and folder != "codex"}
        self.assertEqual(hint_keys(without_codex, "kimi"), ["claude", "gemini"])

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

    def test_every_agent_folder_has_a_descriptor(self):
        folders = [path for path in sorted(AGENTS.glob("*")) if path.is_dir()]
        self.assertTrue(folders, "no agent folder under %s" % AGENTS.relative_to(ROOT).as_posix())
        self.assertEqual([path.name for path in folders if not (path / "agent.md").is_file()], [])

    def test_descriptors_have_fields_by_role(self):
        problems = []
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
        found, problems = descriptors(), []
        for folder, values in found.items():
            default = values.get("Default reviewer", "none")
            keys = [other.get("Scratch key") for name, other in found.items()
                    if name != folder and other.get("Reviewer card") == "reviewer.md"]
            if default != "none" and default not in keys:
                problems.append("%s: Default reviewer %r is no other folder's reviewer Scratch key"
                                % (folder, default))
        self.assertEqual(problems, [])

    def test_descriptor_values_of_the_four(self):
        # The spec's table, section "Agent folder"; folders beyond these four are not checked here.
        expected = {
            "claude-code": {"Name": "Claude Code",
                            "Executor card": "executor.md", "Reviewer card": "reviewer.md",
                            "Invocation": "/ship <task>", "Default reviewer": "codex", "Binary": "claude",
                            "Reviewer name": "Claude Code", "Reviewer vendor": "Anthropic",
                            "Scratch key": "claude", "Finding prefix": "A", "Order": "2"},
            "codex": {"Name": "Codex", "Executor card": "executor.md", "Reviewer card": "reviewer.md",
                      "Invocation": "$ship <task>", "Default reviewer": "claude", "Binary": "codex",
                      "Reviewer name": "Codex", "Reviewer vendor": "OpenAI",
                      "Scratch key": "codex", "Finding prefix": "C", "Order": "1"},
            "kimi": {"Name": "Kimi Code", "Executor card": "executor.md", "Reviewer card": "reviewer.md",
                     "Invocation": "/skill:ship:ship <task>", "Default reviewer": "none", "Binary": "kimi",
                     "Reviewer name": "Kimi Code", "Reviewer vendor": "Moonshot AI",
                     "Scratch key": "kimi", "Finding prefix": "K", "Order": "3"},
            "antigravity": {"Name": "Antigravity CLI",
                            "Executor card": "executor.md", "Reviewer card": "reviewer.md",
                            "Invocation": "/ship:ship <task>", "Default reviewer": "none", "Binary": "agy",
                            "Reviewer name": "Gemini, through the Antigravity CLI",
                            "Reviewer vendor": "Google",
                            "Scratch key": "gemini", "Finding prefix": "G", "Order": "4"},
        }
        found = descriptors()
        self.maxDiff = None
        self.assertEqual({folder: found.get(folder) for folder in expected}, expected)

    def test_named_cards_exist(self):
        problems = []
        for folder, values in descriptors().items():
            for field in ["Executor card", "Reviewer card"]:
                card = values.get(field, "none")
                if card != "none" and not (AGENTS / folder / card).is_file():
                    problems.append("%s: %s %s does not exist" % (folder, field, card))
        self.assertEqual(problems, [])
