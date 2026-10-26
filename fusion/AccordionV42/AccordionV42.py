"""Native builders and offline-testable orchestration for Accordion V4.2.

The body builders consume an already-owned Fusion component and keep source
values in millimetres until the ``NativeBuilder`` conversion boundary.  The
Task 3 orchestration below owns document creation, User Parameters, and
occurrence placement; Fusion recompute and BRep health remain runtime gates.

Fusion is unavailable in the offline test environment.  The native timeline,
kernel recompute, and BRep validity gate therefore remain ``not_run`` until a
Fusion document is rebuilt with this package.
"""

from __future__ import annotations

import math
import re
import hashlib
import sys
from pathlib import Path
from numbers import Real
from typing import Any, Iterable

# Fusion loads this entrypoint directly by path, so its script folder is not
# guaranteed to be on sys.path. These module names are generic and can also be
# left behind by another Fusion add-in loaded in the same Python process.
_PACKAGE_DIR = Path(__file__).resolve().parent
for _module_name in ("Contract", "Geometry", "NativeThreads"):
    _loaded_module = sys.modules.get(_module_name)
    _loaded_file = getattr(_loaded_module, "__file__", None)
    if _loaded_module is not None and (
        _loaded_file is None
        or Path(_loaded_file).resolve().parent != _PACKAGE_DIR
    ):
        del sys.modules[_module_name]
_PACKAGE_DIR_STR = str(_PACKAGE_DIR)
if _PACKAGE_DIR_STR in sys.path:
    sys.path.remove(_PACKAGE_DIR_STR)
sys.path.insert(0, _PACKAGE_DIR_STR)

import Contract
if "Geometry" in sys.modules and getattr(sys.modules["Geometry"], "Contract", None) is not Contract:
    del sys.modules["Geometry"]
import Geometry
import NativeThreads


FUSION_RUNTIME_STATUS = "not_run"
SUPPORT_HULL_STATUS = "not_run"
MM_TO_CM = 0.1
RUN_WIDTH_MM = 620.0
RUN_VALUES = {
    "clamp_travel_mm": 0.0,
    "thread_offset_mm": -0.25,
    "pip_gap_mm": 0.6,
    "leaf_bottom_mm": -4.5,
    "leaf_top_mm": 4.5,
    "support_web_width_mm": 10.0,
    "male_bore_d_mm": 2.0,
    "joint_angle_deg": 0.0,
}


def _cm_from_mm(value: float) -> float:
    """Convert one source millimetre scalar to Fusion's centimetre scalar."""
    return float(value) * MM_TO_CM

# These are the source witnesses used by the builders and by the offline
# contract tests.  Values are source millimetres unless the key says ``deg``.
SOURCE_PROFILES = {
    "leaf": {
        "panel_thickness_mm": 9.0,
        "hinge_bore_d_mm": 4.6,
        "barrel_outer_d_mm": 9.2,
        "panel_x0_mm": 6.0,
        "panel_width_mm": 30.0,
        "band_pitch_mm": 25.0,
        "band_clearance_mm": 0.3,
    },
    "pin": {
        "shaft_d_mm": 4.0,
        "head_d_mm": 8.0,
        "shaft_length_mm": 247.0,
        "neck_length_mm": 0.5,
        "head_length_mm": 3.0,
        "flat_offset_mm": 1.5,
    },
    "left_support": {
        "web_width_mm": 10.0,
        "bed_z_mm": -38.0,
        "thread_axis_z_mm": -30.0,
        "thread_root_r_mm": 8.0,
    },
    "right_support": {
        "pip_gap_default_mm": 0.6,
        "ring_outer_r_mm": 20.0,
        "web_width_mm": 10.0,
    },
    "female_rotor": {
        "thread_length_mm": 118.0,
        "local_start_mm": -130.0,
        "groove_start_mm": -10.5,
        "groove_center_mm": -3.0,
        "groove_end_mm": 4.5,
        "rotor_end_mm": 9.5,
        "outer_r_mm": 18.0,
        "waist_r_mm": 10.5,
    },
    "rod_socket": {
        "front_thread_length_mm": 25.0,
        "rear_thread_length_mm": 20.0,
        "body_r_mm": 16.0,
        "collar_length_mm": 3.0,
    },
    "rod_shaft": {
        "joint_thread_length_mm": 23.0,
        "tip_thread_length_mm": 110.0,
        "collar_r_mm": 14.0,
        "collar_length_mm": 3.0,
    },
}


def _catalog_expression(expression: str, values: dict[str, Any],
                        parameter_links: dict[str, str] | None = None) -> str:
    """Resolve source names and catalog constants into a Fusion expression."""
    aliases = dict(values)
    aliases.update({
        "height": values.get("height_mm", Contract.HEIGHT_MM),
        "width": values.get("width_mm", values.get("width")),
        "pitch": Contract.PITCH_MM,
        "thread_offset": values.get("thread_offset_mm", values.get("thread_offset")),
        "male_bore_d": values.get("male_bore_d_mm", values.get("male_bore_d")),
        "pip_gap": values.get("pip_gap_mm", values.get("pip_gap")),
        "support_web_width": values.get("support_web_width_mm", values.get("support_web_width")),
        "joint_angle": values.get("joint_angle_deg", values.get("joint_angle")),
        "thread_pitch": NativeThreads.STANDARD["pitch"],
        "thread_angle": NativeThreads.STANDARD["angle"],
        "hinge_outer_d_mm": SOURCE_PROFILES["leaf"]["barrel_outer_d_mm"],
        "hinge_bore_d_mm": SOURCE_PROFILES["leaf"]["hinge_bore_d_mm"],
    })
    for name, value in NativeThreads.STANDARD.items():
        if name.endswith("_d"):
            aliases[name] = value

    def replacement(match: re.Match[str]) -> str:
        name = match.group(0)
        if parameter_links and name in parameter_links:
            return "(" + parameter_links[name] + ")"
        if name == "rod_socket_bed_mm" and parameter_links and "thread_offset" in parameter_links:
            # The flat follows the female groove crest, preserving 2 mm wall.
            return "(%g mm - %s + 2 mm)" % (
                NativeThreads.STANDARD["female_major_d"] / 2,
                parameter_links["thread_offset"])
        value = aliases.get(name)
        if not isinstance(value, Real) or isinstance(value, bool):
            return name
        if name.endswith("_deg") or name.endswith("_phase") or name in {
            "joint_angle", "thread_angle", "phase", "phase_deg",
        }:
            unit = " deg"
        elif name.endswith("_count") or name in {"index", "parity"}:
            unit = ""
        else:
            unit = " mm"
        return "(" + str(float(value)) + unit + ")"

    names = sorted((name for name, value in aliases.items()
                    if isinstance(value, Real) and not isinstance(value, bool)),
                   key=len, reverse=True)
    if not names:
        return expression
    return re.sub(r"\b(?:" + "|".join(map(re.escape, names)) + r")\b", replacement, expression)


