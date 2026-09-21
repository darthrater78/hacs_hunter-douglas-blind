"""Build the 13-byte plaintext command frame (docs/PROTOCOL.md §3)."""

from __future__ import annotations

_UNSET = b"\x00\x80"


def _position(percent: float | None) -> bytes:
    if percent is None:
        return _UNSET
    if not 0 <= percent <= 100:
        raise ValueError("percent must be within 0..100")
    return round(percent * 100).to_bytes(2, "little")


def build_command_frame(
    sequence: int,
    primary: float | None = None,
    secondary: float | None = None,
    tilt: float | None = None,
) -> bytes:
    """Return the plaintext frame. Encryption (keystream XOR) is not done here.

    Writes scale percent x 100; reads scale raw / 40 -- the asymmetry is real.
    """
    if not 0 <= sequence <= 0xFF:
        raise ValueError("sequence must fit in one byte")
    if tilt is not None and not 0 <= tilt <= 100:
        raise ValueError("tilt must be within 0..100")
    return (
        b"\xf7\x01"
        + bytes([sequence])
        + b"\x09"
        + _position(primary)
        + _position(secondary)
        + _UNSET  # reserved, always unset
        + (bytes([round(tilt), 0x00]) if tilt is not None else b"\x00\x80")
        + b"\x00"
    )
