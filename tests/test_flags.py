from __future__ import annotations

import base64

import pytest

from wargame import flags

SECRET = b"\x11" * 32
ALPHABET = set("abcdefghijklmnopqrstuvwxyz234567")


def test_flag_shape():
    value = flags.derive_flag(SECRET, "03", "2026Q4")
    assert len(value) == flags.FLAG_LENGTH
    assert set(value) <= ALPHABET, "SSH parolası olarak yazılabilir olmalı"


def test_flag_is_deterministic():
    assert flags.derive_flag(SECRET, "03", "2026Q4") == flags.derive_flag(SECRET, "03", "2026Q4")


def test_flag_depends_on_level():
    assert flags.derive_flag(SECRET, "03", "e") != flags.derive_flag(SECRET, "04", "e")


def test_flag_depends_on_epoch():
    old = flags.derive_flag(SECRET, "03", "2026Q4")
    new = flags.derive_flag(SECRET, "03", "2027Q1")
    assert old != new, "dönem değişince eski parolalar geçersiz olmalı"


def test_flag_depends_on_secret():
    other = b"\x22" * 32
    assert flags.derive_flag(SECRET, "03", "e") != flags.derive_flag(other, "03", "e")


def test_flag_has_100_bits():
    # 20 base32 karakteri = 100 bit; kaba kuvvetle bulunamaz.
    assert flags.FLAG_LENGTH * 5 >= 100


def test_many_flags_are_unique():
    values = {flags.derive_flag(SECRET, f"{i:02d}", "e") for i in range(64)}
    assert len(values) == 64


def test_load_secret_from_env(monkeypatch):
    encoded = base64.b64encode(SECRET).decode()
    monkeypatch.setenv("WARGAME_SECRET", encoded)
    assert flags.load_secret() == SECRET


def test_load_secret_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("WARGAME_SECRET", raising=False)
    path = tmp_path / "secret"
    path.write_text(base64.b64encode(SECRET).decode())
    monkeypatch.setenv("WARGAME_SECRET_FILE", str(path))
    assert flags.load_secret() == SECRET


def test_missing_secret_is_loud(tmp_path, monkeypatch):
    monkeypatch.delenv("WARGAME_SECRET", raising=False)
    monkeypatch.setenv("WARGAME_SECRET_FILE", str(tmp_path / "yok"))
    with pytest.raises(flags.SecretError):
        flags.load_secret()


def test_short_secret_is_rejected():
    with pytest.raises(flags.SecretError):
        flags.load_secret(base64.b64encode(b"kisa").decode())


def test_invalid_base64_is_rejected():
    with pytest.raises(flags.SecretError):
        flags.load_secret("bu base64 değil!")
