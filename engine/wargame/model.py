"""Level contract: YAML loading, validation, and template resolution.

A level is a *declarative* delta applied to the filesystem.
`provision.py` applies the delta; `audit.py` verifies the result.

Template variables:
    {{user}}        the player who owns the files (e.g. player03)
    {{level}}       level identifier ("03")
    {{slug}}        level slug
    {{title}}       level title
    {{flag}}        the flag produced by this level  (pass/NN+1)
    {{flag:05}}     flag for an explicitly named level
    {{flag:05|b64}} same value, base64-encoded
    {{flag:05|hex}} same value, hex-encoded
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

import yaml

LEVEL_ID_RE = re.compile(r"^(\d{2})-([a-z0-9][a-z0-9-]*)$")
TEMPLATE_RE = re.compile(r"\{\{\s*([A-Za-z0-9_:]+)(?:\|([a-z0-9]+))?\s*\}\}")
MODE_RE = re.compile(r"^[0-7]{3,4}$")
PATH_RE = re.compile(r"^/[A-Za-z0-9._/-]+$")
USER_RE = re.compile(r"^(root|player\d{2}|[a-z][a-z0-9_-]{2,31})$")
FLAG_FILTERS = {"b64", "hex"}
ARCHIVE_FORMATS = {"tar", "tar.gz", "tar.bz2", "tar.xz"}
WHEN_VALUES = {"always", "suid-disabled", "suid-enabled"}
CRON_MACROS = {
    "@reboot", "@yearly", "@annually", "@monthly",
    "@weekly", "@daily", "@midnight", "@hourly",
}


class LevelError(ValueError):
    """Invalid level definition."""


@dataclass(frozen=True)
class DirSpec:
    path: str
    owner: str
    mode: int


@dataclass(frozen=True)
class FileSpec:
    path: str
    owner: str
    mode: int
    template: str | None = None
    content: str | None = None
    source: str | None = None
    # Fixed-size file: content is padded to this byte count with newlines.
    # Makes `find -size Nc` puzzles deterministic.
    pad_to: int | None = None
    # text: written as-is; xor: bytes XORed with 0x5A (reverse-engineering level).
    encoding: str = "text"
    # always | suid-disabled | suid-enabled — profile-conditional content.
    when: str = "always"

    @property
    def kind(self) -> str:
        if self.template:
            return "template"
        if self.content is not None:
            return "inline"
        return "source"


@dataclass(frozen=True)
class ArchiveMember:
    """An entry inside an archive. May itself be a nested archive."""

    name: str
    template: str | None = None
    content: str | None = None
    fmt: str | None = None
    members: tuple["ArchiveMember", ...] = ()


@dataclass(frozen=True)
class ArchiveSpec:
    path: str
    owner: str
    mode: int
    fmt: str
    members: tuple[ArchiveMember, ...] = ()


@dataclass(frozen=True)
class AclSpec:
    """Extra permission on a file (POSIX ACL).

    SUID and file capabilities (setcap) do not work under `no_new_privs`;
    file permissions/ACLs are unaffected. This is how privileges are granted
    in the hardened profile.
    """

    path: str
    user: str
    perms: str
    when: str = "suid-disabled"


@dataclass(frozen=True)
class PcapSpec:
    """Captured HTTP traffic; produces packets carrying the flag."""

    path: str
    owner: str
    mode: int
    host: str
    seal: str


@dataclass(frozen=True)
class CronSpec:
    user: str
    schedule: str
    command: str
    when: str = "always"


@dataclass
class Level:
    id: str
    slug: str
    title: str
    concept: list[str]
    requires: str | None
    estimated_minutes: int
    users: list[str]
    dirs: list[DirSpec]
    files: list[FileSpec]
    archives: list[ArchiveSpec]
    pcaps: list[PcapSpec]
    acls: list[AclSpec]
    cron: list[CronSpec]
    hints: list[str]
    docs: str | None
    expose: list[str]
    flag_owner: str
    flag_mode: int
    root: Path
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def user(self) -> str:
        return f"player{self.id}"

    @property
    def next_id(self) -> str:
        return f"{int(self.id) + 1:02d}"

    @property
    def flag_path(self) -> str:
        return f"/etc/wargame/pass/{self.id}"

    def file_paths(self) -> list[str]:
        return [f.path for f in self.files]


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def load_level(directory: Path) -> Level:
    directory = Path(directory)
    manifest = directory / "level.yml"
    if not manifest.is_file():
        raise LevelError(f"{directory}: level.yml not found")

    data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise LevelError(f"{manifest}: root must be a mapping")

    match = LEVEL_ID_RE.match(directory.name)
    if not match:
        raise LevelError(
            f"{directory.name}: directory name must follow '<id>-<slug>' format"
        )
    dir_id, dir_slug = match.group(1), match.group(2)

    level_id = _require_str(data, "id", manifest)
    if not level_id.isdigit() or len(level_id) != 2:
        raise LevelError(f"{manifest}: id must be a two-digit number")
    if level_id != dir_id:
        raise LevelError(f"{manifest}: id ({level_id}) does not match directory ({dir_id})")

    slug = str(data.get("slug", dir_slug))
    if slug != dir_slug:
        raise LevelError(f"{manifest}: slug ({slug}) does not match directory ({dir_slug})")

    owner_default = f"player{level_id}"
    extra_users = _str_list(data.get("users", []), "users", manifest)
    allowed_owners = {"root", owner_default, *extra_users}

    next_owner = f"player{int(level_id) + 1:02d}"
    dirs = [_parse_dir(raw, i, allowed_owners, manifest) for i, raw in enumerate(_list(data, "dirs", manifest))]
    files = [
        _parse_file(raw, i, allowed_owners, next_owner, directory, manifest)
        for i, raw in enumerate(_list(data, "files", manifest))
    ]
    archives = [
        _parse_archive(raw, i, allowed_owners, directory, manifest)
        for i, raw in enumerate(_list(data, "archives", manifest))
    ]
    pcaps = [
        _parse_pcap(raw, i, allowed_owners, manifest)
        for i, raw in enumerate(_list(data, "pcaps", manifest))
    ]
    acls = [
        _parse_acl(raw, i, manifest)
        for i, raw in enumerate(_list(data, "acl", manifest))
    ]
    if not files and not archives and not pcaps:
        raise LevelError(f"{manifest}: at least one file, archive, or pcap must be declared")

    seen: set[str] = set()
    for path in (
        [d.path for d in dirs]
        + [f.path for f in files]
        + [a.path for a in archives]
        + [p.path for p in pcaps]
    ):
        if path in seen:
            raise LevelError(f"{manifest}: duplicate path {path}")
        seen.add(path)

    # Cron jobs may run as the level user, root, or the next user
    # (e.g. a service that serves its own flag).
    cron = [_parse_cron(raw, i, {owner_default, "root", next_owner, *extra_users}, manifest)
            for i, raw in enumerate(_list(data, "cron", manifest))]

    flag_raw = data.get("flag") or {}
    if not isinstance(flag_raw, dict):
        raise LevelError(f"{manifest}: flag must be a mapping")
    flag_owner = str(flag_raw.get("owner", owner_default))
    if flag_owner not in allowed_owners:
        raise LevelError(f"{manifest}: flag owner not declared: {flag_owner}")
    flag_mode = _parse_mode(flag_raw.get("mode", "0400"), f"{manifest}: flag")

    requires = data.get("requires")
    if requires is not None:
        requires = str(requires).zfill(2)
        if requires != f"{int(level_id) - 1:02d}":
            raise LevelError(
                f"{manifest}: requires must be the immediately preceding level "
                f"({int(level_id) - 1:02d})"
            )

    hints = _str_list(data.get("hints", []), "hints", manifest)
    if len(hints) < 2:
        raise LevelError(f"{manifest}: at least 2 graduated hints required")

    # Runtime-generated files: treated as legitimate during audit
    # (e.g. a cron job's flag output).
    expose = [_parse_path(p, f"{manifest}: expose") for p in _list(data, "expose", manifest)]

    return Level(
        id=level_id,
        slug=slug,
        title=_require_str(data, "title", manifest),
        concept=_str_list(data.get("concept", []), "concept", manifest),
        requires=requires,
        estimated_minutes=int(data.get("estimated_minutes", 10)),
        users=extra_users,
        dirs=dirs,
        files=files,
        archives=archives,
        pcaps=pcaps,
        acls=acls,
        cron=cron,
        hints=hints,
        docs=data.get("docs"),
        expose=expose,
        flag_owner=flag_owner,
        flag_mode=flag_mode,
        root=directory,
        raw=data,
    )


def load_all(root: Path) -> list[Level]:
    root = Path(root)
    levels = [load_level(p) for p in sorted(root.iterdir()) if p.is_dir() and (p / "level.yml").is_file()]
    if not levels:
        raise LevelError(f"{root}: no levels found")

    levels.sort(key=lambda lv: lv.id)
    expected = [f"{i:02d}" for i in range(len(levels))]
    actual = [lv.id for lv in levels]
    if actual != expected:
        raise LevelError(f"level IDs must be contiguous starting at 00: {actual}")

    slugs = [lv.slug for lv in levels]
    if len(set(slugs)) != len(slugs):
        raise LevelError("slugs must be unique")

    return levels


# ---------------------------------------------------------------------------
# templating
# ---------------------------------------------------------------------------


def template_variables(text: str) -> list[str]:
    """Return all variable names (without filters) referenced in a template."""
    return [m.group(1) for m in TEMPLATE_RE.finditer(text)]


def render(text: str, context: dict[str, str], *, where: str = "<text>") -> str:
    def replace(match: re.Match[str]) -> str:
        key, filter_name = match.group(1), match.group(2)
        if key not in context:
            raise LevelError(f"{where}: unknown template variable {{{{ {key} }}}}")
        value = context[key]
        return _apply_filter(value, filter_name, where)

    return TEMPLATE_RE.sub(replace, text)


def _apply_filter(value: str, name: str | None, where: str) -> str:
    if name is None:
        return value
    if name not in FLAG_FILTERS:
        raise LevelError(f"{where}: unknown filter '{name}'")
    raw = value.encode("utf-8")
    if name == "b64":
        return base64.b64encode(raw).decode("ascii")
    return raw.hex()


def build_context(level: Level, flag_for: Callable[[str], str]) -> dict[str, str]:
    """Build the template context dictionary for a level."""
    context = {
        "user": level.user,
        "level": level.id,
        "slug": level.slug,
        "title": level.title,
        "flag": flag_for(level.next_id),
    }
    # Resolve all {{flag:NN}} references found in the level's content.
    for match in TEMPLATE_RE.finditer(_all_template_sources(level)):
        key = match.group(1)
        if key.startswith("flag:"):
            target = key.split(":", 1)[1]
            if not target.isdigit():
                raise LevelError(f"invalid flag reference: {key}")
            context[key] = flag_for(target.zfill(2))
    return context


def iter_member_texts(level: Level, members: tuple[ArchiveMember, ...]) -> Iterator[tuple[str, str]]:
    """Iterate over archive members as (name, template-text) pairs."""
    for member in members:
        if member.template:
            path = level.root / member.template
            try:
                yield member.name, path.read_text(encoding="utf-8")
            except OSError as exc:
                raise LevelError(f"{member.template}: cannot read ({exc})") from exc
        elif member.content is not None:
            yield member.name, member.content
        yield from iter_member_texts(level, member.members)


def _all_template_sources(level: Level) -> str:
    parts: list[str] = []
    for spec in level.files:
        if spec.content is not None:
            parts.append(spec.content)
        elif spec.template:
            try:
                parts.append((level.root / spec.template).read_text(encoding="utf-8"))
            except OSError as exc:
                raise LevelError(f"{spec.template}: cannot read ({exc})") from exc
    for spec in level.archives:
        parts.extend(text for _, text in iter_member_texts(level, spec.members))
    for spec in level.pcaps:
        parts.append(spec.seal)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _list(data: dict[str, Any], key: str, manifest: Path) -> list[Any]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise LevelError(f"{manifest}: '{key}' must be a list")
    return value


def _str_list(value: Any, key: str, manifest: Path) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise LevelError(f"{manifest}: '{key}' must be a list of strings")
    return list(value)


def _require_str(data: dict[str, Any], key: str, manifest: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LevelError(f"{manifest}: '{key}' is required")
    return value.strip()


def _parse_mode(value: Any, where: str) -> int:
    text = str(value)
    if not MODE_RE.match(text):
        raise LevelError(f"{where}: invalid mode '{value}' (e.g. \"0640\", \"4755\")")
    return int(text, 8)


def _parse_path(value: Any, where: str) -> str:
    text = str(value)
    if not PATH_RE.match(text) or ".." in text:
        raise LevelError(f"{where}: invalid absolute path '{value}'")
    return text


def _parse_dir(raw: Any, index: int, owners: set[str], manifest: Path) -> DirSpec:
    where = f"{manifest}: dirs[{index}]"
    if not isinstance(raw, dict):
        raise LevelError(f"{where}: must be a mapping")
    owner = str(raw.get("owner", ""))
    if owner not in owners:
        raise LevelError(f"{where}: undeclared owner '{owner}'")
    return DirSpec(
        path=_parse_path(raw.get("path"), where),
        owner=owner,
        mode=_parse_mode(raw.get("mode", "0750"), where),
    )


def _parse_file(
    raw: Any,
    index: int,
    owners: set[str],
    next_owner: str,
    root: Path,
    manifest: Path,
) -> FileSpec:
    where = f"{manifest}: files[{index}]"
    if not isinstance(raw, dict):
        raise LevelError(f"{where}: must be a mapping")
    owner = str(raw.get("owner", ""))
    mode = _parse_mode(raw.get("mode", "0640"), where)

    if owner not in owners:
        if owner != next_owner:
            raise LevelError(f"{where}: undeclared owner '{owner}'")
        # A file owned by the next level's user is only allowed when
        # it carries the SUID or SGID bit (e.g. a setuid reader binary).
        if not mode & 0o6000:
            raise LevelError(
                f"{where}: file owned by {owner} is only allowed with SUID/SGID mode"
            )

    sources = [k for k in ("template", "content", "source") if raw.get(k) is not None]
    if len(sources) != 1:
        raise LevelError(f"{where}: exactly one of template/content/source is required")
    kind = sources[0]

    encoding = str(raw.get("encoding", "text"))
    if encoding not in ("text", "xor"):
        raise LevelError(f"{where}: invalid encoding '{encoding}' (text | xor)")

    when = str(raw.get("when", "always"))
    if when not in WHEN_VALUES:
        raise LevelError(f"{where}: invalid when '{when}' ({', '.join(sorted(WHEN_VALUES))})")

    pad_to = raw.get("pad_to")
    if pad_to is not None:
        if not isinstance(pad_to, int) or isinstance(pad_to, bool) or not 0 < pad_to <= 1_048_576:
            raise LevelError(f"{where}: pad_to must be an integer in 1..1048576")

    spec = FileSpec(
        path=_parse_path(raw.get("path"), where),
        owner=owner,
        mode=mode,
        template=raw.get("template"),
        content=raw.get("content"),
        source=raw.get("source"),
        pad_to=pad_to,
        encoding=encoding,
        when=when,
    )

    if kind == "template":
        candidate = (root / str(spec.template)).resolve()
        if root.resolve() not in candidate.parents:
            raise LevelError(f"{where}: template path escapes the level directory")
        if not candidate.is_file():
            raise LevelError(f"{where}: template not found: {spec.template}")
    return spec


def _parse_archive(
    raw: Any,
    index: int,
    owners: set[str],
    root: Path,
    manifest: Path,
) -> ArchiveSpec:
    where = f"{manifest}: archives[{index}]"
    if not isinstance(raw, dict):
        raise LevelError(f"{where}: must be a mapping")
    owner = str(raw.get("owner", ""))
    if owner not in owners:
        raise LevelError(f"{where}: undeclared owner '{owner}'")
    fmt = str(raw.get("format", "tar.gz"))
    if fmt not in ARCHIVE_FORMATS:
        raise LevelError(f"{where}: invalid format '{fmt}' ({', '.join(sorted(ARCHIVE_FORMATS))})")
    members = _parse_members(raw.get("members"), where, root, manifest)
    if not members:
        raise LevelError(f"{where}: archive must have at least one member")
    return ArchiveSpec(
        path=_parse_path(raw.get("path"), where),
        owner=owner,
        mode=_parse_mode(raw.get("mode", "0640"), where),
        fmt=fmt,
        members=tuple(members),
    )


def _parse_members(raw: Any, where: str, root: Path, manifest: Path) -> list[ArchiveMember]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise LevelError(f"{where}: members must be a list")
    parsed: list[ArchiveMember] = []
    for position, item in enumerate(raw):
        spot = f"{where}.members[{position}]"
        if not isinstance(item, dict):
            raise LevelError(f"{spot}: must be a mapping")
        name = str(item.get("name", ""))
        if not name or name.startswith("/") or ".." in name:
            raise LevelError(f"{spot}: invalid member name '{name}'")
        sources = [k for k in ("template", "content") if item.get(k) is not None]
        nested_raw = item.get("members")
        if nested_raw is not None and sources:
            raise LevelError(f"{spot}: nested archive and content cannot be combined")
        if nested_raw is None and len(sources) != 1:
            raise LevelError(f"{spot}: exactly one of template/content is required")

        nested: list[ArchiveMember] = []
        fmt: str | None = None
        if nested_raw is not None:
            fmt = str(item.get("format", "tar.gz"))
            if fmt not in ARCHIVE_FORMATS:
                raise LevelError(f"{spot}: invalid format '{fmt}'")
            nested = _parse_members(nested_raw, spot, root, manifest)
            if not nested:
                raise LevelError(f"{spot}: nested archive must have at least one member")

        if item.get("template"):
            candidate = (root / str(item["template"])).resolve()
            if root.resolve() not in candidate.parents or not candidate.is_file():
                raise LevelError(f"{spot}: template not found: {item['template']}")

        parsed.append(ArchiveMember(
            name=name,
            template=item.get("template"),
            content=item.get("content"),
            fmt=fmt,
            members=tuple(nested),
        ))
    return parsed


def _parse_acl(raw: Any, index: int, manifest: Path) -> AclSpec:
    where = f"{manifest}: acl[{index}]"
    if not isinstance(raw, dict):
        raise LevelError(f"{where}: must be a mapping")
    user = str(raw.get("user", ""))
    if not USER_RE.match(user):
        raise LevelError(f"{where}: invalid user '{user}'")
    perms = str(raw.get("perms", ""))
    if not perms or set(perms) - set("rwx"):
        raise LevelError(f"{where}: perms may only contain r/w/x")
    when = str(raw.get("when", "suid-disabled"))
    if when not in ("always", "suid-disabled"):
        raise LevelError(f"{where}: when must be 'always' or 'suid-disabled'")
    return AclSpec(
        path=_parse_path(raw.get("path"), where),
        user=user,
        perms=perms,
        when=when,
    )


def _parse_pcap(raw: Any, index: int, owners: set[str], manifest: Path) -> PcapSpec:
    where = f"{manifest}: pcaps[{index}]"
    if not isinstance(raw, dict):
        raise LevelError(f"{where}: must be a mapping")
    owner = str(raw.get("owner", ""))
    if owner not in owners:
        raise LevelError(f"{where}: undeclared owner '{owner}'")
    seal = str(raw.get("seal", "{{flag}}"))
    host = str(raw.get("host", "repository.calder.example"))
    if not host or "\n" in host:
        raise LevelError(f"{where}: invalid host")
    return PcapSpec(
        path=_parse_path(raw.get("path"), where),
        owner=owner,
        mode=_parse_mode(raw.get("mode", "0640"), where),
        host=host,
        seal=seal,
    )


def _parse_cron(raw: Any, index: int, users: set[str], manifest: Path) -> CronSpec:
    where = f"{manifest}: cron[{index}]"
    if not isinstance(raw, dict):
        raise LevelError(f"{where}: must be a mapping")
    user = str(raw.get("user", ""))
    if user not in users:
        raise LevelError(f"{where}: undeclared user '{user}'")
    schedule = str(raw.get("schedule", "")).split()
    if len(schedule) == 1 and schedule[0].startswith("@"):
        if schedule[0] not in CRON_MACROS:
            raise LevelError(f"{where}: unknown schedule macro '{schedule[0]}'")
    elif len(schedule) != 5:
        raise LevelError(f"{where}: schedule must have 5 fields (min hour day month weekday)")
    command = str(raw.get("command", "")).strip()
    if not command or "\n" in command:
        raise LevelError(f"{where}: command must be a single line")
    when = str(raw.get("when", "always"))
    if when not in WHEN_VALUES:
        raise LevelError(f"{where}: invalid when '{when}'")
    return CronSpec(user=user, schedule=" ".join(schedule), command=command, when=when)
