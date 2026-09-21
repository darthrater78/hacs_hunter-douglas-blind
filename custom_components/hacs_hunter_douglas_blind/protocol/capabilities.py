"""typeId -> capability lookup (docs/PROTOCOL.md §5, from the framework's Capabilities.kt)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    id: int
    name: str
    primary: bool
    secondary: bool
    tilt: bool
    tilt_range_degrees: int | None = None
    primary_inverted: bool = False
    overlapped: bool = False


_CAPS = [
    Capability(0, "bottom_up", True, False, False),
    Capability(1, "bottom_up_tilt_90", True, False, True, 90),
    Capability(2, "bottom_up_tilt_180", True, False, True, 180),
    Capability(3, "vertical", True, False, False),
    Capability(4, "vertical_tilt_180", True, False, True, 180),
    Capability(5, "tilt_only", False, False, True, 180),
    Capability(6, "top_down", True, False, False, primary_inverted=True),
    Capability(7, "top_down_bottom_up", True, True, False),
    Capability(8, "dual_overlapped", True, True, False, overlapped=True),
    Capability(9, "dual_overlapped_tilt_90", True, True, True, 90, overlapped=True),
    Capability(10, "dual_overlapped_tilt_180", True, True, True, 180, overlapped=True),
]
CAPABILITIES = {c.id: c for c in _CAPS}

_TYPE_TO_CAPABILITY = {
    1: 0, 4: 0, 6: 0, 7: 6, 8: 7, 18: 1, 23: 1, 31: 0, 32: 0, 33: 7, 38: 9,
    39: 5, 40: 5, 43: 1, 44: 1, 49: 0, 51: 2, 52: 0, 53: 0, 54: 4, 55: 4,
    56: 4, 62: 2, 65: 8, 66: 5, 69: 3, 70: 3, 71: 3, 79: 8, 84: 0, 95: 8,
}


def capability_for_type(type_id: int) -> tuple[Capability, bool]:
    """Return (capability, is_known_type). Unknown types fall back to bottom-up."""
    cap_id = _TYPE_TO_CAPABILITY.get(type_id)
    if cap_id is None:
        return CAPABILITIES[0], False
    return CAPABILITIES[cap_id], True
