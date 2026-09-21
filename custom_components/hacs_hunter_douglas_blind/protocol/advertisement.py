"""Decode the unencrypted manufacturer advertisement (docs/PROTOCOL.md §2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Advertisement:
    """Decoded shade state. Percent fields are 0..100."""

    home_id: int
    type_id: int
    primary: float
    secondary: float | None
    tilt: float | None
    velocity: int | None


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def parse_advertisement(payload: bytes) -> Advertisement | None:
    """Parse a manufacturer payload with the 2-byte company ID already stripped.

    Home Assistant's ``BluetoothServiceInfoBleak.manufacturer_data[0x0819]``
    is already in this form. Returns None when the payload is too short.
    """
    if len(payload) < 5:
        return None
    return Advertisement(
        home_id=int.from_bytes(payload[0:2], "little"),
        type_id=payload[2],
        primary=_clamp(int.from_bytes(payload[3:5], "little") / 40.0),
        secondary=(
            _clamp(int.from_bytes(payload[5:7], "little") / 40.0)
            if len(payload) >= 7
            else None
        ),
        tilt=_clamp(float(payload[7])) if len(payload) >= 8 else None,
        velocity=payload[8] if len(payload) >= 9 else None,
    )