class NativeBuilder:
    """Small Fusion adapter shared by all seven body builders.

    ``design`` and ``values`` are supplied by the future Run layer.  This
    class has no document/assembly ownership and never creates a parameter
    table; it only turns source expressions into native sketches/features.
    """

    def __init__(self, design: Any, values: dict[str, Any]):
        import adsk.core as core  # type: ignore
        import adsk.fusion as fusion  # type: ignore

        self.core = core
        self.fusion = fusion
        self.design = design
        self.root = design.rootComponent
        self.values = values
        self.parameter_links: dict[str, str] = {}
        self.witnesses: list[Any] = []
        self.positive = fusion.ExtentDirections.PositiveExtentDirection
        self.orientations = (
            fusion.DimensionOrientations.HorizontalDimensionOrientation,
            fusion.DimensionOrientations.VerticalDimensionOrientation,
        )

    def expression(self, text: str) -> str:
        return _catalog_expression(text, self.values, self.parameter_links)

    def value(self, expression: str) -> Any:
        return self.core.ValueInput.createByString(self.expression(expression))

    def internal_cm(self, expression: str) -> float:
        # Fusion evaluates length expressions to internal centimetres.  The
        # defaultUnits argument only supplies the expression's default unit;
        # it does not change the returned internal-unit scalar.
        return self.design.unitsManager.evaluateExpression(
            self.expression(expression), "mm")

    def point(self, x: float, y: float, z: float) -> Any:
        return self.core.Point3D.create(x, y, z)

    def frame(self, sketch: Any, origin: tuple[float, float, float],
              x_hat: tuple[float, float, float], y_hat: tuple[float, float, float]) -> dict[str, tuple[int, int]]:
        origin_s = sketch.modelToSketchSpace(self.point(*origin))
        x_s = sketch.modelToSketchSpace(self.point(*x_hat))
        y_s = sketch.modelToSketchSpace(self.point(*y_hat))
        if max(abs(origin_s.x), abs(origin_s.y), abs(origin_s.z)) > 1e-4:
            raise RuntimeError("Sketch frame origin is not at the sketch origin")

        def axis(target: Any) -> tuple[int, int]:
            dx, dy = target.x - origin_s.x, target.y - origin_s.y
            if abs(dx) >= abs(dy):
                return (0, 1 if dx >= 0 else -1)
            return (1, 1 if dy >= 0 else -1)

        x_axis, y_axis = axis(x_s), axis(y_s)
        if x_axis[0] == y_axis[0]:
            raise RuntimeError("Sketch frame axes overlap")
        return {"u": x_axis, "v": y_axis}

    def uv(self, frame: dict[str, tuple[int, int]], u_cm: float, v_cm: float) -> Any:
        coords = [0.0, 0.0]
        for axis, value in ((frame["u"], u_cm), (frame["v"], v_cm)):
            coords[axis[0]] += axis[1] * value
        return self.point(coords[0], coords[1], 0.0)

    def new_sketch(self, component: Any, plane: Any, name: str) -> Any:
        sketch = component.sketches.add(plane)
        sketch.name = name
        self.witnesses.append(sketch)
        return sketch

    def offset_plane(self, component: Any, base: Any, expression: str, name: str) -> Any:
        plane_input = component.constructionPlanes.createInput()
        if not plane_input.setByOffset(base, self.value(expression)):
            raise RuntimeError("Could not create " + name)
        plane = component.constructionPlanes.add(plane_input)
        plane.name = name
        plane.isLightBulbOn = False
        self.witnesses.append(plane)
        return plane

    def add_point(self, sketch: Any, frame: dict[str, tuple[int, int]],
                  u_cm: float, v_cm: float) -> Any:
        return sketch.sketchPoints.add(self.uv(frame, u_cm, v_cm))

    def finish_sketch(self, sketch: Any, profiles: int = 1) -> None:
        if sketch.profiles.count != profiles:
            raise RuntimeError("%s has %s profiles; expected %s" %
                               (sketch.name, sketch.profiles.count, profiles))
        sketch.isLightBulbOn = False

    def normal_sign(self, sketch: Any, axis_index: int) -> int:
        origin = sketch.sketchToModelSpace(self.point(0, 0, 0))
        tip = sketch.sketchToModelSpace(self.point(0, 0, 1))
        delta = (tip.x - origin.x, tip.y - origin.y, tip.z - origin.z)
        if abs(abs(delta[axis_index]) - 1) > 1e-4:
            raise RuntimeError("Sketch normal is not aligned with the requested axis")
        return 1 if delta[axis_index] >= 0 else -1

    def extrude(self, component: Any, profile: Any, distance: str, axis_index: int,
                name: str, body: Any = None, start: str = "0 mm", cut: bool = False) -> Any:
        operation = (self.fusion.FeatureOperations.CutFeatureOperation if cut else
                     self.fusion.FeatureOperations.JoinFeatureOperation if body is not None else
                     self.fusion.FeatureOperations.NewBodyFeatureOperation)
        feature_input = component.features.extrudeFeatures.createInput(profile, operation)
        normal = self.normal_sign(profile.parentSketch, axis_index)
        signed_start = start if normal > 0 else "-(%s) - (%s)" % (start, distance)
        feature_input.startExtent = self.fusion.OffsetStartDefinition.create(self.value(signed_start))
        if not feature_input.setOneSideExtent(
                self.fusion.DistanceExtentDefinition.create(self.value(distance)), self.positive):
            raise RuntimeError("Could not set extrusion " + name)
        if body is not None:
            feature_input.participantBodies = [body]
        feature = component.features.extrudeFeatures.add(feature_input)
        if feature is None:
            raise RuntimeError("Extrusion failed: " + name)
        feature.name = name
        self.require_healthy(feature, name)
        if body is None and not cut:
            if feature.bodies.count != 1:
                raise RuntimeError("Extrusion %s created %s bodies" % (name, feature.bodies.count))
            body = feature.bodies.item(0)
            body.name = name
        return body

    def revolve(self, component: Any, profile: Any, axis: Any, name: str,
                body: Any = None, cut: bool = False) -> Any:
        operation = (self.fusion.FeatureOperations.CutFeatureOperation if cut else
                     self.fusion.FeatureOperations.JoinFeatureOperation if body is not None else
                     self.fusion.FeatureOperations.NewBodyFeatureOperation)
        feature_input = component.features.revolveFeatures.createInput(profile, axis, operation)
        if not feature_input.setAngleExtent(False, self.value("360 deg")):
            raise RuntimeError("Could not set revolve angle " + name)
        if body is not None:
            feature_input.participantBodies = [body]
        feature = component.features.revolveFeatures.add(feature_input)
        if feature is None:
            raise RuntimeError("Revolve failed: " + name)
        feature.name = name
        self.require_healthy(feature, name)
        if body is None and not cut:
            body = feature.bodies.item(0)
            body.name = name
        return body

    def loft(self, component: Any, profiles: Iterable[Any], name: str) -> Any:
        """Create one native solid loft from already-finished sketch profiles."""
        loft_input = component.features.loftFeatures.createInput(
            self.fusion.FeatureOperations.NewBodyFeatureOperation)
        loft_input.isSolid = True
        for profile in profiles:
            loft_input.loftSections.add(profile)
        feature = component.features.loftFeatures.add(loft_input)
        if feature is None or feature.bodies.count != 1:
            raise RuntimeError("Loft failed: " + name)
        feature.name = name
        self.require_healthy(feature, name)
        body = feature.bodies.item(0)
        body.name = name
        return body

    def combine(self, component: Any, target: Any, tool: Any, operation: str, name: str) -> Any:
        tools = self.core.ObjectCollection.create()
        tools.add(tool)
        feature_input = component.features.combineFeatures.createInput(target, tools)
        feature_input.operation = {
            "join": self.fusion.FeatureOperations.JoinFeatureOperation,
            "cut": self.fusion.FeatureOperations.CutFeatureOperation,
            "intersect": self.fusion.FeatureOperations.IntersectFeatureOperation,
        }[operation]
        feature_input.isKeepToolBodies = False
        feature = component.features.combineFeatures.add(feature_input)
        if feature is None or feature.bodies.count != 1:
            raise RuntimeError("Combine failed: " + name)
        feature.name = name
        self.require_healthy(feature, name)
        result = feature.bodies.item(0)
        result.name = name
        return result

    def require_healthy(self, feature: Any, name: str) -> None:
        self.witnesses.append(feature)
        error = self.fusion.FeatureHealthStates.ErrorFeatureHealthState
        if getattr(feature, "healthState", None) == error:
            raise RuntimeError("%s: %s" % (name, getattr(feature, "errorOrWarningMessage", "")))


