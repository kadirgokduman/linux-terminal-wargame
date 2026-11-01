"""Flag derivation.

Rule: no flag is ever written to the repository. Every flag is derived
deterministically from a single server secret and an epoch tag. When the
epoch changes all flags rotate; a leaked flag's lifetime is bounded by the
epoch boundary.

    flag = base32(HMAC-SHA256(secret, "wargame/v1|<level>|<epoch>"))[:20]

20 base32 characters = 100 bits of entropy. Suitable as an SSH password
(lowercase + digits, unambiguous alphabet) and not brute-forceable.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path

FLAG_LENGTH = 20
DEFAULT_SECRET_FILE = Path("/run/secrets/wargame_secret")
MIN_SECRET_BYTES = 16


class SecretError(RuntimeError):
    """Secret not found or invalid."""


def load_secret(explicit: str | None = None) -> bytes:
    """Load the secret from an environment variable or a file.

    Priority: explicit argument > WARGAME_SECRET (base64 text) >
    WARGAME_SECRET_FILE > /run/secrets/wargame_secret.
    """
    if explicit:
        return _decode(explicit, "argument")

    env_value = os.environ.get("WARGAME_SECRET")
    if env_value:
        return _decode(env_value.strip(), "WARGAME_SECRET")

    path = Path(os.environ.get("WARGAME_SECRET_FILE", DEFAULT_SECRET_FILE))
    if not path.is_file():
        raise SecretError(
            f"secret not found: {path} (generate one with: make secret)"
        )
    return _decode(path.read_text(encoding="utf-8").strip(), str(path))


def _decode(text: str, source: str) -> bytes:
    try:
        raw = base64.b64decode(text, validate=True)
    except ValueError as exc:  # binascii.Error is a subclass
        raise SecretError(f"{source}: not valid base64") from exc
    if len(raw) < MIN_SECRET_BYTES:
        raise SecretError(
            f"{source}: secret must be at least {MIN_SECRET_BYTES} bytes "
            f"(got {len(raw)})"
        )
    return raw


def derive_flag(secret: bytes, level_id: str, epoch: str) -> str:
    """Derive a deterministic flag for a given level and epoch."""
    level_id = str(level_id).zfill(2) if str(level_id).isdigit() else str(level_id)
    message = f"wargame/v1|{level_id}|{epoch}".encode("utf-8")
    digest = hmac.digest(secret, message, hashlib.sha256)
    encoded = base64.b32encode(digest).decode("ascii").rstrip("=")
    return encoded.lower()[:FLAG_LENGTH]


def derive_all(secret: bytes, level_ids: list[str], epoch: str) -> dict[str, str]:
    return {level_id: derive_flag(secret, level_id, epoch) for level_id in level_ids}
