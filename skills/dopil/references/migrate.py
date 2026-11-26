"""Move a route scratch of the previous plugin into dopil's.

The only moves are `<dir>/.ship/<entry>` to `<dir>/.dopil/<entry>` and `<git-common-dir>/ship-routes/<id>.txt` to
`<git-common-dir>/dopil-routes/<id>.txt` with the root prefix rewritten. Run as
`python3 -I <skill dir>/references/migrate.py check|run` from the project's directory; the rule that runs it is
references/ledger.md, "Migration of an old scratch". On resume, `restart <gates.md> <old gate> <inputs.json>` turns a
gate the migration line names into its next attempt and prints `RESTART <old> -> <new>` or `NOTHING <old>: <reason>`
(exit 0), `REFUSE <path>: <reason>` (2, nothing written) or `PARTIAL <error>` (3, the next call finishes it).

Lines: `MOVE <src> -> <dst>`, `LEAVE <path>: <reason>`, `RESTART-LATER <gates.md>: <gates>`,
`REFUSE <path>: <reason>`, `PARTIAL <step>, step <n> of 5: <error>; moved: <the moves done>`. Exit 0: nothing to move
(only `LEAVE` lines possible) or `run` done; 1: `check` found moves; 2: refused, and nothing it changed is kept (an
error while planning included); 3: `run` failed after a write, and the next `run` finishes it; 64: a usage error, with
a `usage:` line on stderr.

Every step is idempotent, with no lock and no saved plan: a move whose source is gone and whose destination is in
place counts as done, so an interrupted run, or two runs at once, end in the same state.
"""

import errno
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple


OLD = ".ship"
NEW = ".dopil"
OLD_ROUTES = "ship-routes"
NEW_ROUTES = "dopil-routes"
RECORD = ".migrating"
UNKNOWN = "unknown"  # the marker's gate list for a registry whose form unclosed_gates does not know
STEPS = ["prepare .dopil", "mark the registries", "move the entries", "move the pointers", "remove the old scratch"]
USAGE = 64  # the usual status of a usage error, distinct from the four outcomes
IGNORE_ALL = (b"*\n", b"*")
GATE = re.compile(r"(spec|plan|code|polish|confirm)-\d\d")
MARKER = re.compile(r"^Migrated \d{4}-\d\d-\d\d: restart on resume: ", re.MULTILINE)
KEY = r"[a-z0-9][a-z0-9-]*"  # a reviewer's scratch key
SEPARATOR = " — "  # between the id, the location and the claim of a carried item
# Variables that point git at another repository or index than the one the working directory is in.
FOREIGN_GIT = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR"]


class Refused(Exception):
    """A refusal, naming the path: raised before anything moves, or by step 1 once it removed what it created."""

    def __init__(self, reason: str, path: Optional[Path] = None):
        super().__init__(reason)
        self.reason, self.path = reason, path


class GitFailed(Refused):
    """A git command exited with a status other than 0."""

    def __init__(self, reason: str, path: Path, status: int):
        super().__init__(reason, path)
        self.status = status


class Leftover(OSError):
    """A path found existing, as a caller may accept, but the temporary file of the write could not be removed: not
    the clean "exists already", and the message names both."""


class Partial(Exception):
    """`run` failed after a write; the message names the interrupted step and the moves done."""


class Nothing(Exception):
    """`restart` has nothing to do; the message says why."""


@dataclass
class Inputs:
    """The executor's inputs.json for a restart, checked."""
    raw: bytes  # the file's bytes, saved into the new scratch
    scratch: Optional[Path]  # the old attempt's scratch, under the moved root; None for a gate never prepared
    scope: str
    header: str  # the old ledger's opening lines, under the moved root
    carry: Dict[str, List[str]]  # each reviewer's carried lines, one per id
    snapshots: List[Tuple[Path, str]]  # each copy, under the moved root, and its original
    locked: List[str]


@dataclass
class Plan:
    scratches: List[Path] = field(default_factory=list)  # each recognized old scratch
    moves: List[Tuple[Path, Path]] = field(default_factory=list)  # entry, its place in .dopil
    pointers: List[Tuple[Path, Path, str]] = field(default_factory=list)  # old pointer, new pointer, new content
    markers: Dict[Path, List[str]] = field(default_factory=dict)  # a route's gates.md, its gates to restart
    leaves: List[Tuple[Path, str]] = field(default_factory=list)  # left in place, with the reason
    in_git: bool = False
    old_routes: Optional[Path] = None  # the old pointer directory, removed once empty
    aliases: Dict[Path, List[Path]] = field(default_factory=dict)  # a scratch, the other spellings pointers give it
    moved: List[Tuple[Path, Path]] = field(default_factory=list)  # the moves `run` did, in order


