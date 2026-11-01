from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

SECRET = b"\x11" * 32
EPOCH = "test"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def levels_dir(repo_root: Path) -> Path:
    return repo_root / "levels"


@pytest.fixture(scope="session")
def secret() -> bytes:
    return SECRET
