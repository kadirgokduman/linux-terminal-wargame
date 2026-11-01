"""Deployment policy switches.

`no_new_privileges` and SUID are mutually exclusive: NNP exists precisely
to prevent setuid binaries from gaining privileges. In the hardened profile,
SUID bits are therefore dropped and the affected levels switch to NNP-compatible
fallback mechanisms.
"""

from __future__ import annotations

import os

_FALSEY = {"", "0", "false", "no", "off"}


def suid_disabled() -> bool:
    return os.environ.get("WARGAME_DISABLE_SUID", "0").strip().lower() not in _FALSEY


def effective_mode(mode: int) -> int:
    """Strip SUID/SGID bits according to the current deployment policy."""
    return mode & ~0o6000 if suid_disabled() else mode


def applies(when: str) -> bool:
    """Is the `when` condition active in the current profile?"""
    if when == "always":
        return True
    if when == "suid-disabled":
        return suid_disabled()
    if when == "suid-enabled":
        return not suid_disabled()
    return True
