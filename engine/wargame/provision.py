"""Apply level definitions to the filesystem.

Design principle: materialization is **idempotent**. The same input
produces the same state every time the container starts; no step
second-guesses "is this already done?" — it compares instead.

Security note: this script runs as root. It only writes to paths declared
in level definitions and accepts no user input.
"""

from __future__ import annotations

import argparse
import bz2
import gzip
import io
import lzma
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from . import flags as flaglib
from . import pcap as pcap_builder
from .model import Level, LevelError, build_context, load_all, render
from .policy import applies, effective_mode, suid_disabled

try:  # pwd/grp are not available on Windows development machines.
    import grp
    import pwd
except ImportError:  # pragma: no cover
    grp = None  # type: ignore[assignment]
    pwd = None  # type: ignore[assignment]

PASS_DIR = Path("/etc/wargame/pass")
CRON_DIR = Path("/etc/cron.d")
UID_BASE = 3000
DEFAULT_LEVELS = Path(os.environ.get("WARGAME_LEVELS", "levels"))


class ProvisionError(RuntimeError):
    """Materialization failed."""


class Provisioner:
    def __init__(
        self,
        levels: list[Level],
        secret: bytes,
        epoch: str,
        *,
        dry_run: bool = False,
        quiet: bool = False,
    ) -> None:
        self.levels = levels
        self.epoch = epoch
        self.dry_run = dry_run
        self.quiet = quiet
        self.actions = 0
        last = int(levels[-1].id)
        self.ids = [f"{i:02d}" for i in range(last + 2)]  # last level + final
        self.flags = {pid: flaglib.derive_flag(secret, pid, epoch) for pid in self.ids}

    # -- helpers -----------------------------------------------------------

    def log(self, message: str) -> None:
        self.actions += 1
        if not self.quiet:
            prefix = "plan" if self.dry_run else "apply"
            print(f"[{prefix}] {message}")

    @staticmethod
    def _display(path: Path) -> str:
        """Always display POSIX paths (log lines are platform-independent)."""
        return "/" + str(path).replace("\\", "/").lstrip("/")

    def flag_for(self, level_id: str) -> str:
        try:
            return self.flags[level_id]
        except KeyError as exc:
            raise ProvisionError(f"undefined level flag: {level_id}") from exc

    # -- steps -------------------------------------------------------------

    def run(self) -> int:
        self._require_root()
        self._ensure_base_dirs()
        self._ensure_users()
        self._apply_passwords()
        for level in self.levels:
            self._apply_level(level)
        return self.actions

    def _require_root(self) -> None:
        if self.dry_run:
            return
        if pwd is None:
            raise ProvisionError("materialization requires POSIX (use --dry-run on Windows)")
        if os.geteuid() != 0:
            raise ProvisionError("materialization must run as root")

    def _ensure_base_dirs(self) -> None:
        for path, mode in ((PASS_DIR, 0o755), (CRON_DIR, 0o755)):
            self._ensure_dir(path, "root", mode)

    def _ensure_users(self) -> None:
        for index, level_id in enumerate(self.ids):
            uid = UID_BASE + index
            name = self.player_name(level_id)
            self._ensure_group(name, uid)
            self._ensure_user(name, uid, f"/home/{name}")

    def _apply_passwords(self) -> None:
        for level_id in self.ids:
            player = self.player_name(level_id)
            target = PASS_DIR / level_id
            self._write(target, self.flags[level_id].encode() + b"\n", player, 0o400)
            self._set_password(player, self.flags[level_id])

    @staticmethod
    def player_name(level_id: str) -> str:
        return f"player{level_id}"

    def _apply_level(self, level: Level) -> None:
        context = build_context(level, self.flag_for)

        for spec in level.dirs:
            self._ensure_dir(Path(spec.path), spec.owner, spec.mode)

        for spec in level.files:
            if not applies(spec.when):
                continue
            target = Path(spec.path)
            parent = target.parent
            # Never change the ownership of an existing system directory
            # (e.g. /usr/local/bin). Only create missing intermediate dirs.
            if not parent.exists():
                self._ensure_dir(parent, level.user, 0o750)
            data = self._load_payload(level, spec, context)
            self._write(target, data, spec.owner, spec.mode)

        for archive in level.archives:
            target = Path(archive.path)
            if not target.parent.exists():
                self._ensure_dir(target.parent, level.user, 0o750)
            data = self._build_archive(level, archive.members, archive.fmt, context, archive.path)
            self._write(target, data, archive.owner, archive.mode)

        for acl in level.acls:
            if acl.when == "suid-disabled" and not suid_disabled():
                continue
            self._apply_acl(Path(acl.path), acl.user, acl.perms)

        for capture in level.pcaps:
            target = Path(capture.path)
            if not target.parent.exists():
                self._ensure_dir(target.parent, level.user, 0o750)
            seal = render(capture.seal, context, where=f"{level.id}:{capture.path}")
            data = pcap_builder.build_capture(capture.host, seal)
            self._write(target, data, capture.owner, capture.mode)

        for index, spec in enumerate(level.cron):
            if not applies(spec.when):
                continue
            content = (
                "# generated by wargame — do not edit manually\n"
                f"{spec.schedule} {spec.user} {spec.command}\n"
            )
            self._write(CRON_DIR / f"wargame-{level.id}-{index}", content.encode(), "root", 0o644)

    def _load_payload(self, level: Level, spec, context: dict[str, str]) -> bytes:
        if spec.source:
            source = Path(spec.source)
            if not source.is_file():
                if self.dry_run:
                    # Binary blobs exist only inside the built image.
                    return b""
                raise ProvisionError(f"{level.id}: source not found: {source}")
            return self._pad(level, spec, source.read_bytes())
        if spec.content is not None:
            text = spec.content
        else:
            text = (level.root / spec.template).read_text(encoding="utf-8")
        try:
            data = render(text, context, where=f"{level.id}:{spec.path}").encode("utf-8")
        except LevelError as exc:
            raise ProvisionError(str(exc)) from exc
        return self._pad(level, spec, self._encode(spec, data))

    def _build_archive(
        self,
        level: Level,
        members,
        fmt: str,
        context: dict[str, str],
        where: str,
    ) -> bytes:
        """Build a deterministic tar archive (mtime=0, sorted members)."""
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for member in sorted(members, key=lambda m: m.name):
                if member.members:
                    assert member.fmt is not None
                    data = self._build_archive(
                        level, member.members, member.fmt, context, f"{where}:{member.name}"
                    )
                elif member.content is not None:
                    data = self._render_bytes(level, member.content, context, where)
                else:
                    path = level.root / str(member.template)
                    data = self._render_bytes(
                        level, path.read_text(encoding="utf-8"), context, where
                    )
                info = tarfile.TarInfo(member.name)
                info.size = len(data)
                info.mtime = 0
                info.mode = 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(data))
        payload = raw.getvalue()
        if fmt == "tar":
            return payload
        if fmt == "tar.gz":
            return gzip.compress(payload, 9, mtime=0)
        if fmt == "tar.bz2":
            return bz2.compress(payload, 9)
        return lzma.compress(payload)

    def _apply_acl(self, path: Path, user: str, perms: str) -> None:
        """Apply a POSIX ACL entry. Not affected by `no_new_privs`."""
        if self.dry_run:
            self.log(f"acl {self._display(path)} u:{user}:{perms}")
            return
        if not path.exists():
            raise ProvisionError(f"acl: file not found: {path}")
        self._run(["setfacl", "-m", f"u:{user}:{perms}", str(path)])
        self.log(f"acl {self._display(path)} u:{user}:{perms}")

    @staticmethod
    def _encode(spec, data: bytes) -> bytes:
        """`encoding: xor` obfuscates bytes with 0x5A (obfuscation ≠ encryption)."""
        if spec.encoding == "xor":
            return bytes(byte ^ 0x5A for byte in data)
        return data

    @staticmethod
    def _render_bytes(level: Level, text: str, context: dict[str, str], where: str) -> bytes:
        try:
            return render(text, context, where=where).encode("utf-8")
        except LevelError as exc:
            raise ProvisionError(str(exc)) from exc

    @staticmethod
    def _pad(level: Level, spec, data: bytes) -> bytes:
        """Pad the file to `pad_to` bytes using newlines."""
        if spec.pad_to is None:
            return data
        if len(data) > spec.pad_to:
            raise ProvisionError(
                f"{level.id}:{spec.path}: content is {len(data)} bytes, "
                f"exceeds pad_to limit of {spec.pad_to}"
            )
        return data.ljust(spec.pad_to, b"\n")

    # -- low-level ---------------------------------------------------------

    def _ensure_group(self, name: str, gid: int) -> None:
        if self.dry_run:
            self.log(f"group {name} (gid {gid})")
            return
        assert grp is not None
        try:
            grp.getgrnam(name)
            return
        except KeyError:
            pass
        self._run(["groupadd", "-g", str(gid), name])

    def _ensure_user(self, name: str, uid: int, home: str) -> None:
        assert pwd is not None or self.dry_run
        if not self.dry_run:
            try:
                pwd.getpwnam(name)
                exists = True
            except KeyError:
                exists = False
            if not exists:
                self._run([
                    "useradd", "-M", "-d", home, "-u", str(uid),
                    "-g", name, "-s", "/bin/bash", name,
                ])
        self.log(f"user {name} (uid {uid})")
        self._ensure_dir(Path(home), name, 0o750)
        uid_num, gid_num = self._ids(name)
        if not self.dry_run and uid_num is not None:
            os.chown(home, uid_num, gid_num)

    def _ensure_dir(self, path: Path, owner: str, mode: int) -> None:
        if not self.dry_run:
            path.mkdir(parents=True, exist_ok=True)
            self._chown(path, owner)
            if (path.stat().st_mode & 0o7777) != mode:
                os.chmod(path, mode)
        self.log(f"dir {self._display(path)} {mode:04o} {owner}")

    def _write(self, path: Path, data: bytes, owner: str, mode: int) -> None:
        mode = effective_mode(mode)
        if self.dry_run:
            self.log(f"file {self._display(path)} {mode:04o} {owner} ({len(data)} bytes)")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        unchanged = path.is_file() and path.read_bytes() == data
        if not unchanged:
            path.write_bytes(data)
        # Order is critical: chown clears SUID/SGID bits (even if the owner
        # does not change, when CAP_FSETID is absent). chmod must therefore
        # always run AFTER chown and unconditionally.
        self._chown(path, owner)
        os.chmod(path, mode)
        if unchanged:
            return
        self.log(f"file {self._display(path)} {mode:04o} {owner}")

    def _chown(self, path: Path, owner: str) -> None:
        uid, gid = self._ids(owner)
        if uid is None:
            raise ProvisionError(f"undeclared user: {owner}")
        os.chown(path, uid, gid, follow_symlinks=False)

    def _ids(self, name: str) -> tuple[int | None, int | None]:
        if pwd is None:
            return None, None
        try:
            entry = pwd.getpwnam(name)
        except KeyError:
            return None, None
        gid = entry.pw_gid
        return entry.pw_uid, gid

    def _set_password(self, user: str, password: str) -> None:
        if self.dry_run:
            self.log(f"password {user} (epoch {self.epoch})")
            return
        self._run(["chpasswd"], input_text=f"{user}:{password}\n")
        self.log(f"password {user} (epoch {self.epoch})")

    def _run(self, cmd: list[str], input_text: str | None = None) -> None:
        if self.dry_run:
            self.log("cmd " + " ".join(cmd))
            return
        executable = shutil.which(cmd[0])
        if executable is None:
            raise ProvisionError(f"command not found: {cmd[0]}")
        subprocess.run(
            cmd, check=True, input=input_text, text=True,
            stdout=subprocess.DEVNULL if cmd[0] != "chpasswd" else None,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wargame provision")
    parser.add_argument("--levels", default=str(DEFAULT_LEVELS))
    parser.add_argument("--epoch", default=os.environ.get("WARGAME_EPOCH", "dev"))
    parser.add_argument("--secret")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        levels = load_all(Path(args.levels))
        secret = flaglib.load_secret(args.secret)
    except (LevelError, flaglib.SecretError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    provisioner = Provisioner(levels, secret, args.epoch, dry_run=args.dry_run, quiet=args.quiet)
    try:
        count = provisioner.run()
    except (ProvisionError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"ok: {count} actions, {len(levels)} levels, epoch '{args.epoch}'")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
