"""Level audit (leak audit).

Purpose: prove that a level does not accidentally leave a flag it does not
own in a world-readable location. The audit searches for flag values in
three encodings (plain, base64, hex) and fails if any are found outside
the allowed paths.

Expected paths:
  * /etc/wargame/pass/NN        canonical flag file
  * level templates that reference {{flag:NN}} (puzzle artefact)
"""

from __future__ import annotations

import base64
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from .model import Level, build_context, template_variables
from .policy import applies, effective_mode

SCAN_ROOTS = ("/etc", "/home", "/opt", "/srv", "/usr/local", "/var")
SKIP_PREFIXES = ("/proc", "/sys", "/dev", "/run", "/var/lib/docker", "/var/cache")
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}
MAX_BYTES = 4 * 1024 * 1024
WORLD_WRITABLE_ALLOW = ("/tmp", "/var/tmp", "/run", "/dev", "/var/spool/wargame")


@dataclass
class Finding:
    check: str
    path: str
    detail: str
    severity: str = "error"

    def __str__(self) -> str:
        return f"[{self.severity}] {self.check} {self.path}: {self.detail}"


@dataclass
class AuditReport:
    findings: list[Finding] = field(default_factory=list)
    scanned_files: int = 0

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)

    def add(self, check: str, path: str, detail: str, severity: str = "error") -> None:
        self.findings.append(Finding(check, path, detail, severity))


def _encodings(value: str) -> list[bytes]:
    raw = value.encode()
    return [raw, base64.b64encode(raw), raw.hex().encode()]


def _allowlist(level: Level, flag_for) -> set[str]:
    """Paths that this level is legitimately allowed to expose."""
    allowed = {level.flag_path, f"/etc/wargame/pass/{level.next_id}"}
    # Runtime-generated outputs that are legitimately visible (e.g. cron job output).
    allowed.update(level.expose)
    context = build_context(level, flag_for)
    for spec in level.files:
        if spec.template:
            try:
                text = (level.root / spec.template).read_text(encoding="utf-8")
            except OSError:
                continue
        else:
            text = spec.content or ""
        for variable in template_variables(text):
            target = variable.split(":", 1)[1] if ":" in variable else level.next_id
            if context.get(variable) and target.zfill(2) == level.next_id:
                allowed.add(spec.path)
    # Archives and pcaps carry the flag as their own artefact.
    allowed.update(spec.path for spec in level.archives)
    allowed.update(spec.path for spec in level.pcaps)
    return allowed


def audit(levels: list[Level], flag_for) -> AuditReport:
    report = AuditReport()

    owners = _file_owners()
    allowlist: set[str] = set()
    patterns: list[tuple[str, bytes, str]] = []
    for level in levels:
        allowlist |= _allowlist(level, flag_for)
        for pid in (level.id, level.next_id):
            value = flag_for(pid)
            for encoded in _encodings(value):
                patterns.append((pid, encoded, value))

    for level in levels:
        report.findings.extend(_check_flag_file(level, owners))
        report.findings.extend(_check_declared_files(level))

    for root in SCAN_ROOTS:
        base = Path(root)
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            if dirpath.startswith(SKIP_PREFIXES):
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
            for name in filenames:
                path = os.path.join(dirpath, name)
                if path in allowlist:
                    continue
                _scan_file(report, path, patterns, allowlist, owners)

    return report


def _file_owners() -> dict[str, str]:
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return {}
    try:
        import pwd
    except ImportError:  # pragma: no cover
        return {}
    return {}


def _check_declared_files(level: Level) -> list[Finding]:
    """Verify that every declared file exists with the correct mode and owner.

    This catches silent SUID loss: chown clears SUID even when the owner
    does not change (when CAP_FSETID is absent).
    """
    findings: list[Finding] = []
    declared = [
        spec for spec in (list(level.files) + list(level.archives) + list(level.pcaps))
        if applies(getattr(spec, "when", "always"))
    ]
    for spec in declared:
        path = Path(spec.path)
        if not path.is_file():
            findings.append(Finding("file-missing", spec.path, "declared file not present"))
            continue
        st = path.stat()
        actual = stat.S_IMODE(st.st_mode)
        expected = effective_mode(spec.mode)
        if not _mode_matches(path, actual, expected):
            findings.append(Finding(
                "file-mode", spec.path,
                f"mode {actual:04o}, declared {expected:04o}",
            ))
        owner = _user_name(st.st_uid)
        if owner is not None and owner != spec.owner:
            findings.append(Finding(
                "file-owner", spec.path,
                f"owner {owner}, declared {spec.owner}",
            ))
    return findings


def _mode_matches(path: Path, actual: int, expected: int) -> bool:
    """Handle POSIX ACL group-triple masking.

    `setfacl -m u:player02:r` rewrites the group permission bits as the
    ACL mask (e.g. 0400 → 0440). This is ACL semantics, not a bug.
    Owner, other, and special bits (SUID/SGID/sticky) are still compared
    exactly.
    """
    mask = 0o707 if _has_extended_acl(path) else 0o7777
    return (actual & mask) == (expected & mask)


def _has_extended_acl(path: Path) -> bool:
    try:
        os.getxattr(path, "system.posix_acl_access")
    except (OSError, AttributeError):
        return False
    return True


def _user_name(uid: int) -> str | None:
    try:
        import pwd
    except ImportError:  # pragma: no cover
        return None
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def _check_flag_file(level: Level, _owners: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    path = Path(level.flag_path)
    if not path.is_file():
        findings.append(Finding("flag-missing", str(path), "canonical flag file not present"))
        return findings
    st = path.stat()
    actual = stat.S_IMODE(st.st_mode)
    if not _mode_matches(path, actual, level.flag_mode):
        findings.append(Finding(
            "flag-mode", str(path),
            f"mode {actual:04o}, expected {level.flag_mode:04o}",
        ))
    if st.st_uid == 0 and level.flag_owner != "root":
        findings.append(Finding("flag-owner", str(path), "owned by root, not the player"))
    return findings


def _scan_file(report: AuditReport, path: str, patterns, allowlist: set[str], _owners) -> None:
    try:
        st = os.lstat(path)
    except OSError:
        return
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES:
        return
    if st.st_mode & stat.S_IWOTH and not path.startswith(WORLD_WRITABLE_ALLOW):
        report.add("world-writable", path, f"mode {stat.S_IMODE(st.st_mode):04o}")
    if st.st_mode & (stat.S_ISUID | stat.S_ISGID):
        report.add("setuid", path, f"mode {stat.S_IMODE(st.st_mode):04o}", severity="warn")

    report.scanned_files += 1
    try:
        data = Path(path).read_bytes()
    except OSError:
        return
    for pid, encoded, raw in patterns:
        if encoded and encoded in data:
            report.add(
                "flag-leak", path,
                f"level {pid} flag found in non-allowed file "
                f"({_encoding_name(encoded, raw)})",
            )
            break


def _encoding_name(encoded: bytes, raw: str) -> str:
    if encoded == raw.encode():
        return "plain"
    if encoded == base64.b64encode(raw.encode()):
        return "base64"
    return "hex"
