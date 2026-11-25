"""Profile rules: a bundle's own conventions on top of OKF conformance.

OKF only says what consumers must tolerate, so a bundle that wants to keep its
own promises (every concept described, no broken links, every file indexed)
declares them in ``okf-profile.yaml`` at the bundle root. Every rule is off
unless the profile turns it on.
"""

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROFILE_FILE = "okf-profile.yaml"
RESERVED = ("index.md", "log.md")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
FENCE_RE = re.compile(r"^(```|~~~)")


@dataclass
class Profile:
    ignore: list = field(default_factory=list)
    non_concepts: list = field(default_factory=list)
    types_by_directory: dict = field(default_factory=dict)
    default_type: str = None
    required_fields: list = field(default_factory=list)
    forbidden_fields: list = field(default_factory=list)
    field_values: dict = field(default_factory=dict)
    ascii_only: bool = False
    title_heading: bool = False
    listed_in_index: bool = False
    broken_links: bool = False
    planned_marker: str = "(planned)"

    @classmethod
    def load(cls, root):
        path = Path(root) / PROFILE_FILE
        if not path.is_file():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        types = data.get("types") or {}
        fields = data.get("fields") or {}
        rules = data.get("rules") or {}
        return cls(
            ignore=list(data.get("ignore") or []),
            non_concepts=list(data.get("non_concepts") or []),
            types_by_directory=dict(types.get("by_directory") or {}),
            default_type=types.get("default"),
            required_fields=list(fields.get("required") or []),
            forbidden_fields=list(fields.get("forbidden") or []),
            field_values=dict(fields.get("values") or {}),
            ascii_only=bool(rules.get("ascii_only")),
            title_heading=bool(rules.get("title_heading")),
            listed_in_index=bool(rules.get("listed_in_index")),
            broken_links=bool(rules.get("broken_links")),
            planned_marker=rules.get("planned_marker", "(planned)"),
        )

    def is_ignored(self, rel):
        posix = rel.as_posix()
        return any(fnmatch.fnmatch(posix, pattern) for pattern in self.ignore)

    def is_non_concept(self, rel):
        posix = rel.as_posix()
        return any(fnmatch.fnmatch(posix, pattern) for pattern in self.non_concepts)

    def expected_type(self, rel):
        for part in reversed(rel.parts[:-1]):
            if part in self.types_by_directory:
                return self.types_by_directory[part]
        return self.default_type


@dataclass
class Finding:
    path: str
    line: int
    level: str
    code: str
    message: str


def bundle_files(root, profile):
    files = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts) or profile.is_ignored(rel):
            continue
        files.append(path)
    return files


def split_frontmatter(text):
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text, 1
    return match.group(1), text[match.end():], match.group(0).count("\n") + 1


def prose_links(body, first_line):
    """Yield (line number, target) for links outside fenced code blocks."""
    fenced = False
    for offset, line in enumerate(body.splitlines()):
        if FENCE_RE.match(line.strip()):
            fenced = not fenced
            continue
        if fenced:
            continue
        for target in LINK_RE.findall(re.sub(r"`[^`]*`", "", line)):
            yield first_line + offset, target


def resolve_link(root, source, target):
    """Return the absolute path a bundle link points to, or None if external."""
    target = target.split("#", 1)[0]
    if not target or SCHEME_RE.match(target):
        return None
    if target.startswith("/"):
        return (root / target.lstrip("/")).resolve()
    return (source.parent / target).resolve()


def planned_targets(root, files, marker):
    planned = set()
    for path in files:
        if path.name != "index.md":
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if marker in line:
                for target in LINK_RE.findall(line):
                    resolved = resolve_link(root, path, target)
                    if resolved:
                        planned.add(resolved)
    return planned


def check(root, profile):
    """Run the profile rules on the bundle at root and return the findings."""
    root = Path(root).resolve()
    findings = []

    def add(path, line, code, message):
        findings.append(Finding(path.relative_to(root).as_posix(), line, "error", code, message))

    files = bundle_files(root, profile)
    planned = planned_targets(root, files, profile.planned_marker)
    indexed = {}
    for path in files:
        if path.name == "index.md":
            _, body, _ = split_frontmatter(path.read_text(encoding="utf-8"))
            indexed[path.parent] = {resolve_link(root, path, t) for t in LINK_RE.findall(body)}
    for path in files:
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        if profile.ascii_only:
            for number, line in enumerate(text.splitlines(), 1):
                bad = sorted({c for c in line if ord(c) > 127})
                if bad:
                    add(path, number, "P001", f"non-ASCII characters {''.join(bad)!r}")
        raw, body, body_line = split_frontmatter(text)
        is_concept = path.name not in RESERVED and raw is not None
        if path.name not in RESERVED and raw is None and not profile.is_non_concept(rel):
            if profile.default_type or profile.types_by_directory:
                add(path, 1, "P002", "missing frontmatter (list the file in non_concepts if it is not a concept)")
        meta = {}
        if is_concept:
            try:
                meta = yaml.safe_load(raw) or {}
            except yaml.YAMLError:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
        if is_concept:
            expected = profile.expected_type(rel)
            if expected and meta.get("type") != expected:
                add(path, 1, "P003", f"type is {meta.get('type')!r}, expected {expected!r} here")
            for key in profile.required_fields:
                value = meta.get(key)
                if value is None or (isinstance(value, (str, list)) and not value):
                    add(path, 1, "P004", f"missing or empty '{key}'")
            for key in profile.forbidden_fields:
                if key in meta:
                    add(path, 1, "P005", f"'{key}' is not used in this bundle")
            for key, allowed in profile.field_values.items():
                if key in meta and meta[key] not in allowed:
                    add(path, 1, "P006", f"{key} is {meta[key]!r}, expected one of {allowed}")
            if profile.title_heading and isinstance(meta.get("title"), str):
                heading = next((l for l in body.splitlines() if l.startswith("# ")), None)
                if heading != f"# {meta['title']}":
                    add(path, body_line, "P007", f"first level-1 heading must be '# {meta['title']}'")
        if profile.broken_links:
            for line, target in prose_links(body, body_line):
                resolved = resolve_link(root, path, target)
                if resolved and not resolved.exists() and resolved not in planned:
                    add(path, line, "P008", f"broken link {target} (mark it {profile.planned_marker} in an index.md if it is planned)")
        if profile.listed_in_index and is_concept and len(rel.parts) > 1:
            listing = indexed.get(path.parent)
            if listing is None:
                add(path, 1, "P009", f"{rel.parent.as_posix()}/ has no index.md")
            elif path.resolve() not in listing:
                add(path, 1, "P010", "not listed in its directory index.md")
    return findings