# A short alias keeps the builder contract convenient for Fusion scripts.
Builder = NativeBuilder


def _validate(values: dict[str, Any]) -> None:
    Contract.validate(values)


def _ordinate(builder: NativeBuilder, expression: str) -> tuple[float, str | None]:
    value = builder.internal_cm(expression)
    if abs(value) < 1e-9:
        return 0.0, None
    return value, expression if value > 0 else "-(%s)" % expression


def _draw_rectangle(builder: NativeBuilder, sketch: Any, frame: dict[str, tuple[int, int]],
                    x0: float, y0: float, width: float, height: float) -> Any:
    points = [builder.add_point(sketch, frame, x0, y0),
              sketch.sketchPoints.add(builder.uv(frame, x0 + width, y0)),
              sketch.sketchPoints.add(builder.uv(frame, x0 + width, y0 + height)),
              sketch.sketchPoints.add(builder.uv(frame, x0, y0 + height))]
    lines = [sketch.sketchCurves.sketchLines.addByTwoPoints(points[i], points[(i + 1) % 4])
             for i in range(4)]
    sketch.geometricConstraints.addHorizontal(lines[0])
    sketch.geometricConstraints.addHorizontal(lines[2])
    sketch.geometricConstraints.addVertical(lines[1])
    sketch.geometricConstraints.addVertical(lines[3])
    return lines


def _draw_polygon(builder: NativeBuilder, sketch: Any, frame: dict[str, tuple[int, int]],
                  points_mm: Iterable[tuple[float, float]]) -> list[Any]:
    points = [builder.add_point(sketch, frame, _cm_from_mm(x), _cm_from_mm(z))
              for x, z in points_mm]
    return [sketch.sketchCurves.sketchLines.addByTwoPoints(points[i], points[(i + 1) % len(points)])
            for i in range(len(points))]


def _draw_polygon_cm(builder: NativeBuilder, sketch: Any,
                     frame: dict[str, tuple[int, int]],
                     points_cm: Iterable[tuple[float, float]]) -> list[Any]:
    """Draw points already converted at the source-to-Fusion boundary."""
    points = [builder.add_point(sketch, frame, x, z) for x, z in points_cm]
    return [sketch.sketchCurves.sketchLines.addByTwoPoints(points[i], points[(i + 1) % len(points)])
            for i in range(len(points))]


def _add_box(builder: NativeBuilder, component: Any, name: str, x0: str, y0: str,
             z0: str, width: str, height: str, depth: str, body: Any = None,
             cut: bool = False) -> Any:
    plane = builder.offset_plane(component, component.xYConstructionPlane, z0, name + " plane")
    sketch = builder.new_sketch(component, plane, name + " sketch")
    z = builder.internal_cm(z0)
    frame = builder.frame(sketch, (0, 0, z), (1, 0, z), (0, 1, z))
    x_cm, _ = _ordinate(builder, x0)
    y_cm, _ = _ordinate(builder, y0)
    lines = _draw_rectangle(builder, sketch, frame, x_cm, y_cm,
                            builder.internal_cm(width), builder.internal_cm(height))
    # Anchor the lower corner so changing a span cannot translate the cutter.
    lines[0].startSketchPoint.isFixed = True
    for line, axis, expression in ((lines[0], "u", width), (lines[1], "v", height)):
        dimension = sketch.sketchDimensions.addDistanceDimension(
            line.startSketchPoint, line.endSketchPoint,
            builder.orientations[frame[axis][0]], builder.point(x_cm + 1, y_cm + 1, 0))
        if dimension is None:
            raise RuntimeError("Could not dimension " + name)
        dimension.parameter.expression = builder.expression(expression)
    builder.finish_sketch(sketch)
    return builder.extrude(component, sketch.profiles.item(0), depth, 2, name, body, cut=cut)


def _dimension_circle(builder: NativeBuilder, sketch: Any, circle: Any, diameter: str) -> None:
    center = circle.centerSketchPoint.geometry
    dimension = sketch.sketchDimensions.addDiameterDimension(
        circle, builder.point(center.x + 1, center.y + 1, 0))
    if dimension is None:
        raise RuntimeError("Could not dimension " + sketch.name)
    dimension.parameter.expression = builder.expression(diameter)


def _add_y_cylinder(builder: NativeBuilder, component: Any, name: str, x: str, z: str,
                    diameter: str, start: str, length: str, body: Any = None,
                    cut: bool = False) -> Any:
    sketch = builder.new_sketch(component, component.xZConstructionPlane, name + " sketch")
    frame = builder.frame(sketch, (0, 0, 0), (1, 0, 0), (0, 0, 1))
    x_cm, _ = _ordinate(builder, x)
    z_cm, _ = _ordinate(builder, z)
    center = builder.add_point(sketch, frame, x_cm, z_cm) if abs(x_cm) + abs(z_cm) else sketch.originPoint
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(center.geometry, builder.internal_cm(diameter) / 2)
    sketch.geometricConstraints.addCoincident(circle.centerSketchPoint, center)
    if center is not sketch.originPoint:
        center.isFixed = True
    _dimension_circle(builder, sketch, circle, diameter)
    builder.finish_sketch(sketch)
    return builder.extrude(component, sketch.profiles.item(0), length, 1, name, body, start, cut)


def _add_x_cylinder(builder: NativeBuilder, component: Any, name: str, start_x: str,
                    y: str, z: str, diameter: str, length: str, body: Any = None,
                    cut: bool = False) -> Any:
    plane = builder.offset_plane(component, component.yZConstructionPlane, start_x, name + " plane")
    sketch = builder.new_sketch(component, plane, name + " sketch")
    x_cm = builder.internal_cm(start_x)
    frame = builder.frame(sketch, (x_cm, 0, 0), (x_cm, 1, 0), (x_cm, 0, 1))
    y_cm, _ = _ordinate(builder, y)
    z_cm, _ = _ordinate(builder, z)
    center = builder.add_point(sketch, frame, y_cm, z_cm) if abs(y_cm) + abs(z_cm) else sketch.originPoint
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(center.geometry, builder.internal_cm(diameter) / 2)
    sketch.geometricConstraints.addCoincident(circle.centerSketchPoint, center)
    if center is not sketch.originPoint:
        center.isFixed = True
    _dimension_circle(builder, sketch, circle, diameter)
    builder.finish_sketch(sketch)
    return builder.extrude(component, sketch.profiles.item(0), length, 0, name, body, cut=cut)