def git(args: List[str], cwd: Path) -> str:
    """Run git in cwd without the caller's redirections; a non-zero status is a refusal naming the command."""
    env = {name: value for name, value in os.environ.items() if name not in FOREIGN_GIT}
    env["LC_ALL"] = "C"  # inside_git matches git's English answer
    try:
        done = subprocess.run(["git"] + list(args), cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    except OSError as error:
        raise Refused("git could not run: %s" % error, cwd)
    if done.returncode != 0:
        raise GitFailed("git %s failed: %s" % (" ".join(args), os.fsdecode(done.stderr).strip()), cwd,
                        done.returncode)
    return os.fsdecode(done.stdout)


def ignored(path: Path) -> bool:
    """Whether git reports the path ignored: status 1 is "not ignored", any other failure a refusal with its error."""
    try:
        git(["check-ignore", "-q", "--", path.name], path.parent)
    except GitFailed as error:
        if error.status == 1:
            return False
        raise
    return True


def table(lines: List[str]) -> Tuple[Optional[List[str]], List[Tuple[int, List[str]]]]:
    """A registry's header cells (None without the Gate/State header) and its gate rows as (line index, cells)."""
    header = None
    rows = []
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        # An escaped `\|` belongs to its cell, as in a Markdown table.
        cells = [cell.strip().replace("\0", "\\|")
                 for cell in line.replace("\\|", "\0").strip().strip("|").split("|")]
        if header is None:
            if "Gate" in cells and "State" in cells:
                header = cells
        elif GATE.fullmatch(cells[0]):
            rows.append((index, cells))
    return header, rows


def cell(cells: List[str], index: int) -> str:
    return cells[index] if index < len(cells) else ""


def is_closed(state: str) -> bool:
    return state.startswith(("closed", "not run"))


def unclosed_gates(gates_text: str) -> List[str]:
    """The gates of a registry whose State is neither `closed` nor `not run`, in order."""
    header, rows = table(gates_text.splitlines())
    if header is None:
        raise Refused("registry form unknown")
    state = header.index("State")
    return [cells[0] for _, cells in rows if not is_closed(cell(cells, state))]


def under(path: Path, root: Path) -> bool:
    """Whether root is a component prefix of path."""
    return path.parts[:len(root.parts)] == root.parts


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", "surrogateescape")


def ignores_all(path: Path) -> bool:
    """Whether the file holds the single line `*`."""
    try:
        return path.read_bytes() in IGNORE_ALL
    except OSError:
        return False


def refuse_links(anchor: Path, paths: List[Path]) -> None:
    """Refuse a symlink on any of the paths or their parents below anchor (the top level, or the git dir)."""
    for path in paths:
        if not under(path, anchor):
            raise Refused("lies outside %s" % anchor, path)
        current = anchor
        for part in path.parts[len(anchor.parts):]:
            current = current / part
            if os.path.islink(str(current)):
                raise Refused("is a symlink", current)


def refuse_unwritable(paths: List[Path]) -> None:
    for path in paths:
        if not os.access(str(path), os.W_OK):
            raise Refused("is not writable", path)


def read_record(record: Path, old: Path) -> Tuple[int, int]:
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
        path, dev, ino = data["path"], data["dev"], data["ino"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise Refused("unreadable record: %s" % error, record)
    if path != str(old):
        raise Refused("records another directory, %s" % path, record)
    return dev, ino


def matches_record(old: Path, dev: int, ino: int) -> bool:
    """Whether old is the recorded directory and holds only a `*` .gitignore, or nothing."""
    st = os.lstat(str(old))
    if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != (dev, ino):
        return False
    names = os.listdir(str(old))
    return names == [] or (names == [".gitignore"] and ignores_all(old / ".gitignore"))


def inside_git(cwd: Path) -> bool:
    try:
        return git(["rev-parse", "--is-inside-work-tree"], cwd).strip() == "true"
    except Refused as error:
        if "not a git repository" in error.reason:
            return False
        raise


def survey(plan: Plan, where: Path, anchor: Path) -> None:
    """Plan the old scratch beside `where`, if there is one: every refusal first, then its moves and registries."""
    old, new = where / OLD, where / NEW
    record = new / RECORD
    if os.path.lexists(str(record)):
        refuse_links(anchor, [record, old])
        dev, ino = read_record(record, old)
        if not os.path.lexists(str(old)) or matches_record(old, dev, ino):
            plan.scratches.append(old)
        else:
            plan.leaves.append((old, "does not match the record %s, kept with it" % record))
        return
    if not os.path.isdir(str(old)):
        return
    names = sorted(os.listdir(str(old)))
    if not names:
        plan.leaves.append((old, "empty, with no record of a migration"))
        return
    routes = [name for name in names if os.path.isfile(str(old / name / "gates.md"))]
    if ".gitignore" not in names and "routes" not in names and not routes:
        return  # not a scratch of the previous plugin
    entries = [name for name in names if name != ".gitignore"]
    if "routes" in names:
        raise Refused("holds fallback pointers, not the plain case", old / "routes")
    if not ignores_all(old / ".gitignore"):
        raise Refused("is missing or not the single line *", old / ".gitignore")
    if plan.in_git and git(["ls-files", "--", OLD], where).strip():
        raise Refused("is tracked by git", old)
    refuse_links(anchor, [old / ".gitignore", new / ".gitignore", record] + [old / name for name in entries]
                 + [old / name / "gates.md" for name in routes] + [new / name for name in entries])
    if os.path.lexists(str(new)) and not os.path.isdir(str(new)):
        raise Refused("is not a directory", new)
    if os.path.lexists(str(new / ".gitignore")) and not ignores_all(new / ".gitignore"):
        raise Refused("is not the single line *", new / ".gitignore")
    for name in entries:
        if os.path.lexists(str(new / name)):
            raise Refused("exists already", new / name)
    # A directory's rename rewrites its `..`, so a moved directory must be writable too.
    refuse_unwritable([old, new if os.path.lexists(str(new)) else where]
                      + [old / name for name in entries if os.path.isdir(str(old / name))]
                      + [old / name / "gates.md" for name in routes])
    for name in routes:
        gates = old / name / "gates.md"
        try:
            plan.markers[gates] = unclosed_gates(read_text(gates))
        except Refused:
            # A registry without the Gate/State header moves too; on resume the executor reads it itself.
            plan.markers[gates] = [UNKNOWN]
    plan.moves.extend((old / name, new / name) for name in entries)
    plan.scratches.append(old)


def survey_pointers(plan: Plan, common: Path, cwd: Path) -> None:
    """Plan the pointers into the planned scratches; every other pointer is left and named."""
    directory = common / OLD_ROUTES
    if not os.path.isdir(str(directory)):
        return
    roots = [Path(line[len("worktree "):]) for line in git(["worktree", "list", "--porcelain"], cwd).splitlines()
             if line.startswith("worktree ")]
    names = sorted(os.listdir(str(directory)))  # read once: another run may remove the directory meanwhile
    for name in names:
        old = directory / name
        if not name.endswith(".txt") or not os.path.isfile(str(old)):
            continue
        raw = os.fsdecode(old.read_bytes())
        pointed = raw.strip()
        # Ownership by real paths: a pointer written through a symlinked parent still names this scratch.
        target = Path(os.path.realpath(pointed) if os.path.isabs(pointed) else pointed)
        owners = [scratch for scratch in plan.scratches if under(target, Path(os.path.realpath(str(scratch))))]
        if not owners:
            inside = sorted((root for root in roots if under(target, root)), key=lambda root: len(root.parts))
            reason = "points outside every worktree"
            if inside:
                reason = "points into the worktree %s; it moves when dopil starts beside its scratch" % inside[-1]
            plan.leaves.append((old, reason))
            continue
        real = Path(os.path.realpath(str(owners[0])))
        below = len(target.parts) - len(real.parts)
        literal = Path(pointed)
        prefix = Path(*literal.parts[:len(literal.parts) - below]) if below < len(literal.parts) else literal
        if prefix.name == OLD and prefix != owners[0] and os.path.realpath(str(prefix)) == str(real):
            # The pointer reaches the scratch through an alias; the registries may spell it the same way.
            known = plan.aliases.setdefault(owners[0], [])
            if prefix not in known:
                known.append(prefix)
        moved = Path(owners[0].parent / NEW, *target.parts[len(real.parts):])
        content = raw.replace(pointed, str(moved), 1)
        new = common / NEW_ROUTES / name
        refuse_links(common, [old, new])
        if os.path.lexists(str(new)) and os.fsdecode(new.read_bytes()) != content:
            raise Refused("exists with other content", new)
        plan.pointers.append((old, new, content))
    already_empty = not names and not os.path.islink(str(directory))
    if plan.pointers or (plan.scratches and already_empty):
        # This plan's own pointers leave it, or an interrupted run emptied it: the run removes it at the end of step
        # 4 once it is empty, so whichever run moves the last pointer, from any worktree, removes it. One condition
        # plans the removal and checks that it can write the git dir; a plan without it does nothing here, so other
        # worktrees' pointers alone never block a local scratch.
        plan.old_routes = directory
        refuse_unwritable([common])
    if plan.pointers:
        # Only a plan that writes pointers needs dopil-routes, and the old pointers' directory, to take them.
        new_routes = common / NEW_ROUTES
        if os.path.lexists(str(new_routes)) and not os.path.isdir(str(new_routes)):
            raise Refused("is not a directory", new_routes)
        refuse_unwritable([path for path in [directory, new_routes] if os.path.lexists(str(path))])


def make_plan(cwd: Path) -> Plan:
    """What `run` would do from cwd; raises Refused on any refusal, before anything moves."""
    cwd = Path(os.path.abspath(str(cwd)))
    plan = Plan()
    try:
        plan.in_git = inside_git(cwd)
        if not plan.in_git:
            survey(plan, cwd, cwd)
            return plan
        top = Path(git(["rev-parse", "--show-toplevel"], cwd).rstrip("\n"))
        common = Path(git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd).rstrip("\n"))
        for where in [cwd] + ([top] if top != cwd else []):
            survey(plan, where, top)
        survey_pointers(plan, common, cwd)
    except OSError as error:
        # Planning only reads, so an unreadable file or directory changed nothing: a refusal.
        raise Refused(error.strerror or str(error), Path(error.filename) if error.filename else cwd)
    return plan


def remove(path: Path) -> None:
    """Remove a file, or an empty directory, that another run may have removed already."""
    try:
        if os.path.isdir(str(path)) and not os.path.islink(str(path)):
            os.rmdir(str(path))
        else:
            os.unlink(str(path))
    except FileNotFoundError:
        pass


def undo(error: BaseException, paths: List[Path]) -> bool:
    """Remove what a failed step created, in the given order; whether a removal failed. A removal that fails does
    not replace the error: its path and reason are added to it, and the caller raises the original."""
    failures = []
    for path in paths:
        try:
            remove(path)
        except OSError as cleanup:
            failures.append("%s not removed: %s" % (path, cleanup.strerror or cleanup))
    if not failures:
        return False
    note = "; ".join(failures)
    if isinstance(error, Refused):
        error.reason = "%s; %s" % (error.reason, note)
        error.args = (error.reason,)
    elif isinstance(error, OSError) and error.strerror:
        error.strerror = "%s; %s" % (error.strerror, note)
    elif isinstance(error, Exception):
        error.args = ("%s; %s" % (error, note),)
    return True


def replace(path: Path, data: bytes, like: Optional[Path] = None, created: Optional[List[Path]] = None,
            temporary_dir: Optional[Path] = None) -> None:
    """Write data to path atomically: a temporary file, in temporary_dir (one that does not move, on the same
    filesystem) or else path's directory, renamed into place and removed on any failure. Given created, the file is
    new instead: linked into place, which raises FileExistsError when the path exists and never replaces it, and
    added to created the moment it is linked; the temporary file joins created too, so a removal that fails here is
    still the caller's to account for."""
    directory = temporary_dir or path.parent
    descriptor, temporary = tempfile.mkstemp(dir=str(directory), prefix="." + path.name + ".")
    if created is not None:
        created.append(Path(temporary))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        if like is not None:
            shutil.copymode(str(like), temporary)
        if created is None:
            os.replace(temporary, str(path))
        else:
            os.link(temporary, str(path))
            created.append(path)
            os.unlink(temporary)
    except BaseException as error:
        if undo(error, [Path(temporary)]) and isinstance(error, FileExistsError):
            raise Leftover(error.errno, error.strerror, error.filename) from error
        raise


def prepare(plan: Plan, check_ignored: Callable[[Path], bool]) -> None:
    """Step 1: `.dopil` with its `*` .gitignore where missing, and git must report a path inside it ignored.
    On any failure it removes what it created and refuses; when something it created stays, it reports PARTIAL."""
    created: List[Path] = []
    new = None
    try:
        for old in plan.scratches:
            new = old.parent / NEW
            try:
                os.mkdir(str(new))
                created.append(new)
            except FileExistsError:
                pass
            ignore = new / ".gitignore"
            try:
                # Written whole, then linked into place: an interruption never leaves an empty .gitignore. It joins
                # created as it is linked, so a failure right after still removes it.
                replace(ignore, b"*\n", created=created)
            except FileExistsError:
                if not ignores_all(ignore):
                    raise Refused("is not the single line *", ignore)
            if plan.in_git and not check_ignored(new / "x"):
                raise Refused("is not reported ignored by git check-ignore", new / "x")
    except (Refused, OSError) as error:
        refusal = error if isinstance(error, Refused) else Refused(str(error), new)
        if undo(refusal, list(reversed(created))):
            # Something this step created is still there: not a clean refusal.
            raise Partial(partial(plan, 0, "%s: %s" % (refusal.path, refusal.reason)))
        raise refusal


def with_new_root(text: str, old: Path) -> str:
    """text with the old scratch root old replaced by the new one beside it, as a whole component: not when a name
    goes on after it."""
    return re.sub(re.escape(str(old)) + r"(?![\w-]|\.\w)", lambda match: str(old.parent / NEW), text)


def mark(gates: Path, waiting: List[str], today: str, aliases: Optional[List[Path]] = None) -> None:
    """Step 2: the new root prefix in a route's gates.md, for the old root and each alias of it, and, once, the line
    naming its gates to restart."""
    old = gates.parent.parent
    try:
        text = read_text(gates)
    except FileNotFoundError:
        return  # the route moved already, and its line with it
    changed = text
    for root in [old] + (aliases or []):
        changed = with_new_root(changed, root)
    if waiting and not MARKER.search(changed):
        changed += ("" if changed.endswith("\n") else "\n") + "Migrated %s: restart on resume: %s\n" % (
            today, ", ".join(waiting))
    if changed != text:
        try:
            # The temporary file in .dopil, which does not move: a run that loses the race leaves nothing behind.
            replace(gates, encoded(changed), gates, temporary_dir=old.parent / NEW)
        except FileNotFoundError:
            if os.path.lexists(str(gates)):
                raise
            # Another run marked the route and moved it, its line with it.


def move_entry(source: Path, target: Path) -> bool:
    """Step 3: one rename; whether this call moved it. A source that is gone has nothing left to move: its target is
    in place, or a fresh plan would not list it."""
    if not os.path.lexists(str(source)):
        return False
    if os.path.lexists(str(target)):
        raise Refused("exists already", target)
    os.rename(str(source), str(target))
    return True


def move_pointer(old: Path, new: Path, content: str) -> bool:
    """Step 4: the rewritten copy, written atomically, then the old pointer deleted; whether this call deleted it. A
    copy already in place counts as done when it is identical and is a refusal otherwise."""
    data = os.fsencode(content)
    if os.path.lexists(str(new)):
        if new.read_bytes() != data:
            raise Refused("exists with other content", new)
    elif os.path.lexists(str(old)):
        os.makedirs(str(new.parent), exist_ok=True)
        replace(new, data, old)
    else:
        return False  # gone with no copy: a fresh plan would not list it
    if not os.path.lexists(str(old)):
        return False
    remove(old)
    return True


def remove_if_empty(directory: Path) -> None:
    """Remove the directory when it is empty; one that is gone or holds something stays."""
    try:
        if not os.listdir(str(directory)):
            os.rmdir(str(directory))
    except OSError as error:
        if error.errno not in (errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST):
            raise


def finish(old: Path, plan: Plan) -> bool:
    """Step 5: once only its .gitignore is left, the old scratch is removed through a record that survives an
    interruption: written first, then the .gitignore unlinked, the directory removed by rmdir, the record deleted."""
    record = old.parent / NEW / RECORD
    if not os.path.lexists(str(record)):
        if not os.path.lexists(str(old)):
            return False  # removed by another run, and its record with it
        names = os.listdir(str(old))
        if names != [".gitignore"]:
            plan.leaves.append((old, "holds new entries, not removed" if names
                                else "empty, with no record of a migration"))
            return False
        st = os.lstat(str(old))
        replace(record, json.dumps({"path": str(old), "dev": st.st_dev, "ino": st.st_ino}).encode("utf-8"))
    dev, ino = read_record(record, old)
    removed = os.path.lexists(str(old))
    if removed:
        if not matches_record(old, dev, ino):
            plan.leaves.append((old, "does not match the record %s, kept with it" % record))
            return False
        remove(old / ".gitignore")
        remove(old)  # rmdir: it cannot remove data
    remove(record)
    return removed


def steps(plan: Plan, today: str, check_ignored: Callable[[Path], bool] = ignored) -> Iterator[str]:
    """Carry the plan out, yielding each of the five steps' names after it; a step finds what another run did as
    done. Each move this run does is added to plan.moved."""
    prepare(plan, check_ignored)
    yield STEPS[0]
    for gates, waiting in plan.markers.items():
        mark(gates, waiting, today, plan.aliases.get(gates.parent.parent))
    yield STEPS[1]
    for source, target in plan.moves:
        if move_entry(source, target):
            plan.moved.append((source, target))
    yield STEPS[2]
    for old, new, content in plan.pointers:
        if move_pointer(old, new, content):
            plan.moved.append((old, new))
    if plan.old_routes:
        remove_if_empty(plan.old_routes)
    yield STEPS[3]
    for old in plan.scratches:
        if finish(old, plan):
            plan.moved.append((old, old.parent / NEW))
    yield STEPS[4]


def run(cwd: Path, today: str, check_ignored: Callable[[Path], bool] = ignored) -> Plan:
    """Plan from cwd and carry the plan out. Refused: nothing it changed is kept; Partial: the next run finishes."""
    plan = make_plan(cwd)
    done = 0
    try:
        for _ in steps(plan, today, check_ignored):
            done += 1
    except Refused as error:
        if done == 0:
            raise
        raise Partial(partial(plan, done, "%s: %s" % (error.path, error.reason)))
    except OSError as error:
        raise Partial(partial(plan, done, str(error)))
    return plan


def partial(plan: Plan, done: int, error: str) -> str:
    """The interrupted step, the error, and every move this run did in that step and before it."""
    moved = ", ".join("%s -> %s" % move for move in plan.moved) or "nothing"
    return "%s, step %d of %d: %s; moved: %s" % (STEPS[done], done + 1, len(STEPS), error, moved)


def report(plan: Plan) -> List[str]:
    targets = dict(plan.moves)
    lines = ["MOVE %s -> %s" % move for move in plan.moves]
    lines += ["MOVE %s -> %s" % (old, new) for old, new, _ in plan.pointers]
    lines += ["MOVE %s -> %s" % (old, old.parent / NEW) for old in plan.scratches]
    lines += ["RESTART-LATER %s: %s" % (targets.get(gates.parent, gates.parent) / gates.name, ", ".join(waiting))
              for gates, waiting in plan.markers.items() if waiting]
    lines += ["LEAVE %s: %s" % leave for leave in plan.leaves]
    return lines


def encoded(text: str) -> bytes:
    return text.encode("utf-8", "surrogateescape")


def with_lines(text: str, lines: List[str]) -> str:
    return text + ("" if not text or text.endswith("\n") else "\n") + "".join(line + "\n" for line in lines)


def row_line(cells: List[str]) -> str:
    """A registry row; an empty cell is a single space."""
    return "|" + "|".join(" %s " % value if value else " " for value in cells) + "|"


def line_group(text: str, pattern: str) -> Optional[str]:
    """The group of the first whole line of text that matches pattern."""
    found = re.search("^" + pattern + "$", text, re.MULTILINE)
    return found.group(1) if found else None


def next_free(old: str, text: str, root: Path) -> str:
    """The next number of old's stage that neither a token of the registry's text nor an entry of the route takes:
    a name that starts with `<stage>-<NN>` and goes on with a non-digit or ends, so `code-02-retry` takes 02."""
    stage, number = old.rsplit("-", 1)
    pattern = re.compile(r"(?<![\w-])%s-(\d\d)(?!\d)" % stage)
    taken = {int(found) for name in [text] + os.listdir(str(root)) for found in pattern.findall(name)}
    number = int(number) + 1
    while number in taken:
        number += 1
    return "%s-%02d" % (stage, number)


def load_inputs(path: Path, moved: Callable[[str], str], root: Path) -> Inputs:
    """The executor's inputs, checked: the old attempt's scratch, an existing directory inside the route root, or
    null for a gate never prepared; its scope (one line, kept literal) and ledger header (empty when the old gate has
    no ledger); each reviewer's carried lines (an identical line once; one id with two claims refused); each snapshot
    pair with its copy present; and the locked set the executor read from the old row (none when it records none).
    moved maps a path under the old scratch root to its place under the moved one."""
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except OSError as error:
        raise Refused(error.strerror or str(error), path)
    except ValueError as error:
        raise Refused("is not JSON: %s" % error, path)
    if not isinstance(data, dict):
        raise Refused("is not a JSON object", path)
    given, scope, header = data.get("scratch"), data.get("scope"), data.get("header")
    if "scratch" not in data or not (given is None or isinstance(given, str) and given.strip()) or not (
            isinstance(scope, str) and scope.strip() and isinstance(header, str)):
        raise Refused("needs scratch (a path, or null for a gate never prepared), scope and header, scope not empty",
                      path)
    if "\n" in scope:
        raise Refused("scope %r: one line" % scope, path)
    scratch = None
    if given is not None:
        scratch = Path(moved(given))
        if not scratch.is_dir():
            raise Refused("is not a directory: the old attempt's scratch", scratch)
        real, inside = os.path.realpath(str(scratch)), os.path.realpath(str(root))
        if real == inside or not under(Path(real), Path(inside)):
            raise Refused("lies outside the route root %s" % root, scratch)
    carry, pairs, locked = data.get("carry", {}), data.get("snapshots", []), data.get("locked", [])
    if not isinstance(carry, dict) or not isinstance(pairs, list):
        raise Refused("needs a carry map and a snapshots list", path)
    if not isinstance(locked, list) or not all(isinstance(key, str) and re.fullmatch(KEY, key) for key in locked):
        raise Refused("locked %r: a list of scratch keys" % (locked,), path)
    for key, items in carry.items():
        if not re.fullmatch(KEY, key) or not isinstance(items, list) or not all(
                isinstance(item, str) and len(item.split(SEPARATOR)) >= 3 for item in items):
            raise Refused("carry %r: a scratch key with lines <id>%s<location>%s<claim>" % (key, SEPARATOR, SEPARATOR),
                          path)
        lines = {}  # id -> its line, in order
        for item in items:
            identifier = item.split(SEPARATOR, 1)[0].strip()
            if lines.setdefault(identifier, item) != item:
                raise Refused("carry %r: %s twice with different claims" % (key, identifier), path)
        carry[key] = list(lines.values())
    snapshots = []
    for pair in pairs:
        if not (isinstance(pair, list) and len(pair) == 2 and all(isinstance(part, str) for part in pair)):
            raise Refused("snapshot %r: not a pair [copy, original]" % (pair,), path)
        copy = Path(moved(pair[0]))
        if not copy.is_file():
            raise Refused("is not a file", copy)
        snapshots.append((copy, moved(pair[1])))
    return Inputs(raw, scratch, scope, header, carry, snapshots, locked)


def restart(gates_md: Path, old: str, inputs: Path) -> str:
    """Turn a migrated open gate into its next attempt and return the new gate's id. Each step finds what an earlier
    call did as done, and the outcome line is the only mark of completion. Nothing: no restart to do; Refused:
    nothing was written; an OSError: the next call finishes."""
    gates = Path(os.path.abspath(str(gates_md)))
    root = gates.parent
    if not GATE.fullmatch(old):
        raise Refused("%s is not a gate id" % old, gates)
    try:
        text = read_text(gates)
    except OSError as error:
        raise Refused(error.strerror or str(error), gates)
    superseded = line_group(text, re.escape(old) + r" superseded by (\S+)")
    if superseded:
        raise Nothing("superseded by %s" % superseded)
    marker = MARKER.search(text)
    if not marker:
        raise Nothing("no migration marker")
    source = line_group(text, r"(\S+) restarts as " + re.escape(old))
    if source:
        raise Nothing("the restart of %s" % source)
    named = text[marker.end():].split("\n", 1)[0].strip().split(", ")
    known = UNKNOWN not in named
    header, rows = table(text.split("\n"))
    if known:
        if old not in named:
            raise Nothing("not named in the marker")
        if header is None:
            raise Refused("registry form unknown", gates)
        if not any(cells[0] == old for _, cells in rows):
            raise Refused("has no row for %s" % old, gates)
    else:
        # A registry the migration could not read: the executor read it and names the gate.
        if not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(old), text):
            raise Nothing("not in the registry")
    assigned = line_group(text, re.escape(old) + r" restarts as (\S+)")
    new = assigned or next_free(old, text, root)
    new_scratch = root / new
    saved = new_scratch / "inputs.json"
    scratch_root = root.parent
    old_root = scratch_root.parent / OLD

    def moved(path: str) -> str:
        """An absolute path under the old scratch root, at its place under the moved one; any other path as given."""
        if not under(Path(path), old_root):
            return path
        return str(scratch_root.joinpath(*Path(path).parts[len(old_root.parts):]))

    source = saved if os.path.lexists(str(saved)) else inputs
    given = load_inputs(source, moved, root)
    old_scratch, carry = given.scratch, given.carry
    ledgers = {}
    for key in sorted(key for key, items in carry.items() if items):
        if old_scratch is None:
            raise Refused("carries items for %s of a gate never prepared, with no ledger to mark" % key, source)
        ledgers[key] = old_scratch / key / "ledger.md"
        if not os.path.isfile(str(ledgers[key])):
            ledgers[key] = old_scratch / "ledger.md"
        if not os.path.isfile(str(ledgers[key])):
            raise Refused("has no ledger to mark the items carried for %s" % key, old_scratch)

    # 1. The assignment, before anything else is written.
    if not assigned:
        text = with_lines(text, ["%s restarts as %s" % (old, new)])
        replace(gates, encoded(text), gates)
    # 2. The new scratch and the saved inputs; once saved, the given file is not read again.
    os.makedirs(str(new_scratch), exist_ok=True)
    if not os.path.lexists(str(saved)):
        replace(saved, given.raw)
    # 3. What the old attempt saved: its bases, and its snapshots with a new mapping to the original paths.
    names = [] if old_scratch is None else [""] + sorted(os.listdir(str(old_scratch)))  # none: never prepared
    for name in names:
        base = old_scratch / name / "base-sha"
        if os.path.isfile(str(base)):
            os.makedirs(str(new_scratch / name), exist_ok=True)
            replace(new_scratch / name / "base-sha", base.read_bytes())
    if given.snapshots:
        os.makedirs(str(new_scratch / "snapshots"), exist_ok=True)
        mapping = []
        for number, (copy, original) in enumerate(given.snapshots, 1):
            target = new_scratch / "snapshots" / ("%02d-%s" % (number, copy.name))
            replace(target, copy.read_bytes())
            mapping.append("%s -> %s" % (target, original))
        replace(new_scratch / "snapshots.txt", encoded(with_lines("", mapping)))
    # 4. Each carried reviewer's known items, and the old lines closed as carried.
    for key, ledger in ledgers.items():
        items = carry[key]
        os.makedirs(str(new_scratch / key), exist_ok=True)
        replace(new_scratch / key / "known-items.md", encoded(with_lines("", items)))
        before = read_text(ledger)
        marks = ["carried to %s/%s" % (new, item.split(SEPARATOR, 1)[0].strip()) for item in items]
        missing = [mark for mark in marks if mark not in before.split("\n")]
        if missing:
            replace(ledger, encoded(with_lines(before, missing)), ledger)
    # 5. The new ledger's opening lines, the new row, the old row closed, and the outcome line.
    new_ledger = new_scratch / "ledger.md"
    if given.header.strip() and not os.path.lexists(str(new_ledger)):
        replace(new_ledger, encoded(with_lines("", with_new_root(given.header, old_root).splitlines())))
    scope = with_new_root(given.scope, old_root)
    cell_scope = scope.replace("|", "\\|")  # literal everywhere; a table cell escapes its `|`
    lines = text.split("\n")
    added = []
    opened = "open (restarted from %s%s)" % (old, "; " + ", ".join(given.locked) if given.locked else "")
    if known:
        state = header.index("State")
        for index, cells in rows:
            if cells[0] == old and not is_closed(cell(cells, state)):
                cells = cells + [""] * (state + 1 - len(cells))
                cells[state] = "closed: superseded by %s (migration)" % new
                lines[index] = row_line(cells)
        if not any(cells[0] == new for _, cells in rows):
            cells = [""] * len(header)
            cells[0] = new
            if "Scope" in header:
                cells[header.index("Scope")] = cell_scope
            if "Scratch" in header:
                cells[header.index("Scratch")] = str(new_scratch)
            cells[state] = opened
            # Right after the last gate row, so the table stays one block above the marker and outcome lines.
            lines.insert(rows[-1][0] + 1, row_line(cells))
    else:
        entry = "%s: %s; scope: %s; scratch: %s" % (new, opened, scope, new_scratch)
        if any(line.lstrip().startswith("|") for line in lines):
            entry = row_line([new, cell_scope, str(new_scratch), opened, ""])
        if entry not in lines:
            added.append(entry)
    replace(gates, encoded(with_lines("\n".join(lines), added + ["%s superseded by %s" % (old, new)])), gates)
    return new


def main(argv: List[str]) -> int:
    if argv[1:2] == ["restart"] and len(argv) == 5:
        try:
            new = restart(Path(argv[2]), argv[3], Path(argv[4]))
        except Nothing as reason:
            print("NOTHING %s: %s" % (argv[3], reason))
            return 0
        except Refused as error:
            print("REFUSE %s: %s" % (error.path or argv[2], error.reason))
            return 2
        except OSError as error:
            print("PARTIAL %s" % error)
            return 3
        print("RESTART %s -> %s" % (argv[3], new))
        return 0
    if argv[1:] not in (["check"], ["run"]):
        print("usage: python3 -I <skill dir>/references/migrate.py check|run|restart <gates.md> <old gate> "
              "<inputs.json>", file=sys.stderr)
        return USAGE
    cwd = Path.cwd()
    try:
        plan = make_plan(cwd) if argv[1] == "check" else run(cwd, date.today().isoformat())
    except Refused as error:
        print("REFUSE %s: %s" % (error.path or cwd, error.reason))
        return 2
    except Partial as error:
        print("PARTIAL %s" % error)
        return 3
    for line in report(plan):
        print(line)
    return 1 if argv[1] == "check" and plan.scratches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
