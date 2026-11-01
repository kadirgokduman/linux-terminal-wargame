from __future__ import annotations

from pathlib import Path

import pytest

from wargame.model import build_context, load_all
from wargame.provision import Provisioner

SECRET = b"\x11" * 32


@pytest.fixture(scope="module")
def levels(levels_dir: Path):
    return load_all(levels_dir)


def test_plan_covers_every_player(levels):
    provisioner = Provisioner(levels, SECRET, "test", dry_run=True, quiet=True)
    expected = {f"{i:02d}" for i in range(len(levels) + 1)}
    assert set(provisioner.flags) == expected
    assert all(len(value) == 20 for value in provisioner.flags.values())


def test_dry_run_produces_actions(levels, capsys):
    provisioner = Provisioner(levels, SECRET, "test", dry_run=True)
    count = provisioner.run()
    assert count > 0
    assert "player00" in capsys.readouterr().out


def test_dry_run_is_quiet(levels, capsys):
    provisioner = Provisioner(levels, SECRET, "test", dry_run=True, quiet=True)
    provisioner.run()
    assert capsys.readouterr().out == ""


def test_epoch_changes_passwords(levels):
    first = Provisioner(levels, SECRET, "2026Q4", dry_run=True, quiet=True)
    second = Provisioner(levels, SECRET, "2027Q1", dry_run=True, quiet=True)
    assert first.flags["01"] != second.flags["01"]


def test_rendered_payloads_are_bytes(levels):
    provisioner = Provisioner(levels, SECRET, "test", dry_run=True, quiet=True)
    level = levels[1]
    context = build_context(level, provisioner.flag_for)
    spec = next(f for f in level.files if f.template)
    payload = provisioner._load_payload(level, spec, context)
    assert isinstance(payload, bytes) and payload