def _add_z_cylinder(builder: NativeBuilder, component: Any, name: str, x: str, y: str,
                    diameter: str, start: str, length: str, body: Any = None,
                    cut: bool = False) -> Any:
    sketch = builder.new_sketch(component, component.xYConstructionPlane, name + " sketch")
    frame = builder.frame(sketch, (0, 0, 0), (1, 0, 0), (0, 1, 0))
    x_cm, _ = _ordinate(builder, x)
    y_cm, _ = _ordinate(builder, y)
    center = builder.add_point(sketch, frame, x_cm, y_cm) if abs(x_cm) + abs(y_cm) else sketch.originPoint
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(center.geometry, builder.internal_cm(diameter) / 2)
    sketch.geometricConstraints.addCoincident(circle.centerSketchPoint, center)
    if center is not sketch.originPoint:
        center.isFixed = True
    _dimension_circle(builder, sketch, circle, diameter)
    builder.finish_sketch(sketch)
    return builder.extrude(component, sketch.profiles.item(0), length, 2, name, body, start, cut)


def _add_polygon_y(builder: NativeBuilder, component: Any, name: str, y: str,
                   points_mm: list[tuple[float, float]], length: str,
                   body: Any = None) -> Any:
    plane = builder.offset_plane(component, component.xZConstructionPlane, y, name + " plane")
    y_cm = builder.internal_cm(y)
    sketch = builder.new_sketch(component, plane, name + " sketch")
    frame = builder.frame(sketch, (0, y_cm, 0), (1, y_cm, 0), (0, y_cm, 1))
    _draw_polygon(builder, sketch, frame, points_mm)
    builder.finish_sketch(sketch)
    return builder.extrude(component, sketch.profiles.item(0), length, 1, name, body)


def _add_polygon_x(builder: NativeBuilder, component: Any, name: str, x: str,
                   points_yz_mm: list[tuple[float, float]], length: str,
                   body: Any = None, cut: bool = False) -> Any:
    """Extrude a source YZ polygon along X, crossing the cm boundary once."""
    plane = builder.offset_plane(component, component.yZConstructionPlane, x,
                                 name + " plane")
    x_cm = builder.internal_cm(x)
    sketch = builder.new_sketch(component, plane, name + " sketch")
    frame = builder.frame(sketch, (x_cm, 0, 0), (x_cm, 1, 0), (x_cm, 0, 1))
    _draw_polygon(builder, sketch, frame, points_yz_mm)
    builder.finish_sketch(sketch)
    return builder.extrude(component, sketch.profiles.item(0), length, 0, name,
                           body, cut=cut)


def _add_z_cone(builder: NativeBuilder, component: Any, name: str, start: str,
                length: str, r0: str, r1: str, body: Any = None) -> Any:
    plane = builder.new_sketch(component, component.xZConstructionPlane, name + " sketch")
    frame = builder.frame(plane, (0, 0, 0), (1, 0, 0), (0, 0, 1))
    z0 = builder.internal_cm(start)
    z1 = z0 + builder.internal_cm(length)
    profile_cm = [(0.0, z0), (builder.internal_cm(r0), z0),
                  (builder.internal_cm(r1), z1), (0.0, z1)]
    lines = _draw_polygon_cm(builder, plane, frame, profile_cm)
    builder.finish_sketch(plane)
    return builder.revolve(component, plane.profiles.item(0), lines[-1], name, body)


def _profile_revolve_cut(builder: NativeBuilder, component: Any, name: str,
                         profile: list[tuple[float, float]], axis_z: str,
                         body: Any) -> Any:
    plane = builder.offset_plane(component, component.xZConstructionPlane,
                                 "height_mm / 2", name + " plane")
    sketch = builder.new_sketch(component, plane, name + " sketch")
    axis_cm = builder.internal_cm(axis_z)
    center_y_cm = builder.internal_cm("height_mm / 2")
    frame = builder.frame(sketch, (0, center_y_cm, 0),
                          (1, center_y_cm, 0), (0, center_y_cm, 1))
    # Geometry.pip_void_profile returns (radius, axial); sketch coordinates are (axial, Z).
    lines = _draw_polygon_cm(
        builder, sketch, frame,
        [(_cm_from_mm(axial), axis_cm + _cm_from_mm(radius))
         for radius, axial in profile])
    builder.finish_sketch(sketch)
    return builder.revolve(component, sketch.profiles.item(0), lines[-1], name, body, cut=True)


def _move_rotate(builder: NativeBuilder, component: Any, body: Any,
                 axis: str, angle: str, name: str) -> None:
    entities = builder.core.ObjectCollection.create()
    entities.add(body)
    move_input = component.features.moveFeatures.createInput2(entities)
    axis_entity = {"x": component.xConstructionAxis,
                   "y": component.yConstructionAxis,
                   "z": component.zConstructionAxis}[axis]
    # Fusion rejects a child component's native origin axis here. Use its
    # assembly proxy so rotations follow that component's placed frame.
    occurrences = builder.root.allOccurrencesByComponent(component)
    if occurrences.count != 1:
        raise RuntimeError("Body construction requires one owning occurrence: " + name)
    axis_entity = axis_entity.createForAssemblyContext(occurrences.item(0))
    if not move_input.defineAsRotate(axis_entity, builder.value(angle)):
        raise RuntimeError("Could not set rotation " + name)
    feature = component.features.moveFeatures.add(move_input)
    if feature is None:
        raise RuntimeError("Rotation failed: " + name)
    feature.name = name
    builder.require_healthy(feature, name)


def _move_translate(builder: NativeBuilder, component: Any, body: Any,
                    x: str, y: str, z: str, name: str) -> None:
    entities = builder.core.ObjectCollection.create()
    entities.add(body)
    move_input = component.features.moveFeatures.createInput2(entities)
    if not move_input.defineAsTranslateXYZ(builder.value(x), builder.value(y), builder.value(z), False):
        raise RuntimeError("Could not set translation " + name)
    feature = component.features.moveFeatures.add(move_input)
    if feature is None:
        raise RuntimeError("Translation failed: " + name)
    feature.name = name
    builder.require_healthy(feature, name)


def _support_ear(side: int, parity: int, band: int) -> list[tuple[float, float]]:
    points = [(-10, -14), (-4.5, -14), (0, -9.5), (0, -9.2),
              (4.6, -4.6), (4.6, 1.6), (1.6, 4.6), (-10, 4.6)]
    return [(-side * x, z) for x, z in points]


