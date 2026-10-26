"""Source-faithful, Fusion-independent contract for Accordion V4.2.

All values in this module remain in source millimetres (or degrees for phase
and joint angle).  Conversion to Fusion's centimetre/radian API belongs at the
native builder boundary.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any


# These hashes describe the self-contained inputs in ``reference/``.  The
# project-root SCAD is a later revision and is not silently substituted.
SOURCE_HASHES = {
    "accordion.scad": "8f80b5382d7d36d020df508ff3d02a9bda6ee88b1fd4fec9c36ce78a013d3a57",
    "threads.scad": "42435bb118dba9e9c5e102dfdd417187ab1366b9dfcbcc6b49b694e7a38b3da2",
}
REFERENCE_STL_SHA256 = "820485a4f9a147d9425e106d44faefb213f56c3d8eeb758a150e6e69cb247ee1"

HEIGHT_MM = 250.0
PITCH_MM = 42.0
HINGE_BORE_R_MM = 2.3
HINGE_OUTER_R_MM = 4.6
HINGE_MIN_WALL_MM = 2.0
CLEARANCE_MM = 0.3
SOCKET_DEPTH_MM = 25.0
TIP_THREAD_MM = 110.0
MAX_EXTENSION_LENGTH_MM = 230.0
MAX_MALE_LENGTH_MM = 240.0
PHASE_TOLERANCE = 1e-6

THREAD_PITCH_MM = 4.0
THREAD_INCLUDED_ANGLE_DEG = 30.0
MALE_MINOR_D_MM = 15.287
MALE_PITCH_D_MM = 17.7725
MALE_MAJOR_D_MM = 19.85
FEMALE_MINOR_D_MM = 16.1875
FEMALE_PITCH_D_MM = 18.1775
FEMALE_MAJOR_D_MM = 20.5
FEMALE_OD_R_MM = 14.0


def _require_finite(values: dict[str, Any], names: tuple[str, ...]) -> None:
    for name in names:
        if name not in values:
            raise ValueError(f"Missing source parameter: {name}")
        value = values[name]
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
            raise ValueError(f"Source parameter {name} must be finite")


def _value(values: dict[str, Any], name: str, alias: str | None = None) -> float:
    value = values[name] if name in values else values[alias] if alias else None
    if value is None:
        raise ValueError(f"Missing source parameter: {name}")
    return float(value)


def _populate_derived(values: dict[str, Any]) -> None:
    width = _value(values, "width_mm", "width")
    clamp = _value(values, "clamp_travel_mm", "clamp_travel")
    leaf_bottom = _value(values, "leaf_bottom_mm", "leaf_bottom")
    leaf_top = _value(values, "leaf_top_mm", "leaf_top")
    support_web = _value(values, "support_web_width_mm", "support_web_width")
    pip_gap = _value(values, "pip_gap_mm", "pip_gap")
    offset = _value(values, "thread_offset_mm", "thread_offset")
    bore = _value(values, "male_bore_d_mm", "male_bore_d")
    joint_angle = _value(values, "joint_angle_deg", "joint_angle")

    assembly_span = width - clamp
    leaf_count = 2 * math.ceil((width - 20.0) / (2.0 * (PITCH_MM - 2.0)))
    pin_count = leaf_count + 1
    extension_count = max(
        1,
        math.ceil((width - 120.0 - MAX_MALE_LENGTH_MM)
                  / (MAX_EXTENSION_LENGTH_MM - SOCKET_DEPTH_MM)),
    )
    male_length = max(
        175.0,
        width - 120.0 - extension_count
        * (MAX_EXTENSION_LENGTH_MM - SOCKET_DEPTH_MM),
    )
    extension_length = SOCKET_DEPTH_MM + (width - 120.0 - male_length) / extension_count
    shank = extension_length - TIP_THREAD_MM
    extension_starts = [
        10.0 + male_length - SOCKET_DEPTH_MM
        + i * (extension_length - SOCKET_DEPTH_MM)
        for i in range(extension_count)
    ]
    extension_turns = [
        (start - 10.0 - i * shank) / THREAD_PITCH_MM
        for i, start in enumerate(extension_starts)
    ]
    extension_phase_degrees = [360.0 * turn for turn in extension_turns]
    tip_start = extension_starts[-1] + shank
    male_tip = extension_starts[-1] + extension_length
    final_female_turn = ((width - 140.0) - 10.0 - extension_count * shank) / THREAD_PITCH_MM
    final_female_phase = 360.0 * (final_female_turn - clamp / THREAD_PITCH_MM) + joint_angle
    rotor_thread_start = assembly_span - 140.0
    dx = (assembly_span - 20.0) / leaf_count
    dz = math.sqrt(PITCH_MM * PITCH_MM - dx * dx)
    tip_overlap = male_tip - (width - 140.0)
    shoulder_clearance = (width - 140.0) - tip_start
    actual_female_engagement = tip_overlap + clamp
    actual_shoulder_gap = shoulder_clearance - clamp

    rod_shaft_start = shank - 20.0 - 3.0
    rod_shaft_length = TIP_THREAD_MM + 20.0 + 3.0
    rod_joint_phase = -360.0 * (20.0 + 3.0) / THREAD_PITCH_MM
    rod_socket_length = shank - 3.0
    rod_socket_bed = FEMALE_MAJOR_D_MM / 2.0 - offset + 2.0
    socket_max_r = 10.5 + 8.0 / 2.0 + pip_gap
    right_axis_z = socket_max_r + 2.0 + 0.2
    right_print_lift = 30.0 + right_axis_z

    values.update({
        "width_mm": width,
        "width": width,
        "height_mm": HEIGHT_MM,
        "height": HEIGHT_MM,
        "clamp_travel_mm": clamp,
        "clamp_travel": clamp,
        "thread_offset_mm": offset,
        "thread_offset": offset,
        "pip_gap_mm": pip_gap,
        "pip_gap": pip_gap,
        "male_bore_d_mm": bore,
        "male_bore_d": bore,
        "leaf_bottom_mm": leaf_bottom,
        "leaf_bottom": leaf_bottom,
        "leaf_top_mm": leaf_top,
        "leaf_top": leaf_top,
        "support_web_width_mm": support_web,
        "support_web_width": support_web,
        "joint_angle_deg": joint_angle,
        "joint_angle": joint_angle,
        "assembly_span_mm": assembly_span,
        "assembly_span": assembly_span,
        "leaf_count": leaf_count,
        "pin_count": pin_count,
        "extension_count": extension_count,
        "physical_part_count": leaf_count + pin_count + 3 + 2 * extension_count,
        "pitch_mm": PITCH_MM,
        "socket_depth_mm": SOCKET_DEPTH_MM,
        "tip_thread_mm": TIP_THREAD_MM,
        "hinge_bore_r_mm": HINGE_BORE_R_MM,
        "hinge_outer_r_mm": HINGE_OUTER_R_MM,
        "leaf_thickness_mm": leaf_top - leaf_bottom,
        "leaf_thickness": leaf_top - leaf_bottom,
        "male_length_mm": male_length,
        "male_length": male_length,
        "extension_length_mm": extension_length,
        "extension_length": extension_length,
        "shank_mm": shank,
        "shank": shank,
        "extension_starts_mm": extension_starts,
        "extension_starts": extension_starts,
        "extension_turns": extension_turns,
        "extension_phase_degrees": extension_phase_degrees,
        "tip_start_mm": tip_start,
        "male_tip_mm": male_tip,
        "final_female_turns": final_female_turn,
        "final_female_turn": final_female_turn,
        "final_female_phase_deg": final_female_phase,
        "rotor_thread_start_mm": rotor_thread_start,
        "dx_mm": dx,
        "dx": dx,
        "dz_mm": dz,
        "dz": dz,
        "tip_overlap_mm": tip_overlap,
        "shoulder_clearance_mm": shoulder_clearance,
        "actual_female_engagement_mm": actual_female_engagement,
        "actual_shoulder_gap_mm": actual_shoulder_gap,
        "rod_socket_length_mm": rod_socket_length,
        "rod_socket_length": rod_socket_length,
        "rod_shaft_start_mm": rod_shaft_start,
        "rod_shaft_start": rod_shaft_start,
        "rod_shaft_length_mm": rod_shaft_length,
        "rod_shaft_length": rod_shaft_length,
        "rod_joint_phase_deg": rod_joint_phase,
        "rod_socket_bed_mm": rod_socket_bed,
        "thread_segment_count": 2 + 4 * extension_count,
        "modeled_thread_feature_count": 2 + 4 * extension_count,
        "socket_max_r_mm": socket_max_r,
        "right_axis_z_mm": right_axis_z,
        "right_print_lift_mm": right_print_lift,
        "source_hashes": dict(SOURCE_HASHES),
        "reference_stl_sha256": REFERENCE_STL_SHA256,
    })


def derive(
    width_mm: float,
    clamp_travel_mm: float = 0,
    thread_offset_mm: float = -0.25,
    pip_gap_mm: float = 0.6,
    male_bore_d_mm: float = 2,
    leaf_bottom_mm: float = -4.5,
    leaf_top_mm: float = 4.5,
    support_web_width_mm: float = 10,
    joint_angle_deg: float = 0,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "width_mm": width_mm,
        "clamp_travel_mm": clamp_travel_mm,
        "thread_offset_mm": thread_offset_mm,
        "pip_gap_mm": pip_gap_mm,
        "male_bore_d_mm": male_bore_d_mm,
        "leaf_bottom_mm": leaf_bottom_mm,
        "leaf_top_mm": leaf_top_mm,
        "support_web_width_mm": support_web_width_mm,
        "joint_angle_deg": joint_angle_deg,
    }
    _populate_derived(values)
    validate(values)
    return values


def validate(values: dict[str, Any]) -> None:
    """Validate source assertions and derived geometry, raising ``ValueError``."""
    names = (
        "width_mm", "clamp_travel_mm", "thread_offset_mm", "pip_gap_mm",
        "male_bore_d_mm", "leaf_bottom_mm", "leaf_top_mm",
        "support_web_width_mm", "joint_angle_deg",
    )
    _require_finite(values, names)
    width = _value(values, "width_mm", "width")
    clamp = _value(values, "clamp_travel_mm", "clamp_travel")
    offset = _value(values, "thread_offset_mm", "thread_offset")
    pip_gap = _value(values, "pip_gap_mm", "pip_gap")
    bore = _value(values, "male_bore_d_mm", "male_bore_d")
    leaf_bottom = _value(values, "leaf_bottom_mm", "leaf_bottom")
    leaf_top = _value(values, "leaf_top_mm", "leaf_top")
    support_web = _value(values, "support_web_width_mm", "support_web_width")

    if not 430.0 <= width <= 1000.0:
        raise ValueError("W must be 430..1000 mm")
    if not 0.0 <= clamp <= 75.0:
        raise ValueError("Clamp travel must be 0..75 mm")
    if not -0.4 <= offset <= -0.1:
        raise ValueError("thread_offset must be -0.4..-0.1 mm")
    if not 0.4 <= pip_gap <= 0.9:
        raise ValueError("PIP radial gap must be 0.4..0.9 mm")
    if bore <= 0:
        raise ValueError("Male axial bore diameter must be positive")
    if support_web < 10.0:
        raise ValueError("Support web must reach the end plate")
    if min(leaf_top, -leaf_bottom,
           HINGE_OUTER_R_MM * math.cos(math.radians(180.0 / 48.0))) - HINGE_BORE_R_MM < HINGE_MIN_WALL_MM:
        raise ValueError("Hinge wall contract must be at least 2 mm")

    if "source_hashes" in values:
        supplied = values["source_hashes"]
        for name, expected in SOURCE_HASHES.items():
            if supplied.get(name) != expected:
                raise ValueError(f"{name} source hash mismatch")
    if "reference_stl_sha256" in values and values["reference_stl_sha256"] != REFERENCE_STL_SHA256:
        raise ValueError("Reference STL hash mismatch")

    # Recompute the complete downstream state from the nine Run inputs. A
    # builder must never consume stale or hand-edited counts, placements,
    # phases, inventory, or physical-count values supplied in this dictionary.
    expected = expected_from_inputs(values, include_hashes=False)
    _populate_derived(expected)
    derived_fields = (
        "height_mm", "height", "pitch_mm", "assembly_span_mm", "assembly_span",
        "leaf_count", "pin_count", "extension_count", "physical_part_count",
        "leaf_thickness_mm", "leaf_thickness", "male_length_mm", "male_length",
        "extension_length_mm", "extension_length", "shank_mm", "shank",
        "extension_starts_mm", "extension_starts", "extension_turns",
        "extension_phase_degrees", "tip_start_mm", "male_tip_mm",
        "final_female_turns", "final_female_turn", "final_female_phase_deg",
        "rotor_thread_start_mm", "dx_mm", "dx", "dz_mm", "dz",
        "tip_overlap_mm", "shoulder_clearance_mm", "actual_female_engagement_mm",
        "actual_shoulder_gap_mm", "rod_socket_length_mm", "rod_socket_length",
        "rod_shaft_start_mm", "rod_shaft_start", "rod_shaft_length_mm",
        "rod_shaft_length", "rod_joint_phase_deg", "rod_socket_bed_mm",
        "socket_max_r_mm", "right_axis_z_mm", "right_print_lift_mm",
        "thread_segment_count",
        "modeled_thread_feature_count",
    )
    for name in derived_fields:
        if name not in values:
            raise ValueError(f"Missing derived source value: {name}")
        actual = values[name]
        canonical = expected[name]
        if isinstance(canonical, list):
            if not isinstance(actual, list) or len(actual) != len(canonical):
                raise ValueError(f"Derived source value drift: {name}")
            matches = all(math.isclose(float(left), float(right), abs_tol=1e-9)
                          for left, right in zip(actual, canonical))
        elif isinstance(canonical, Real):
            matches = math.isclose(float(actual), float(canonical), abs_tol=1e-9)
        else:
            matches = actual == canonical
        if not matches:
            raise ValueError(f"Derived source value drift: {name}")

    leaf_count = int(2 * math.ceil((width - 20.0) / (2.0 * (PITCH_MM - 2.0))))
    extension_count = max(1, math.ceil((width - 120.0 - MAX_MALE_LENGTH_MM)
                                       / (MAX_EXTENSION_LENGTH_MM - SOCKET_DEPTH_MM)))
    male_length = max(175.0, width - 120.0 - extension_count
                      * (MAX_EXTENSION_LENGTH_MM - SOCKET_DEPTH_MM))
    extension_length = SOCKET_DEPTH_MM + (width - 120.0 - male_length) / extension_count
    shank = extension_length - TIP_THREAD_MM
    starts = [10.0 + male_length - SOCKET_DEPTH_MM
              + i * (extension_length - SOCKET_DEPTH_MM)
              for i in range(extension_count)]
    turns = [(start - 10.0 - i * shank) / THREAD_PITCH_MM
             for i, start in enumerate(starts)]
    tip_start = starts[-1] + shank
    male_tip = starts[-1] + extension_length
    final_turn = ((width - 140.0) - 10.0 - extension_count * shank) / THREAD_PITCH_MM
    dx = (width - clamp - 20.0) / leaf_count
    if not dx < PITCH_MM:
        raise ValueError("Leaves cannot reach a straight line inside this width range")
    if not 160.0 <= extension_length <= MAX_EXTENSION_LENGTH_MM:
        raise ValueError("Extension length must be 160..230 mm")
    if not 175.0 <= male_length <= MAX_MALE_LENGTH_MM:
        raise ValueError("Male length must be 175..240 mm")
    if shank < SOCKET_DEPTH_MM + 25.0:
        raise ValueError("Extension shank must leave a 25 mm reserve")
    if extension_length > 250.0 or male_length + 10.0 > 250.0:
        raise ValueError("Rod pieces must fit the 250 mm bed")
    tip_overlap = male_tip - (width - 140.0)
    shoulder_clearance = (width - 140.0) - tip_start
    if abs(tip_overlap - 30.0) >= PHASE_TOLERANCE:
        raise ValueError("Last male engagement must be 30 mm")
    if shoulder_clearance < 80.0 - PHASE_TOLERANCE:
        raise ValueError("Terminal shoulder clearance must be at least 80 mm")
    if tip_overlap + clamp > 118.0 + PHASE_TOLERANCE:
        raise ValueError("Actual female engagement must be at most 118 mm")
    if shoulder_clearance - clamp < 5.0 - PHASE_TOLERANCE:
        raise ValueError("Actual shoulder gap must be at least 5 mm")
    if any(abs((starts[i + 1] - starts[i]) - (extension_length - SOCKET_DEPTH_MM))
           >= PHASE_TOLERANCE for i in range(extension_count - 1)):
        raise ValueError("Adjacent extension sockets must overlap by 25 mm")
    if any(abs((turns[i + 1] - turns[i]) - 21.25) >= PHASE_TOLERANCE
           for i in range(extension_count - 1)):
        raise ValueError("Adjacent extension phase step must be 21.25 turns")
    if abs(final_turn - turns[-1] - 20.0) >= PHASE_TOLERANCE:
        raise ValueError("Final female phase must be 20 turns after the last extension")

    socket_max_r = 10.5 + 4.0 + pip_gap
    if 20.0 * math.cos(math.radians(180.0 / 48.0)) - socket_max_r < 2.0:
        raise ValueError("Ring radial wall below 2 mm")
    if 18.0 <= socket_max_r + 2.0 + 0.2:
        raise ValueError("Rotor body must meet the bed")
    male_core_r = MALE_MINOR_D_MM / 2.0 + offset
    if male_core_r - bore / 2.0 <= 2.0:
        raise ValueError("Male thread core wall around the axial bore must exceed 2 mm")
    if 7.0 - bore / 2.0 <= 2.0:
        raise ValueError("Rod shaft flat-bed wall around the axial bore must exceed 2 mm")
    if 7.0 >= male_core_r:
        raise ValueError("Rod shaft bed cut must reach the core")
    if (FEMALE_MAJOR_D_MM / 2.0 - offset + 2.0) - (FEMALE_MAJOR_D_MM / 2.0 - offset) < 2.0:
        raise ValueError("Rod socket wall must remain at least 2 mm")


def expected_from_inputs(values: dict[str, Any], include_hashes: bool = True) -> dict[str, Any]:
    """Make the minimal input dictionary used for internal drift checks."""
    result = {
        "width_mm": _value(values, "width_mm", "width"),
        "clamp_travel_mm": _value(values, "clamp_travel_mm", "clamp_travel"),
        "thread_offset_mm": _value(values, "thread_offset_mm", "thread_offset"),
        "pip_gap_mm": _value(values, "pip_gap_mm", "pip_gap"),
        "male_bore_d_mm": _value(values, "male_bore_d_mm", "male_bore_d"),
        "leaf_bottom_mm": _value(values, "leaf_bottom_mm", "leaf_bottom"),
        "leaf_top_mm": _value(values, "leaf_top_mm", "leaf_top"),
        "support_web_width_mm": _value(values, "support_web_width_mm", "support_web_width"),
        "joint_angle_deg": _value(values, "joint_angle_deg", "joint_angle"),
    }
    if include_hashes and "source_hashes" in values:
        result["source_hashes"] = dict(values["source_hashes"])
    return result


def thread_segments(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the source's modeled TR20x4 segment inventory in millimetres."""
    validate(values)
    ext_count = int(values["extension_count"])
    segments: list[dict[str, Any]] = [
        {"part": "left_support", "role": "left_male", "internal": False,
         "length_mm": values["male_length_mm"], "length": values["male_length_mm"],
         "start_mm": 10.0, "start": 10.0, "phase_deg": 0.0, "phase": 0.0,
         "local_start_mm": 0.0, "local_phase_deg": 0.0,
         "bore_d_mm": values["male_bore_d_mm"]},
        {"part": "female_rotor", "role": "rotor_female", "internal": True,
         "length_mm": 118.0, "length": 118.0,
         "start_mm": values["rotor_thread_start_mm"], "start": values["rotor_thread_start_mm"],
         "phase_deg": values["final_female_phase_deg"], "phase": values["final_female_phase_deg"],
         "local_start_mm": -130.0, "local_phase_deg": 0.0, "bore_d_mm": None},
    ]
    for index in range(ext_count):
        extension_start = values["extension_starts_mm"][index]
        extension_phase = values["extension_phase_degrees"][index]
        phase = extension_phase + values["rod_joint_phase_deg"]
        start = extension_start + values["rod_shaft_start_mm"]
        segments.extend((
            {"part": "rod_socket", "role": f"socket_front_female_{index}", "internal": True,
             "length_mm": SOCKET_DEPTH_MM, "length": SOCKET_DEPTH_MM,
             "start_mm": extension_start, "start": extension_start,
             "phase_deg": extension_phase, "phase": extension_phase,
             "local_start_mm": 0.0, "local_phase_deg": 0.0,
             "bore_d_mm": None},
            {"part": "rod_socket", "role": f"socket_rear_female_{index}", "internal": True,
             "length_mm": 20.0, "length": 20.0, "start_mm": start, "start": start,
             "phase_deg": phase, "phase": phase,
             "local_start_mm": values["rod_shaft_start_mm"],
             "local_phase_deg": values["rod_joint_phase_deg"], "bore_d_mm": None},
            {"part": "rod_shaft", "role": f"shaft_joint_male_{index}", "internal": False,
             "length_mm": 23.0, "length": 23.0, "start_mm": start, "start": start,
             "phase_deg": phase, "phase": phase,
             "local_start_mm": values["rod_shaft_start_mm"],
             "local_phase_deg": values["rod_joint_phase_deg"],
             "bore_d_mm": values["male_bore_d_mm"]},
            {"part": "rod_shaft", "role": f"shaft_tip_male_{index}", "internal": False,
             "length_mm": TIP_THREAD_MM, "length": TIP_THREAD_MM,
             "start_mm": extension_start + values["shank_mm"],
             "start": extension_start + values["shank_mm"],
             "phase_deg": extension_phase, "phase": extension_phase,
             "local_start_mm": values["shank_mm"], "local_phase_deg": 0.0,
             "bore_d_mm": values["male_bore_d_mm"]},
        ))
    return segments


