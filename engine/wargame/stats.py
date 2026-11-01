"""Progress log analysis: `/var/log/wargame/progress.log`.

Log format (written by record-login.sh):

    <ISO-timestamp>\\t<level>\\t<client>\\t<tty>

Each line represents a **successful login**. If a level has a log entry,
its flag has been obtained and used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DEFAULT_LOG = Path("/var/log/wargame/progress.log")
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class StatsError(RuntimeError):
    """Log file could not be read."""


@dataclass(frozen=True)
class Session:
    when: datetime
    level: str
    host: str
    tty: str


@dataclass
class LevelStat:
    level: str
    sessions: int = 0
    first: datetime | None = None
    last: datetime | None = None
    hosts: set[str] = field(default_factory=set)

    def add(self, session: Session) -> None:
        self.sessions += 1
        self.hosts.add(session.host)
        if self.first is None or session.when < self.first:
            self.first = session.when
        if self.last is None or session.when > self.last:
            self.last = session.when

    @property
    def span_seconds(self) -> int:
        if self.first is None or self.last is None:
            return 0
        return int((self.last - self.first).total_seconds())


@dataclass
class Report:
    levels: list[LevelStat]
    total_sessions: int
    hosts: set[str]
    first_seen: datetime | None
    last_seen: datetime | None
    skipped: int

    @property
    def highest(self) -> str | None:
        return self.levels[-1].level if self.levels else None

    def to_dict(self) -> dict:
        return {
            "levels": [
                {
                    "level": stat.level,
                    "sessions": stat.sessions,
                    "first": stat.first.strftime(TS_FORMAT) if stat.first else None,
                    "last": stat.last.strftime(TS_FORMAT) if stat.last else None,
                    "span_seconds": stat.span_seconds,
                    "hosts": sorted(stat.hosts),
                }
                for stat in self.levels
            ],
            "total_sessions": self.total_sessions,
            "hosts": sorted(self.hosts),
            "first_seen": self.first_seen.strftime(TS_FORMAT) if self.first_seen else None,
            "last_seen": self.last_seen.strftime(TS_FORMAT) if self.last_seen else None,
            "skipped_lines": self.skipped,
        }


def parse_log(text: str) -> tuple[list[Session], int]:
    sessions: list[Session] = []
    skipped = 0
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.rstrip("\r").split("\t")
        if len(parts) != 4:
            skipped += 1
            continue
        stamp, level, host, tty = (part.strip() for part in parts)
        if not level.isdigit():
            skipped += 1
            continue
        try:
            when = datetime.strptime(stamp, TS_FORMAT)
        except ValueError:
            skipped += 1
            continue
        sessions.append(Session(when=when, level=level.zfill(2), host=host, tty=tty))
    sessions.sort(key=lambda item: item.when)
    return sessions, skipped


def read_log(path: Path) -> tuple[list[Session], int]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise StatsError(f"log file not found: {path}") from None
    except OSError as exc:
        raise StatsError(f"cannot read log: {path} ({exc})") from exc
    return parse_log(text)


def build_report(sessions: list[Session], skipped: int = 0) -> Report:
    stats: dict[str, LevelStat] = {}
    for session in sessions:
        stats.setdefault(session.level, LevelStat(level=session.level)).add(session)

    ordered = [stats[key] for key in sorted(stats)]
    hosts = {session.host for session in sessions}
    return Report(
        levels=ordered,
        total_sessions=len(sessions),
        hosts=hosts,
        first_seen=sessions[0].when if sessions else None,
        last_seen=sessions[-1].when if sessions else None,
        skipped=skipped,
    )


def _human(seconds: int) -> str:
    """Format a duration as a human-readable string.

    Uses unambiguous abbreviations:
      s  = seconds
      m  = minutes
      h  = hours
    """
    if seconds <= 0:
        return "—"
    if seconds < 60:
        return f"{seconds}s"
    minutes, rest = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {rest}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def format_report(report: Report) -> str:
    if not report.levels:
        return "log is empty: no successful logins recorded yet."

    lines = [
        f"{'LVL':<5}{'SESSIONS':>8}{'FIRST LOGIN':>22}{'LAST LOGIN':>22}{'SPAN':>10}",
        "-" * 67,
    ]
    for stat in report.levels:
        first = stat.first.strftime("%Y-%m-%d %H:%M:%S") if stat.first else "—"
        last = stat.last.strftime("%Y-%m-%d %H:%M:%S") if stat.last else "—"
        lines.append(
            f"{stat.level:<5}{stat.sessions:>8}{first:>22}{last:>22}"
            f"{_human(stat.span_seconds):>10}"
        )

    lines.append("-" * 67)
    highest = report.highest or "—"
    lines.append(f"Highest level   : player{highest}  (flag {highest} used)")
    lines.append(f"Total sessions  : {report.total_sessions}")
    lines.append(f"Unique clients  : {len(report.hosts)}")
    if report.first_seen and report.last_seen:
        span = int((report.last_seen - report.first_seen).total_seconds())
        lines.append(f"Total duration  : {_human(span)}")
    if report.skipped:
        lines.append(f"Skipped lines   : {report.skipped} (malformed / incomplete records)")

    # Detect gaps: find the lowest level that was never entered.
    seen = {stat.level for stat in report.levels}
    for index in range(int(highest) + 1):
        candidate = f"{index:02d}"
        if candidate not in seen:
            lines.append(f"Warning         : level {candidate} has never been entered")
            break

    return "\n".join(lines)


def to_json(report: Report) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