def _support_hull_profile(builder: NativeBuilder, component: Any, name: str,
                          z: str, x: str, y: str, width: str,
                          depth: str) -> Any:
    plane = builder.offset_plane(component, component.xYConstructionPlane, z,
                                 name + " plane")
    sketch = builder.new_sketch(component, plane, name + " sketch")
    z_cm = builder.internal_cm(z)
    frame = builder.frame(sketch, (0, 0, z_cm), (1, 0, z_cm), (0, 1, z_cm))
    x_cm, _ = _ordinate(builder, x)
    y_cm, _ = _ordinate(builder, y)
    _draw_rectangle(builder, sketch, frame, x_cm, y_cm,
                    builder.internal_cm(width), builder.internal_cm(depth))
    builder.finish_sketch(sketch)
    return sketch.profiles.item(0)


def _add_support_web(builder: NativeBuilder, component: Any, body: Any,
                     side: int, foot_z: str, name: str) -> Any:
    """Add the source support spine, trim wedges, and left hull transition."""
    left = side < 0
    bed_z = "-38 mm" if left else "-right_print_lift_mm"
    web_origin = "-support_web_width_mm" if left else "0 mm"
    web_height = "33 mm" if left else "right_print_lift_mm - 5 mm"
    body = _add_box(builder, component, name + " web", web_origin, "0 mm",
                    bed_z, "support_web_width_mm", "height_mm", web_height,
                    body)

    # support_web() removes one triangular end wedge at each Y end.  The
    # dimensions are source values: support_ear_bottom=-14 and margin=0.3.
    bed_z_mm = -38.0 if left else -float(builder.values["right_print_lift_mm"])
    trim_height_mm = -bed_z_mm - 14.0 - 0.3
    wedge_x = "-(support_web_width_mm + 1 mm)" if left else "-1 mm"
    wedge_length = "support_web_width_mm + 2 mm"
    first = [(-1.0, -1.0), (trim_height_mm + 1.0, -1.0),
             (-1.0, trim_height_mm + 1.0)]
    second = [(1.0, -1.0), (-trim_height_mm - 1.0, -1.0),
              (1.0, trim_height_mm + 1.0)]
    body = _add_polygon_x(builder, component, name + " lower Y trim", wedge_x,
                          [(y, z + bed_z_mm) for y, z in first],
                          wedge_length, body, cut=True)
    body = _add_polygon_x(builder, component, name + " upper Y trim", wedge_x,
                          [(y + Contract.HEIGHT_MM, z + bed_z_mm)
                           for y, z in second],
                          wedge_length, body, cut=True)

    if left:
        body = _add_box(builder, component, name + " foot", "-10 mm",
                        "height_mm / 2 - 18 mm", foot_z, "10 mm", "36 mm",
                        "-5 mm - (" + foot_z + ")", body)
        lower = _support_hull_profile(
            builder, component, name + " hull lower", foot_z, "-10 mm",
            "height_mm / 2 - 18 mm", "10 mm", "36 mm")
        upper = _support_hull_profile(
            builder, component, name + " hull upper", "-12 mm", "-10 mm",
            "height_mm / 2 - 32 mm", "6 mm", "64 mm")
        hull = builder.loft(component, (lower, upper), name + " hull loft")
        body = builder.combine(component, body, hull, "join", name + " hull join")
    return body


def build_leaf(builder: NativeBuilder, component: Any, values: dict[str, Any]) -> Any:
    """Build one source ``leaf()`` solid with alternating clipped knuckles."""
    _validate(values)
    profile = SOURCE_PROFILES["leaf"]
    body = _add_box(builder, component, "Leaf panel", "6 mm", "0 mm",
                    "leaf_bottom_mm", "30 mm", "height_mm", "leaf_thickness_mm")
    bands = Geometry.hinge_band_witness(values)
    for band in bands:
        edge = int(band["parity"])
        y = "%s mm" % band["y_mm"]
        length = "%s mm" % band["length_mm"]
        x = "pitch - 6 mm" if edge else "0 mm"
        connector = _add_box(builder, component, "Leaf connector %s" % band["index"],
                              x, y, "leaf_bottom_mm", "6 mm", length, "leaf_thickness_mm", body)
        body = connector
        barrel = _add_y_cylinder(builder, component, "Leaf barrel %s" % band["index"],
                                 "pitch" if edge else "0 mm", "0 mm",
                                 "hinge_outer_d_mm", y, length)
        barrel_clip = _add_box(builder, component,
                               "Leaf barrel clip %s" % band["index"],
                               "-4.6 mm" if not edge else "pitch - 4.6 mm", y,
                               "leaf_bottom_mm", "9.2 mm", length,
                               "leaf_thickness_mm")
        barrel = builder.combine(component, barrel, barrel_clip, "intersect",
                                 "Leaf barrel clipped %s" % band["index"])
        body = builder.combine(component, body, barrel, "join",
                               "Leaf barrel %s join" % band["index"])
    for x in ("0 mm", "pitch"):
        body = _add_y_cylinder(builder, component, "Leaf hinge bore " + x,
                               x, "0 mm", "hinge_bore_d_mm", "-1 mm",
                               "height_mm + 2 mm", body, cut=True)
    body.name = "Leaf body"
    return body


def build_pin(builder: NativeBuilder, component: Any, values: dict[str, Any]) -> Any:
    """Build the source hinge pin shaft, tapered neck, head, and D-flat."""
    _validate(values)
    profile = SOURCE_PROFILES["pin"]
    body = _add_z_cylinder(builder, component, "Pin shaft", "0 mm", "0 mm",
                           "4 mm", "0 mm", "247 mm")
    body = _add_z_cone(builder, component, "Pin neck", "246.5 mm", "0.5 mm",
                       "2 mm", "4 mm", body)
    body = _add_z_cylinder(builder, component, "Pin head", "0 mm", "0 mm",
                           "8 mm", "247 mm", "3 mm", body)
    # The print bed cut is a native subtractive feature and preserves the flat.
    body = _add_box(builder, component, "Pin D-flat", "1.5 mm", "-5 mm",
                    "-1 mm", "5 mm", "10 mm", "252 mm", body, cut=True)
    body.name = "Hinge pin body"
    return body


def _add_support_ears(builder: NativeBuilder, component: Any, body: Any,
                      side: int, parity: int) -> Any:
    for band in Geometry.hinge_band_witness(builder.values, parity):
        y = "%s mm" % band["y_mm"]
        body = _add_polygon_y(builder, component,
                              "%s support ear %s" % ("Left" if side < 0 else "Right", band["index"]),
                              y, _support_ear(side, parity, int(band["index"])),
                              "%s mm" % band["length_mm"], body)
    return body


def _cut_hinge_sweep(builder: NativeBuilder, component: Any, body: Any,
                     parity: int, name: str) -> Any:
    """Subtract the source alternating barrel sweep clearance from a support."""
    # accordion.scad uses hinge_sweep_clearance(): diameter (9.2 + 0.6) and
    # y = band_y - 0.3/2, length = band_len + 0.3.
    for band in Geometry.hinge_band_witness(builder.values, parity):
        start_mm = float(band["y_mm"]) - 0.15
        length_mm = float(band["length_mm"]) + 0.3
        body = _add_y_cylinder(
            builder, component, "%s %s" % (name, band["index"]),
            "0 mm", "0 mm", "9.8 mm", "%s mm" % start_mm,
            "%s mm" % length_mm, body, cut=True)
    return body


