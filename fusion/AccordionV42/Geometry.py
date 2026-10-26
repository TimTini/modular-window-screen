"""Pure source geometry witnesses and assembly transforms for V4.2."""

from __future__ import annotations

import math
from typing import Any

import Contract


_MISSING = object()


def _get(values: dict[str, Any], *names: str, default: Any = _MISSING) -> Any:
    """Read the first present canonical/alias key without eager fallback access."""
    for name in names:
        if name in values:
            return values[name]
    if default is not _MISSING:
        return default
    raise KeyError(names[0])


def leaf_outline(values: dict[str, Any]) -> list[tuple[float, float]]:
    """Return the flat panel rectangle from ``leaf()`` in the X/Z plane."""
    pitch = float(_get(values, "pitch_mm", "pitch", default=Contract.PITCH_MM))
    bottom = float(_get(values, "leaf_bottom_mm", "leaf_bottom"))
    top = float(_get(values, "leaf_top_mm", "leaf_top"))
    return [(6.0, bottom), (pitch - 6.0, bottom),
            (pitch - 6.0, top), (6.0, top)]


def pip_void_profile(values: dict[str, Any]) -> list[tuple[float, float]]:
    """Return the radius/X polygon revolved by source ``pip_void()``."""
    gap = float(_get(values, "pip_gap_mm", "pip_gap"))
    rotor_outer = 18.0
    rotor_waist = 10.5
    center = -3.0
    half = rotor_outer - rotor_waist
    groove_start = center - half
    groove_end = center + half
    web_width = float(_get(values, "support_web_width_mm", "support_web_width"))
    exit_x = max(groove_end + 5.1, web_width + 0.1)
    return [
        (0.0, groove_start - 0.1),
        (rotor_outer + gap + 0.1, groove_start - 0.1),
        (rotor_outer + gap, groove_start),
        (rotor_waist + gap, center),
        (rotor_outer + gap, groove_end),
        (rotor_outer + gap, exit_x),
        (0.0, exit_x),
    ]


def rod_placement(
    values: dict[str, Any], index: int
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return ``placed_extension(index)`` origin and intrinsic rotation in degrees."""
    count = int(_get(values, "extension_count"))
    if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= count:
        raise IndexError(f"extension index must be in 0..{count - 1}")
    starts = _get(values, "extension_starts_mm", "extension_starts")
    turns = _get(values, "extension_turns")
    start = float(starts[index])
    turn = float(turns[index])
    height = float(_get(values, "height_mm", "height"))
    return (start, height / 2.0, -30.0), (0.0, 90.0, 360.0 * turn)


def hinge_band_witness(
    values: dict[str, Any], parity: int | None = None
) -> list[dict[str, float | int]]:
    """Return the source ``band_y``/``band_len`` witnesses for the hinge.

    The source places one band every 25 mm, offset by half the 0.3 mm
    clearance.  ``parity`` selects the alternating knuckle set used by a
    moving leaf or an end support; leaving it unset returns both sets.
    """
    if parity is not None and parity not in (0, 1):
        raise ValueError("hinge band parity must be 0 or 1")
    height = float(_get(values, "height_mm", "height"))
    if not math.isfinite(height) or height != 250.0 or height % 25.0 != 0:
        raise ValueError("Height must be a positive multiple of 25 mm and equal 250 mm")
    clearance = float(_get(values, "clearance_mm", "clearance", default=0.3))
    band_count = int(height / 25.0)
    pin_head = 3.0
    pin_neck = 0.5
    bands: list[dict[str, float | int]] = []
    for index in range(band_count):
        band_parity = index % 2
        if parity is not None and band_parity != parity:
            continue
        y = index * 25.0 + clearance / 2.0
        length = min(25.0 - clearance, height - pin_head - pin_neck - y)
        if length > 0:
            bands.append({
                "index": index,
                "parity": band_parity,
                "y_mm": y,
                "length_mm": length,
            })
    return bands
