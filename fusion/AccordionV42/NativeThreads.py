"""Native modeled TR20x4 adapter for the isolated Accordion V4.2 package.

The source contract is expressed in millimetres.  Fusion's BRep geometry and
``ThreadInfo`` diameter values use centimetres, so the conversion is kept at
the adapter boundary: catalog/profile helpers stay in source millimetres and
the runtime selector converts its expected radius to centimetres once.

Fusion runtime behavior is intentionally confined to ``add_modeled_thread``.
The pure helpers below are usable by offline tests without importing Fusion.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Iterable


THREAD_OFFSET_MIN_MM = -0.4
THREAD_OFFSET_MAX_MM = -0.1
THREAD_ROOT_OVERLAP_MM = 0.15
RADIUS_TOLERANCE_CM = 1e-6
AXIS_TOLERANCE = 1e-6


# Source catalog values are diameters in millimetres.  Do not turn these into
# User Parameters: changing the standard requires rebuilding the adapter.
STANDARD = {
    "type": "ISO Metric Trapezoidal Threads",
    "designation": "TR20x4",
    "external_class": "7e",
    "internal_class": "7H",
    "hand": "right",
    "pitch": 4.0,
    "angle": 30.0,
    "male_major_d": 19.85,
    "male_pitch_d": 17.7725,
    "male_minor_d": 15.287,
    "female_major_d": 20.5,
    "female_pitch_d": 18.1775,
    "female_minor_d": 16.1875,
}


def validate_offset_mm(value: Real) -> float:
    """Validate and return the source ``thread_offset`` in millimetres."""
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        raise ValueError("thread_offset must be a finite real value in mm")
    result = float(value)
    if not THREAD_OFFSET_MIN_MM <= result <= THREAD_OFFSET_MAX_MM:
        raise ValueError("thread_offset must be -0.4..-0.1 mm")
    return result


def catalog_radii_mm(internal: bool = False) -> dict[str, float]:
    """Return source catalog radii in millimetres for one thread handedness."""
    prefix = "female" if internal else "male"
    return {
        "major": STANDARD[f"{prefix}_major_d"] / 2.0,
        "pitch": STANDARD[f"{prefix}_pitch_d"] / 2.0,
        "minor": STANDARD[f"{prefix}_minor_d"] / 2.0,
    }


def _offset_from_values(values: dict[str, Any]) -> float:
    if "thread_offset_mm" in values:
        return validate_offset_mm(values["thread_offset_mm"])
    if "thread_offset" in values:
        return validate_offset_mm(values["thread_offset"])
    raise ValueError("Missing source parameter: thread_offset_mm")


def profile(values: dict[str, Any], internal: bool = False) -> list[tuple[float, float]]:
    """Return the source trapezoid as ``(radius_mm, axial_mm)`` points.

    The catalog crest and bore radii remain unchanged.  The signed offset
    changes the root/groove clearance and the axial half-width, matching
    ``threads.scad``.
    """
    offset = _offset_from_values(values)
    tangent = math.tan(math.radians(STANDARD["angle"] / 2.0))
    cosine = math.cos(math.radians(STANDARD["angle"] / 2.0))
    if internal:
        root = STANDARD["female_minor_d"] / 2.0 - THREAD_ROOT_OVERLAP_MM
        crest = STANDARD["female_major_d"] / 2.0 - offset
        pitch_radius = STANDARD["female_pitch_d"] / 2.0
        axial_allowance = -offset / cosine
    else:
        root = STANDARD["male_minor_d"] / 2.0 + offset - THREAD_ROOT_OVERLAP_MM
        crest = STANDARD["male_major_d"] / 2.0
        pitch_radius = STANDARD["male_pitch_d"] / 2.0
        axial_allowance = offset / cosine

    def half_width(radius: float) -> float:
        return (STANDARD["pitch"] / 4.0
                - (radius - pitch_radius) * tangent
                + axial_allowance)

    return [
        (root, -half_width(root)),
        (crest, -half_width(crest)),
        (crest, half_width(crest)),
        (root, half_width(root)),
    ]


def _iter_collection(collection: Any) -> Iterable[Any]:
    """Iterate Fusion collections and simple Python sequences alike."""
    try:
        return iter(collection)
    except TypeError:
        count = int(collection.count)
        return (collection.item(index) for index in range(count))


def select_source_cylinder(
    faces: Iterable[Any],
    cylinder_surface_type: Any,
    expected_radius_mm: float,
    axial_direction: Any = (0.0, 0.0, 1.0),
) -> Any:
    """Select exactly one axial source cylinder at the mm-to-cm boundary.

    ``expected_radius_mm`` is a source value.  Face radii are Fusion values in
    centimetres.  ``axial_direction`` is an arbitrary unit vector in the same
    coordinate frame as the face axis.  A face is accepted when its axis is
    parallel or anti-parallel to that vector; transverse and malformed axes
    are rejected.
    """
    target_axis = _vector_components(axial_direction, "axial_direction")
    expected_radius_cm = float(expected_radius_mm) / 10.0
    candidates = []
    for face in _iter_collection(faces):
        geometry = getattr(face, "geometry", None)
        if geometry is None or getattr(geometry, "surfaceType", None) != cylinder_surface_type:
            continue
        radius = getattr(geometry, "radius", None)
        axis = getattr(geometry, "axis", None)
        try:
            face_axis = _vector_components(axis, "face axis")
        except ValueError:
            continue
        if radius is None:
            continue
        if abs(float(radius) - expected_radius_cm) > RADIUS_TOLERANCE_CM:
            continue
        dot = sum(left * right for left, right in zip(face_axis, target_axis))
        if abs(abs(dot) - 1.0) > AXIS_TOLERANCE:
            continue
        candidates.append(face)
    if len(candidates) != 1:
        raise RuntimeError(
            "Expected one axial catalog cylinder, found %s" % len(candidates)
        )
    return candidates[0]


def _vector_components(value: Any, name: str) -> tuple[float, float, float]:
    """Read and validate a Fusion vector or a three-number stand-in."""
    if value is None:
        raise ValueError(name + " must be a unit vector")
    if all(hasattr(value, component) for component in ("x", "y", "z")):
        components = (value.x, value.y, value.z)
    else:
        try:
            components = tuple(value)
        except TypeError as error:
            raise ValueError(name + " must be a unit vector") from error
        if len(components) != 3:
            raise ValueError(name + " must be a unit vector")
    try:
        vector = tuple(float(component) for component in components)
    except (TypeError, ValueError) as error:
        raise ValueError(name + " must be a unit vector") from error
    if not all(math.isfinite(component) for component in vector):
        raise ValueError(name + " must be a unit vector")
    norm = math.sqrt(sum(component * component for component in vector))
    if abs(norm - 1.0) > AXIS_TOLERANCE:
        raise ValueError(name + " must be a unit vector")
    return vector


_MISSING = object()


def _validate_installed_thread_data(info: Any, internal: bool) -> None:
    if info is None:
        raise RuntimeError("Installed ThreadData is missing")
    prefix = "female" if internal else "male"
    metadata = {
        "isTapered": False,
        "isInternal": internal,
        "threadType": STANDARD["type"],
        "threadDesignation": STANDARD["designation"],
        "threadClass": STANDARD["internal_class"] if internal else STANDARD["external_class"],
    }
    for name, expected in metadata.items():
        actual = getattr(info, name, _MISSING)
        if actual is _MISSING:
            raise RuntimeError("Installed ThreadData is missing " + name)
        if name in ("isTapered", "isInternal"):
            matches = actual is expected
        else:
            matches = actual == expected
        if not matches:
            raise RuntimeError("Installed ThreadData differs for " + name)

    thread_pitch = getattr(info, "threadPitch", _MISSING)
    if thread_pitch is _MISSING:
        raise RuntimeError("Installed ThreadData is missing threadPitch")
    try:
        pitch_matches = abs(float(thread_pitch) - STANDARD["pitch"] / 10.0) <= 1e-7
    except (TypeError, ValueError):
        pitch_matches = False
    if not pitch_matches:
        raise RuntimeError("Installed ThreadData differs for threadPitch")

    thread_angle = getattr(info, "threadAngle", _MISSING)
    if thread_angle is _MISSING:
        raise RuntimeError("Installed ThreadData is missing threadAngle")
    try:
        angle_matches = abs(float(thread_angle) - STANDARD["angle"]) <= 1e-7
    except (TypeError, ValueError):
        angle_matches = False
    if not angle_matches:
        raise RuntimeError("Installed ThreadData differs for threadAngle")

    right_handed = getattr(info, "isRightHanded", _MISSING)
    if right_handed is _MISSING:
        raise RuntimeError("Installed ThreadData is missing isRightHanded")
    if right_handed is not True:
        raise RuntimeError("Installed ThreadData differs for isRightHanded")

    expected = catalog_radii_mm(internal)
    expected_diameters = {
        "major_d": expected["major"] * 2.0,
        "pitch_d": expected["pitch"] * 2.0,
        "minor_d": expected["minor"] * 2.0,
    }
    for field, expected_mm in expected_diameters.items():
        diameter_cm = getattr(info, field.replace("_d", "") + "Diameter", None)
        if diameter_cm is None:
            raise RuntimeError("Installed ThreadData is missing " + field)
        try:
            diameter_matches = abs(float(diameter_cm) * 10.0 - expected_mm) <= 1e-7
        except (TypeError, ValueError):
            diameter_matches = False
        if not diameter_matches:
            raise RuntimeError("Installed ThreadData differs for %s %s" % (prefix, field))

def _generated_thread_faces(builder: Any, thread: Any) -> list[Any]:
    plane_type = builder.core.SurfaceTypes.PlaneSurfaceType
    generated = [
        face for face in _iter_collection(thread.faces)
        if getattr(getattr(face, "geometry", None), "surfaceType", None) != plane_type
    ]
    if len(generated) != 3:
        raise RuntimeError(
            "Expected two thread flanks and one root surface; got %s" % len(generated)
        )
    return generated


def add_modeled_thread(
    builder: Any,
    component: Any,
    body: Any,
    internal: bool,
    length_expression: str,
    role: str,
    axial_direction: Any = (0.0, 0.0, 1.0),
) -> Any:
    """Add native modeled Thread plus FDM Offset Face and return its final body.

    ``axial_direction`` is expressed in the component's local frame.  The
    default +Z is the V4.2 source body invariant; callers may state another
    local direction for a body built along X or Y.

    ``length_expression`` is passed unchanged to ``builder.value`` so the
    owning builder remains the sole unit-aware Fusion boundary.  The helper
    does not evaluate or convert that expression in Python.
    """
    if not isinstance(internal, bool):
        raise TypeError("internal must be bool")
    if not isinstance(role, str) or not role.strip():
        raise ValueError("role must be a non-empty feature name")
    if not isinstance(length_expression, str) or not length_expression.strip():
        raise ValueError("length_expression must be a non-empty Fusion expression")

    spec = STANDARD
    thread_class = spec["internal_class"] if internal else spec["external_class"]
    info = builder.fusion.ThreadInfo.create(
        False,
        internal,
        spec["type"],
        spec["designation"],
        thread_class,
        True,
    )
    if info is None:
        raise RuntimeError("Installed Fusion does not provide " + spec["designation"])
    _validate_installed_thread_data(info, internal)

    radii = catalog_radii_mm(internal)
    source_radius_mm = radii["minor"] if internal else radii["major"]
    source_face = select_source_cylinder(
        body.faces,
        builder.core.SurfaceTypes.CylinderSurfaceType,
        source_radius_mm,
        axial_direction=axial_direction,
    )

    thread_input = component.features.threadFeatures.createInput(source_face, info)
    thread_input.isModeled = True
    thread_input.isFullLength = False
    thread_input.threadLocation = builder.fusion.ThreadLocations.LowEndThreadLocation
    thread_input.threadLength = builder.value(length_expression)
    thread_input.threadOffset = builder.value("0 mm")
    thread = component.features.threadFeatures.add(thread_input)
    if thread is None or thread.bodies.count != 1 or not thread.bodies.item(0).isSolid:
        raise RuntimeError("Modeled Thread failed: " + role)
    _validate_installed_thread_data(getattr(thread, "threadInfo", None), internal)
    thread.name = "%s Thread TR20x4 %s" % (role, thread_class)
    builder.require_healthy(thread, thread.name)

    # Thread exposes exactly two helical flanks and one root cylinder here.
    # Plane end caps are deliberately excluded from Offset Face.
    generated = _generated_thread_faces(builder, thread)
    offset_input = component.features.offsetFacesFeatures.createInput(
        generated,
        builder.value("thread_offset"),
    )
    allowance = component.features.offsetFacesFeatures.add(offset_input)
    if allowance is None or allowance.bodies.count != 1:
        raise RuntimeError("Native FDM Offset Face failed: " + role)
    allowance.name = "%s Offset Face FDM flank and root allowance" % role
    builder.require_healthy(allowance, allowance.name)
    result = allowance.bodies.item(0)
    if not result.isSolid:
        raise RuntimeError("Thread allowance must preserve a solid: " + role)
    return result