def build_left_support(builder: NativeBuilder, component: Any, values: dict[str, Any]) -> Any:
    """Build the left end plate, web, polygon ears, male thread, and bore."""
    _validate(values)
    body = _add_box(builder, component, "Left end plate", "-10 mm", "0 mm",
                    "-8 mm", "6 mm", "height_mm", "12.5 mm")
    body = _add_support_ears(builder, component, body, -1, 1)
    body = _add_support_web(builder, component, body, -1, "-38 mm",
                            "Left support")
    body = _add_box(builder, component, "Left threaded root",
                    "-10 mm", "height_mm / 2 - 12 mm",
                    "-38 mm", "8 mm", "24 mm", "34 mm", body)
    collar = _add_x_cylinder(builder, component, "Left collar", "-4 mm", "height_mm / 2",
                             "-30 mm", "16 mm", "6 mm")
    body = builder.combine(component, body, collar, "join", "Left collar join")
    thread = _add_z_cylinder(builder, component, "Left male thread blank", "0 mm", "0 mm",
                             "male_major_d", "0 mm", "male_length_mm")
    thread = NativeThreads.add_modeled_thread(
        builder, component, thread, False, "male_length_mm", "Left male thread")
    _move_rotate(builder, component, thread, "y", "90 deg", "Left thread axis")
    _move_translate(builder, component, thread, "0 mm", "height_mm / 2", "-30 mm",
                    "Left thread placement")
    body = builder.combine(component, body, thread, "join", "Left thread join")
    # Clip the helix before joining the grounded sole. The sole lies wholly
    # above this plane, so the final solid is unchanged; this avoids an ASM
    # containment failure at the untrimmed helix/sole intersections.
    body = _add_box(builder, component, "Left support bed clip", "-200 mm", "-100 mm",
                    "-100 mm", "400 mm", "400 mm", "62 mm", body, cut=True)
    body = _add_box(builder, component, "Left support bed sole", "0 mm",
                    "height_mm / 2 - 0.5 mm", "-38 mm", "male_length_mm",
                    "1 mm", "1.5 mm", body)
    body = _add_x_cylinder(builder, component, "Left axial bore",
                           "-(support_web_width_mm + 0.1 mm)",
                           "height_mm / 2", "-30 mm", "male_bore_d_mm",
                           "male_length_mm + support_web_width_mm + 0.2 mm",
                           body, cut=True)
    body = _add_y_cylinder(builder, component, "Left hinge bore", "0 mm", "0 mm",
                           "4.6 mm", "-1 mm", "height_mm + 2 mm", body, cut=True)
    body = _cut_hinge_sweep(builder, component, body, 0, "Left hinge sweep")
    body.name = "Left support body"
    return body


def build_right_support(builder: NativeBuilder, component: Any, values: dict[str, Any]) -> Any:
    """Build the right support, ring/web, and exact source PIP V void."""
    _validate(values)
    body = _add_box(builder, component, "Right end plate", "4 mm", "0 mm",
                    "-8 mm", "6 mm", "height_mm", "12.5 mm")
    body = _add_support_ears(builder, component, body, 1, 0)
    body = _add_support_web(builder, component, body, 1, "-26 mm",
                            "Right support")
    hub = _add_x_cylinder(builder, component, "Right capture ring", "-7 mm",
                          "height_mm / 2", "-30 mm", "40 mm", "8 mm")
    body = builder.combine(component, body, hub, "join", "Right ring join")
    body = _profile_revolve_cut(builder, component, "Right PIP V void",
                                Geometry.pip_void_profile(values), "-30 mm", body)
    body = _add_y_cylinder(builder, component, "Right hinge bore", "0 mm", "0 mm",
                           "4.6 mm", "-1 mm", "height_mm + 2 mm", body, cut=True)
    body = _cut_hinge_sweep(builder, component, body, 1, "Right hinge sweep")
    body = _add_box(builder, component, "Right support bed clip", "-200 mm", "-100 mm",
                    "-100 mm", "400 mm", "400 mm",
                    "100 mm - right_print_lift_mm", body, cut=True)
    body.name = "Right support body"
    return body


def build_female_rotor(builder: NativeBuilder, component: Any, values: dict[str, Any]) -> Any:
    """Build the rotor shell and its native 118 mm female TR20x4 feature."""
    _validate(values)
    profile = SOURCE_PROFILES["female_rotor"]
    body = _add_z_cylinder(builder, component, "Rotor rear journal", "0 mm", "0 mm",
                           "36 mm", "-130 mm", "119.5 mm")
    body = _add_z_cone(builder, component, "Rotor entry cone", "-10.5 mm", "7.5 mm",
                       "18 mm", "10.5 mm", body)
    body = _add_z_cone(builder, component, "Rotor exit cone", "-3 mm", "7.5 mm",
                       "10.5 mm", "18 mm", body)
    body = _add_z_cylinder(builder, component, "Rotor front journal", "0 mm", "0 mm",
                           "36 mm", "4.5 mm", "5 mm", body)
    body = _add_z_cylinder(builder, component, "Rotor through bore", "0 mm", "0 mm",
                           "female_minor_d", "-130.1 mm", "139.7 mm", body, cut=True)
    body = NativeThreads.add_modeled_thread(
        builder, component, body, True, "118 mm", "Female rotor thread")
    _move_rotate(builder, component, body, "y", "90 deg", "Female rotor axis")
    _move_translate(builder, component, body, "0 mm", "height_mm / 2", "-30 mm",
                    "Female rotor placement")
    body = _add_box(builder, component, "Female rotor bed clip", "-200 mm", "-100 mm",
                    "-100 mm", "400 mm", "400 mm", "100 mm - right_print_lift_mm",
                    body, cut=True)
    body.name = "Female rotor body"
    return body


def build_rod_socket(builder: NativeBuilder, component: Any, values: dict[str, Any]) -> Any:
    """Build a separate CT09 socket with front/rear female native threads."""
    _validate(values)
    body = _add_z_cylinder(builder, component, "CT09 socket shell", "0 mm", "0 mm",
                           "32 mm", "0 mm", "rod_shaft_start_mm")
    body = _add_z_cylinder(builder, component, "CT09 socket bore", "0 mm", "0 mm",
                           "female_minor_d", "-0.1 mm", "rod_shaft_start_mm + 0.2 mm",
                           body, cut=True)
    body = NativeThreads.add_modeled_thread(
        builder, component, body, True, "25 mm", "CT09 socket front female")
    # The shell stops at the rear segment's start. Adjacent threaded annuli
    # share only an end face, so Join cannot refill the rear groove.
    rear = _add_z_cylinder(builder, component, "CT09 rear thread blank", "0 mm", "0 mm",
                           "32 mm", "0 mm", "20 mm")
    rear = _add_z_cylinder(builder, component, "CT09 rear thread bore", "0 mm", "0 mm",
                           "female_minor_d", "-0.1 mm", "20.2 mm", rear, cut=True)
    rear = NativeThreads.add_modeled_thread(
        builder, component, rear, True, "20 mm", "CT09 socket rear female")
    _move_rotate(builder, component, rear, "z", "rod_joint_phase_deg", "CT09 socket rear phase")
    _move_translate(builder, component, rear, "0 mm", "0 mm", "rod_shaft_start_mm",
                    "CT09 socket rear placement")
    body = builder.combine(component, body, rear, "join", "CT09 socket thread union")
    body = _add_box(builder, component, "CT09 socket bed cut", "-40 mm", "-40 mm",
                    "-1 mm", "80 mm", "40 mm - rod_socket_bed_mm",
                    "rod_socket_length_mm + 2 mm", body, cut=True)
    body.name = "CT09 socket body"
    return body