def assembly_instances(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the separately printed instances in the source assembly.

    Coordinates are source millimetres.  ``origin_mm`` is the translation at
    the outside of each ``placed_*`` module.  ``rotation_deg`` is the source
    XYZ Euler vector.  ``rotation_ops`` preserves the source textual order
    from outer rotate to inner rotate, so the rod rows explicitly retain
    ``Y+90`` followed by their local Z phase.  The female rotor additionally
    exposes ``pivot_mm`` and ``pivot_rotation_deg`` for its translate, rotate,
    inverse-translate sequence.
    """
    validate(values)

    def row(name: str, part_type: str, index: int, origin: tuple[float, float, float],
            rotation: tuple[float, float, float], module: str,
            rotation_ops: tuple[tuple[str, float], ...] = (), **extra: Any) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": name,
            "part": part_type,
            "part_type": part_type,
            "index": index,
            "module": module,
            "origin_mm": origin,
            "source_origin_mm": origin,
            "rotation_deg": rotation,
            "source_rotation_deg": rotation,
            "rotation_ops": rotation_ops,
            "rotation_order": tuple(axis for axis, _ in rotation_ops),
        }
        result.update(extra)
        return result

    instances: list[dict[str, Any]] = []
    dx = float(values["dx_mm"])
    dz = float(values["dz_mm"])
    for index in range(int(values["leaf_count"])):
        z = dz if index % 2 else 0.0
        slope = (1.0 if index % 2 == 0 else -1.0) * math.degrees(math.atan2(dz, dx))
        origin = (10.0 + index * dx, 0.0, z)
        instances.append(row(
            f"leaf-{index:02d}", "leaf", index, origin, (0.0, -slope, 0.0),
            "placed_leaf", (("y", -slope),), source_slope_deg=slope,
        ))

    for index in range(int(values["pin_count"])):
        z = dz if index % 2 else 0.0
        origin = (10.0 + index * dx, 0.0, z)
        instances.append(row(
            f"pin-{index:02d}", "pin", index, origin, (-90.0, 0.0, 0.0),
            "placed_pin", (("x", -90.0),),
        ))

    instances.append(row(
        "left-support", "left_support", 0, (10.0, 0.0, 0.0), (0.0, 0.0, 0.0),
        "placed_left",
    ))

    for index, (start, phase) in enumerate(zip(
        values["extension_starts_mm"], values["extension_phase_degrees"]
    )):
        origin = (float(start), HEIGHT_MM / 2.0, -30.0)
        ops = (("y", 90.0), ("z", float(phase)))
        for part_type in ("rod_socket", "rod_shaft"):
            instances.append(row(
                f"rod-{index:02d}-{'socket' if part_type == 'rod_socket' else 'shaft'}",
                part_type, index, origin, (0.0, 90.0, float(phase)),
                "placed_extension", ops, local_phase_deg=float(phase),
                phase_deg=float(phase), extension_index=index,
            ))

    right_x = float(values["assembly_span_mm"]) - 10.0
    instances.append(row(
        "female-rotor", "female_rotor", 0, (right_x, 0.0, 0.0),
        (float(values["final_female_phase_deg"]), 0.0, 0.0), "placed_female",
        (("x", float(values["final_female_phase_deg"])),),
        pivot_mm=(right_x, HEIGHT_MM / 2.0, -30.0),
        pivot_rotation_deg=float(values["final_female_phase_deg"]),
        pre_translate_mm=(0.0, HEIGHT_MM / 2.0, -30.0),
        post_translate_mm=(0.0, -HEIGHT_MM / 2.0, 30.0),
        phase_deg=float(values["final_female_phase_deg"]),
    ))
    instances.append(row(
        "right-support", "right_support", 0, (right_x, 0.0, 0.0), (0.0, 0.0, 0.0),
        "placed_right",
    ))

    if len(instances) != int(values["physical_part_count"]):
        raise ValueError("Assembly instance count does not match physical_part_count")
    if len({item["name"] for item in instances}) != len(instances):
        raise ValueError("Assembly instance names must be unique")
    return instances
