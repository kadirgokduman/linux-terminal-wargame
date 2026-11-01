from __future__ import annotations

import json

import pytest

from wargame.stats import (
    StatsError,
    build_report,
    format_report,
    parse_log,
    read_log,
    to_json,
)

SAMPLE = "\n".join([
    "2026-10-24T20:28:35Z\t00\t172.28.0.1\tssh",
    "2026-10-24T20:29:36Z\t00\t172.28.0.1\tssh",
    "2026-10-24T20:30:10Z\t01\t172.28.0.1\tssh",
    "2026-10-24T20:31:02Z\t2\t10.0.0.9\tssh",       # single digit, gets zero-padded
    "malformed line",
    "2026-10-24T20:32:00Z\t03\thost\tssh\textra",
    "",
])


def test_parse_counts_and_normalizes():
    sessions, skipped = parse_log(SAMPLE)
    assert [item.level for item in sessions] == ["00", "00", "01", "02"]
    assert skipped == 2


def test_parse_sorts_by_time():
    sessions, _ = parse_log(SAMPLE)
    assert sessions == sorted(sessions, key=lambda item: item.when)


def test_report_aggregates_by_level():
    sessions, skipped = parse_log(SAMPLE)
    report = build_report(sessions, skipped)

    assert [stat.level for stat in report.levels] == ["00", "01", "02"]
    assert report.levels[0].sessions == 2
    assert report.levels[0].span_seconds == 61
    assert report.total_sessions == 4
    assert report.highest == "02"
    assert report.hosts == {"172.28.0.1", "10.0.0.9"}


def test_report_handles_empty_log():
    report = build_report([], 0)
    assert report.highest is None
    assert "log is empty" in format_report(report)


def test_format_is_readable():
    sessions, skipped = parse_log(SAMPLE)
    text = format_report(build_report(sessions, skipped))
    assert "Highest level" in text
    assert "player02" in text
    assert "Total sessions  : 4" in text


def test_json_output_is_stable():
    sessions, skipped = parse_log(SAMPLE)
    payload = json.loads(to_json(build_report(sessions, skipped)))
    assert payload["total_sessions"] == 4
    assert payload["levels"][0]["level"] == "00"
    assert payload["levels"][0]["sessions"] == 2
    assert payload["skipped_lines"] == 2


def test_missing_log_is_loud(tmp_path):
    with pytest.raises(StatsError):
        read_log(tmp_path / "missing.log")


def test_read_log_roundtrip(tmp_path):
    path = tmp_path / "progress.log"
    path.write_text(SAMPLE, encoding="utf-8")
    sessions, skipped = read_log(path)
    assert len(sessions) == 4 and skipped == 2


def test_gap_warning_is_reported():
    sessions, _ = parse_log(
        "2026-10-24T20:28:35Z\t00\th\tssh\n"
        "2026-10-24T20:29:00Z\t02\th\tssh\n"
    )
    text = format_report(build_report(sessions))
    assert "level 01 has never been entered" in text