def build_rod_shaft(builder: NativeBuilder, component: Any, values: dict[str, Any]) -> Any:
    """Build a separate CT09 shaft with two male threads and one bore."""
    _validate(values)
    joint = _add_z_cylinder(builder, component, "CT09 shaft joint blank", "0 mm", "0 mm",
                            "male_major_d", "0 mm", "23 mm")
    joint = NativeThreads.add_modeled_thread(
        builder, component, joint, False, "23 mm", "CT09 shaft joint male")
    _move_rotate(builder, component, joint, "z", "rod_joint_phase_deg", "CT09 shaft joint phase")
    _move_translate(builder, component, joint, "0 mm", "0 mm", "rod_shaft_start_mm",
                    "CT09 shaft joint placement")
    tip = _add_z_cylinder(builder, component, "CT09 shaft tip blank", "0 mm", "0 mm",
                          "male_major_d", "0 mm", "110 mm")
    tip = NativeThreads.add_modeled_thread(
        builder, component, tip, False, "110 mm", "CT09 shaft tip male")
    _move_translate(builder, component, tip, "0 mm", "0 mm", "shank_mm",
                    "CT09 shaft tip placement")
    collar = _add_z_cylinder(builder, component, "CT09 shaft stop collar", "0 mm", "0 mm",
                             "28 mm", "rod_socket_length_mm", "3 mm")
    body = builder.combine(component, joint, tip, "join", "CT09 shaft thread union")
    body = builder.combine(component, body, collar, "join", "CT09 shaft collar union")
    body = _add_z_cylinder(builder, component, "CT09 shaft continuous bore", "0 mm", "0 mm",
                           "male_bore_d_mm", "rod_shaft_start_mm - 0.1 mm",
                           "rod_shaft_length_mm + 0.2 mm", body, cut=True)
    body = _add_box(builder, component, "CT09 shaft bed cut", "-40 mm", "-40 mm",
                    "-1 mm", "80 mm", "40 mm - 7 mm", "extension_length_mm + 2 mm",
                    body, cut=True)
    body.name = "CT09 shaft body"
    return body


_PARAMETER_SPECS = (
    ("thread_offset", "thread_offset_mm", "mm", "Source guard: -0.4..-0.1 mm; direct edits outside this domain are unsupported."),
    ("male_bore_d", "male_bore_d_mm", "mm", "Source guard: positive bore with thread core wall above 2 mm; direct edits outside this domain are unsupported."),
)


def _source_root() -> Path:
    # V4.2 was validated against a pinned, self-contained input snapshot.
    # The project-root SCAD is a later final revision and is intentionally not
    # substituted here because that would invalidate the recorded evidence.
    return Path(__file__).resolve().parent / "reference"


def _verify_source_hashes() -> None:
    root = _source_root()
    for name, expected in Contract.SOURCE_HASHES.items():
        path = root / name
        if not path.is_file():
            raise RuntimeError("Missing source file for hash verification: " + str(path))
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError("%s source hash mismatch" % name)


def _value_input(app: Any, expression: str) -> Any:
    factory = getattr(app, "value_input", None)
    if callable(factory):
        return factory(expression)
    core = getattr(app, "core", None)
    if core is not None and hasattr(core, "ValueInput"):
        return core.ValueInput.createByString(expression)
    try:
        import adsk.core as core  # type: ignore
    except ImportError:
        return expression
    return core.ValueInput.createByString(expression)


def _parameter_setup(app: Any, design: Any, values: dict[str, Any]) -> dict[str, str]:
    links: dict[str, str] = {}
    for name, source_name, units, comment in _PARAMETER_SPECS:
        expression = "%s %s" % (values[source_name], units)
        design.userParameters.add(name, _value_input(app, expression), units, comment)
        links[source_name] = name
        links[name] = name
    return links


def _matrix(app: Any) -> Any:
    factory = getattr(app, "create_matrix", None)
    if callable(factory):
        return factory()
    core = getattr(app, "core", None)
    if core is not None and hasattr(core, "Matrix3D"):
        return core.Matrix3D.create()
    try:
        import adsk.core as core  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Fusion Matrix3D API is unavailable") from exc
    return core.Matrix3D.create()


def _vector(app: Any, vector: tuple[float, float, float]) -> Any:
    factory = getattr(app, "create_vector", None)
    if callable(factory):
        return factory(*vector)
    core = getattr(app, "core", None)
    if core is not None and hasattr(core, "Vector3D"):
        return core.Vector3D.create(*vector)
    import adsk.core as core  # type: ignore
    return core.Vector3D.create(*vector)


def _point(app: Any, point: tuple[float, float, float]) -> Any:
    factory = getattr(app, "create_point", None)
    if callable(factory):
        return factory(*point)
    core = getattr(app, "core", None)
    if core is None:
        import adsk.core as core  # type: ignore
    return core.Point3D.create(*point)


def _set_translation(matrix: Any, app: Any, origin_mm: tuple[float, float, float]) -> None:
    translation = tuple(_cm_from_mm(value) for value in origin_mm)
    setter = getattr(matrix, "set_translation", None)
    if callable(setter):
        setter(translation)
    else:
        matrix.translation = _vector(app, translation)


def _set_x_translation(matrix: Any, app: Any, x_mm: float) -> None:
    current = getattr(matrix, "translation", None)
    if current is None:
        y_mm, z_mm = 0.0, 0.0
    elif hasattr(current, "y"):
        y_mm, z_mm = float(current.y) / MM_TO_CM, float(current.z) / MM_TO_CM
    else:
        y_mm, z_mm = float(current[1]) / MM_TO_CM, float(current[2]) / MM_TO_CM
    _set_translation(matrix, app, (x_mm, y_mm, z_mm))


