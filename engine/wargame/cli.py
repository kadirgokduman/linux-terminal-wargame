"""Command-line interface.

    python -m wargame check      levels/        # validate level definitions
    python -m wargame provision  --dry-run      # show what would be applied
    python -m wargame audit                     # leak and permission audit
    python -m wargame flag 03 [--next]          # print a flag value
    python -m wargame login 03                  # print SSH login info
    python -m wargame list                      # level table
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from . import flags as flaglib
from . import stats as stats_mod
from .audit import audit
from .model import LevelError, load_all
from .provision import DEFAULT_LEVELS, Provisioner, ProvisionError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wargame", description="CLI wargame engine")
    parser.add_argument("--version", action="version", version=f"wargame {__version__}")
    parser.add_argument("--levels", default=str(DEFAULT_LEVELS), help="levels directory")
    parser.add_argument("--epoch", default=os.environ.get("WARGAME_EPOCH", "dev"))
    parser.add_argument("--secret", help="base64 secret (default: env / file)")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="validate level definitions")
    sub.add_parser("list", help="list all levels")

    provision = sub.add_parser("provision", help="apply definitions to the filesystem")
    provision.add_argument("--dry-run", action="store_true")
    provision.add_argument("--quiet", action="store_true")

    audit_cmd = sub.add_parser("audit", help="leak and permission audit")
    audit_cmd.add_argument("--quiet", action="store_true")

    flag_cmd = sub.add_parser("flag", help="print a flag value")
    flag_cmd.add_argument("level")
    flag_cmd.add_argument("--next", action="store_true", help="flag for the next level")

    login = sub.add_parser("login", help="print SSH login info")
    login.add_argument("level")

    stats = sub.add_parser("stats", help="summarise the progress log")
    stats.add_argument("--log", default=str(stats_mod.DEFAULT_LOG))
    stats.add_argument("--json", action="store_true", help="machine-readable output")

    return parser


def _load(args) -> list:
    return load_all(Path(args.levels))


def _flag(args, level_id: str) -> str:
    secret = flaglib.load_secret(args.secret)
    return flaglib.derive_flag(secret, level_id, args.epoch)


def cmd_check(args) -> int:
    levels = _load(args)
    width = max(len(lv.title) for lv in levels)
    for level in levels:
        target = f"{level.id} → {level.next_id}"
        print(f"  {level.id}  {level.title:<{width}}  {len(level.files)} files  {target}  {level.slug}")
    print(f"ok: {len(levels)} levels valid")
    return 0


def cmd_list(args) -> int:
    levels = _load(args)
    print(f"{'ID':<4}{'TITLE':<28}{'CONCEPT':<34}{'MIN':>3}")
    for level in levels:
        print(f"{level.id:<4}{level.title:<28}{', '.join(level.concept):<34}{level.estimated_minutes:>3}")
    return 0


def cmd_provision(args) -> int:
    levels = _load(args)
    secret = flaglib.load_secret(args.secret)
    provisioner = Provisioner(levels, secret, args.epoch, dry_run=args.dry_run, quiet=args.quiet)
    count = provisioner.run()
    if not args.quiet:
        print(f"ok: {count} actions, {len(levels)} levels, epoch '{args.epoch}'")
    return 0


def cmd_audit(args) -> int:
    levels = _load(args)
    secret = flaglib.load_secret(args.secret)

    def flag_for(level_id: str) -> str:
        return flaglib.derive_flag(secret, level_id, args.epoch)

    report = audit(levels, flag_for)
    for finding in report.findings:
        print(finding)
    if args.quiet and report.ok:
        return 0
    print(f"audit: {report.scanned_files} files scanned, {len(report.findings)} findings")
    return 0 if report.ok else 1


def cmd_flag(args) -> int:
    level_id = args.level.zfill(2)
    target = f"{int(level_id) + 1:02d}" if args.next else level_id
    print(_flag(args, target))
    return 0


def cmd_stats(args) -> int:
    sessions, skipped = stats_mod.read_log(Path(args.log))
    report = stats_mod.build_report(sessions, skipped)
    print(stats_mod.to_json(report) if args.json else stats_mod.format_report(report))
    return 0


def cmd_login(args) -> int:
    level_id = args.level.zfill(2)
    port = os.environ.get("WARGAME_PORT", "2222")
    host = os.environ.get("WARGAME_HOSTNAME", "localhost")
    print(f"ssh player{level_id}@{host} -p {port}")
    print(f"password: {_flag(args, level_id)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "check": cmd_check,
        "list": cmd_list,
        "provision": cmd_provision,
        "audit": cmd_audit,
        "flag": cmd_flag,
        "login": cmd_login,
        "stats": cmd_stats,
    }
    try:
        return handlers[args.command](args)
    except (LevelError, flaglib.SecretError, ProvisionError, stats_mod.StatsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