def _apply_rotation(matrix: Any, app: Any, angle_deg: float, axis: str,
                    pivot_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
    axis_vectors = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
    rotation = _matrix(app)
    rotation.setToRotation(math.radians(angle_deg), _vector(app, axis_vectors[axis]),
                           _point(app, tuple(_cm_from_mm(value) for value in pivot_mm)))
    transform_by = getattr(matrix, "transformBy", None)
    if callable(transform_by):
        transform_by(rotation)
    else:
        matrix.setToRotation(math.radians(angle_deg), _vector(app, axis_vectors[axis]),
                             _point(app, tuple(_cm_from_mm(value) for value in pivot_mm)))


def _instance_matrix(app: Any, instance: dict[str, Any]) -> Any:
    matrix = _matrix(app)
    if instance["part_type"] == "female_rotor":
        # The rotor builder already creates its local X-axis rotor at
        # (0,H/2,-30).  Rotate around that local pivot, then apply only the
        # source outer X translation; this avoids applying the body-local
        # placement twice.
        pivot = tuple(float(value) for value in instance["pivot_mm"])
        local_pivot = (0.0, pivot[1], pivot[2])
        _apply_rotation(matrix, app, float(instance["pivot_rotation_deg"]), "x", local_pivot)
        _set_x_translation(matrix, app, float(instance["origin_mm"][0]))
        return matrix
    # SCAD nesting Ry(Rz(p)) applies the inner rotation first. Fusion's
    # transformBy pre-multiplies, so visit the source operators in reverse.
    for axis, angle in reversed(instance.get("rotation_ops", ())):
        _apply_rotation(matrix, app, float(angle), axis)
    _set_translation(matrix, app, tuple(float(value) for value in instance["origin_mm"]))
    return matrix


def _collection_count(collection: Any) -> int | None:
    count = getattr(collection, "count", None)
    if isinstance(count, int):
        return count
    try:
        return len(collection)
    except (TypeError, AttributeError):
        return None


def build_document(app: Any, design: Any, values: dict[str, Any]) -> dict[str, Any]:
    """Build one native component per part type and place its occurrences.

    Builders remain body-local.  Assembly transforms are applied once on the
    occurrence matrix from :func:`Contract.assembly_instances`; the female
    rotor's local Y/Z placement is therefore not repeated here.
    """
    Contract.validate(values)
    _verify_source_hashes()
    global RUN_WIDTH_MM
    RUN_WIDTH_MM = float(values["width_mm"])
    instances = Contract.assembly_instances(values)
    parameter_links = _parameter_setup(app, design, values)
    root = design.rootComponent
    builder = NativeBuilder(design, values)
    builder.parameter_links = parameter_links
    builders = {
        "leaf": build_leaf,
        "pin": build_pin,
        "left_support": build_left_support,
        "right_support": build_right_support,
        "female_rotor": build_female_rotor,
        "rod_socket": build_rod_socket,
        "rod_shaft": build_rod_shaft,
    }
    components: dict[str, Any] = {}
    bodies: dict[str, Any] = {}
    occurrences: list[Any] = []
    for instance in instances:
        part_type = instance["part_type"]
        matrix = _instance_matrix(app, instance)
        if part_type not in components:
            occurrence = root.occurrences.addNewComponent(matrix)
            component = occurrence.component
            component.name = "AccordionV42 " + part_type
            components[part_type] = component
            bodies[part_type] = builders[part_type](builder, component, values)
        else:
            occurrence = root.occurrences.addExistingComponent(components[part_type], matrix)
        occurrences.append({"instance": instance, "occurrence": occurrence})
    witnesses = {
        name: values[name]
        for name in ("assembly_span_mm", "dx_mm", "dz_mm",
                     "actual_female_engagement_mm", "actual_shoulder_gap_mm")
    }
    limitations = (
        "Fusion kernel geometry, native Thread health and live parameter recompute remain unverified.",
    )
    actual_body_count = 0
    body_counts_available = True
    for component in components.values():
        count = _collection_count(getattr(component, "bRepBodies", None))
        if count is None:
            body_counts_available = False
            break
        actual_body_count += count
    actual_thread_count = 0
    thread_counts_available = True
    for component in components.values():
        features = getattr(component, "features", None)
        count = _collection_count(getattr(features, "threadFeatures", None))
        if count is None:
            thread_counts_available = False
            break
        actual_thread_count += count
    native_thread_definitions_by_part = {
        "left_support": 1,
        "female_rotor": 1,
        "rod_socket": 2,
        "rod_shaft": 2,
    }
    native_thread_definitions = sum(
        native_thread_definitions_by_part.get(part_type, 0)
        for part_type in components
    )
    actual_counts = {
        "component_definitions": len(components),
        "body_definitions": actual_body_count if body_counts_available else None,
        "occurrence_instances": len(occurrences),
        # Physical thread segments are assembly instances.  Fusion's native
        # thread feature collection is measured once per unique component.
        "physical_thread_segments": None,
        "native_thread_feature_definitions": (
            actual_thread_count if thread_counts_available else None
        ),
    }
    expected_counts = {
        "component_definitions": len(components),
        "body_definitions": len(components),
        "occurrence_instances": len(instances),
        "physical_thread_segments": int(values["thread_segment_count"]),
        "native_thread_feature_definitions": native_thread_definitions,
    }
    return {
        "run_width_mm": RUN_WIDTH_MM,
        "run_values": {name: values[name] for name in RUN_VALUES},
        "run_configuration_only": (
            "clamp_travel_mm", "pip_gap_mm", "leaf_bottom_mm", "leaf_top_mm", "joint_angle_deg",
            "support_web_width_mm",
        ),
        "rebuild_required_for_run_configuration": True,
        "expected_counts": expected_counts,
        "actual_counts": actual_counts,
        "build_attempted": True,
        "solid_health_status": "not_run",
        "recompute_status": "not_run",
        "components": components,
        "bodies": bodies,
        "occurrences": occurrences,
        "source_hashes": dict(Contract.SOURCE_HASHES),
        "parameter_links": parameter_links,
        "measurement_witnesses": witnesses,
        "fusion_runtime_status": FUSION_RUNTIME_STATUS,
        "limitations": limitations,
        "run_log": "Accordion V4.2 W=%g components=%d occurrences=%d" %
                   (RUN_WIDTH_MM, len(components), len(occurrences)),
    }


def run(context: Any) -> dict[str, Any]:
    """Create a fresh parametric Fusion document and build the configured width."""
    app = getattr(context, "app", None) or getattr(context, "application", None)
    if app is None:
        try:
            import adsk.core as core  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Fusion application context is required") from exc
        app = core.Application.get()
    # Every run owns a new document.  A context.design is intentionally not
    # reused, so a run cannot append occurrences into a user's open design.
    documents = getattr(app, "documents", None)
    if documents is None or not hasattr(documents, "add"):
        raise RuntimeError("Fusion document collection is required")
    import adsk.core as core  # type: ignore
    document = documents.add(core.DocumentTypes.FusionDesignDocumentType)
    design = getattr(document, "product", None) or getattr(app, "activeProduct", None)
    if design is None:
        raise RuntimeError("Parametric Fusion design is required")
    try:
        import adsk.fusion as fusion  # type: ignore
    except ImportError:
        fusion = None
    if fusion is not None:
        cast_design = fusion.Design.cast(design)
        if cast_design is None:
            raise RuntimeError("Active product is not a Fusion Design")
        parametric_type = getattr(getattr(fusion, "DesignTypes", None), "ParametricDesignType", None)
        if parametric_type is not None:
            cast_design.designType = parametric_type
            if getattr(cast_design, "designType", None) != parametric_type:
                raise RuntimeError("Fusion design must use ParametricDesignType")
        design = cast_design
    width = getattr(context, "width_mm", RUN_WIDTH_MM)
    run_values = dict(RUN_VALUES)
    run_values.update(getattr(context, "run_values", {}) or {})
    values = Contract.derive(float(width), **run_values)
    return build_document(app, design, values)
