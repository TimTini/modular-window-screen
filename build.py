"""Build and audit the parametric V4.2 assembly; never controls a printer."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit import inspect as inspect_mesh, signed_volume, triangles_from
from check_layers import inspect_layers
sys.path.insert(0, str(HERE / "tests"))
from test_hinge_wall import measure_wall

PARTS = {
    "parts/leaf": ("print-leaf", 1),
    "parts/hinge-pin": ("print-hinge-pin", 1),
    "fit-kit": ("print-fit-kit", 3),
}
HARDWARE_PARTS = {
    "parts/left-support": ("print-left-support", 1),
    "parts/right-support": ("right-support", 1),
    "parts/right-pip": ("print-right-pip", 2),
    "parts/rod-extension": ("print-rod-extension", 2),
    "parts/rod-socket": ("print-rod-socket", 1),
    "parts/rod-shaft": ("print-rod-shaft", 1),
    "parts/pip-coupon": ("print-pip-coupon", 2),
    "parts/test-male": ("print-test-male", 1),
    "parts/test-female": ("print-test-female", 1),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True)
    if result.returncode or re.search(r"(?m)^ERROR:", result.stdout + result.stderr):
        raise RuntimeError(f"Command failed: {command}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def default_tool(env_name, names):
    configured = os.environ.get(env_name)
    if configured:
        return Path(configured)
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)
    return Path(names[0])


def gcode_roles(path):
    """Count actual positive XY extrusion, rather than configuration flags alone."""
    role = "Custom"
    absolute = True
    previous_e = 0.0
    extrusion = Counter()
    moves = Counter()
    estimates = []
    effective = {}
    position = {"X": 0.0, "Y": 0.0, "Z": 0.0}
    max_bridge_move = 0.0
    max_bridge_height = None
    xy_min = [math.inf, math.inf]
    xy_max = [-math.inf, -math.inf]
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(";TYPE:"):
            role = line[6:].strip()
        if line.startswith("; estimated printing time") or line.startswith("; filament used [cm3]"):
            estimates.append(line[2:])
        if line.startswith("; ") and " = " in line:
            key, value = line[2:].split(" = ", 1)
            if key in ("support_material", "support_material_auto", "support_material_threshold", "layer_height"):
                effective[key] = value
        code = line.split(";", 1)[0].strip()
        if code == "M82":
            absolute = True
        elif code == "M83":
            absolute = False
        fields = {key: float(value) for key, value in re.findall(r"([XYZE])(-?[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", code)}
        if code.startswith("G92") and "E" in fields:
            previous_e = fields["E"]
        elif re.match(r"G[01](?:\s|$)", code):
            # These Prusa diagnostic Gcodes use absolute XYZ positioning (G90).
            new_position = {axis: fields.get(axis, value) for axis, value in position.items()}
            if "E" in fields:
                delta = fields["E"] - previous_e if absolute else fields["E"]
                previous_e = fields["E"] if absolute else previous_e
                if delta > 0 and ("X" in fields or "Y" in fields):
                    extrusion[role] += delta
                    moves[role] += 1
                    for index, axis in enumerate(("X", "Y")):
                        xy_min[index] = min(xy_min[index], position[axis], new_position[axis])
                        xy_max[index] = max(xy_max[index], position[axis], new_position[axis])
                    if "bridge" in role.lower():
                        distance = math.hypot(new_position["X"] - position["X"], new_position["Y"] - position["Y"])
                        if distance > max_bridge_move:
                            max_bridge_move, max_bridge_height = distance, new_position["Z"]
            position = new_position
    support = sum(value for key, value in extrusion.items() if key.startswith("Support"))
    bridges = sum(value for key, value in extrusion.items() if "bridge" in key.lower())
    return {
        "extruded_filament_mm_by_role": dict(extrusion),
        "extrusion_moves_by_role": dict(moves),
        "support_extrusion_mm": support,
        "bridge_extrusion_mm": bridges,
        "support_volume_mm3": support * math.pi * (1.75 / 2) ** 2,
        "max_bridge_xy_move_mm": max_bridge_move,
        "max_bridge_move_at_z_mm": max_bridge_height,
        "bridge_measurement": "Longest positive XY bridge-role extrusion move, including anchors; not a measurement of unsupported span or physical sag",
        "extrusion_center_bounds_xy_mm": [xy_min, xy_max],
        "effective_settings": effective,
        "diagnostic_profile_estimates": estimates,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--openscad",
        type=Path,
        default=default_tool("OPENSCAD_EXECUTABLE", ("openscad.com", "openscad")),
        help="OpenSCAD executable; defaults to OPENSCAD_EXECUTABLE or PATH",
    )
    parser.add_argument(
        "--slicer",
        type=Path,
        default=default_tool("PRUSASLICER_EXECUTABLE", ("prusa-slicer-console.exe", "prusa-slicer")),
        help="PrusaSlicer console executable; defaults to PRUSASLICER_EXECUTABLE or PATH",
    )
    args = parser.parse_args()
    for tool in (args.openscad, args.slicer):
        if not tool.is_file():
            raise FileNotFoundError(f"Required tool missing: {tool}; provide its path on the command line")
    out = HERE / "exports"
    work = HERE / "verification"
    (out / "parts").mkdir(parents=True, exist_ok=True)
    (work / "slices").mkdir(parents=True, exist_ok=True)

    def render(selector, target, defines=(), image=False, camera="0,0,0,65,0,30,500"):
        command = [args.openscad, "--backend", "Manifold", "--hardwarnings", "-o", target, "-D", f'part="{selector}"']
        for define in defines:
            command.extend(["-D", define])
        command.extend(["--render", "--imgsize=1100,850", "--autocenter", "--viewall", f"--camera={camera}"] if image else ["--export-format", "binstl"])
        command.append(HERE / "accordion.scad")
        output = run(command)
        match = re.search(r"ECHO: leaf_count = (\d+), pin_count = (\d+), width_mm = ([\d.]+), male_length_mm = ([\d.]+), extension_count = (\d+), extension_length_mm = ([\d.]+)", output)
        if not match:
            raise RuntimeError(f"Missing assembly dimensions in OpenSCAD output: {output}")
        config = dict(zip(
            ("leaf_count", "pin_count", "width_mm", "male_length_mm", "extension_count", "extension_length_mm"),
            (int(match[1]), int(match[2]), float(match[3]), float(match[4]), int(match[5]), float(match[6])),
        ))
        report["configurations"][str(config["width_mm"])] = config
        if selector == "display" and not image and not defines:
            report["configuration"] = config
        return target

    def slice_model(path, name, supports=True):
        target = work / "slices" / f"{name}.gcode"
        command = [args.slicer, "--datadir", work / "slicer-data", "--load", HERE / "verification.ini"]
        if not supports:
            command.append("--no-support-material")
        log = run(command + ["--export-gcode", "--dont-arrange", "--center", "125,125", "--output", target, path])
        target.with_suffix(".log").write_text(log, encoding="utf-8")
        result = gcode_roles(target)
        xy_min, xy_max = result["extrusion_center_bounds_xy_mm"]
        result["extrusion_centers_within_250_bed"] = all(0 <= a <= b <= 250 for a, b in zip(xy_min, xy_max))
        # Automatic supports are a diagnostic and can extend beyond a 250 mm part.
        # Only the support-disabled path is proposed for this print orientation.
        if not supports:
            assert result["extrusion_centers_within_250_bed"], (name, "extrusion outside bed", xy_min, xy_max)
        assert result["effective_settings"]["support_material"] == str(int(supports))
        assert result["effective_settings"]["support_material_auto"] == "1"
        result.update({"input_sha256": sha256(path), "gcode_sha256": sha256(target),
                       "profile_sha256": sha256(HERE / "verification.ini"),
                       "cli_overrides": [] if supports else ["--no-support-material"],
                       "warnings": [x for x in log.splitlines() if "warning" in x.lower()],
                       "stability_issues": [issue for issue in (
                           "Floating bridge anchors", "Low bed adhesion", "Long bridging extrusions",
                           "Collapsing overhang") if issue in log]})
        return result

    report = {
        "version": "4.2",
        "scope": "V4.2 clipped supports and concave V rotor in assembly and print; 250 mm bed, hinge/thread/PIP geometry and offline slicer diagnostics",
        "sources_sha256": {name: sha256(HERE / name) for name in ("accordion.scad", "threads.scad", "check_layers.py", "verification.ini", "build.py", "tests/test_dimensions.py", "tests/test_hinge_wall.py", "tests/test_v42_assembly.py", "tests/test_split_rod.py", "tests/test_male_bore.py", "tests/test_support_spine.py", "tests/test_right_rotor_opening.py", "tests/test_support_trapezoid.py", "tests/test_female_body.py")},
        "tools": {"openscad": run([args.openscad, "--version"]).strip(),
                  "slicer": run([args.slicer, "--help"]).splitlines()[0],
                  "slicer_console_sha256": sha256(args.slicer)},
        "parts": {}, "hardware": {}, "layers": {}, "slicing": {}, "no_support_slicing": {}, "probes": {},
        "configurations": {}, "variant_hardware": {}, "hinge_walls": {},
        "limitation": "Circular roofs require short bridges. Disabling supports and obtaining Gcode is not physical support-free validation; automatic-support diagnostics are retained separately.",
        "physical_print_verified": False, "load_verified": False, "fusion_verified": False,
        "bed_mm": [250, 250],
        "bed_limit": "CAD envelope and diagnostic slicing only; 250 mm parts leave no room for external brim/skirt",
        "rod_joint": "Two horizontally printed parts per extension: closed socket with >=2 mm floor and shaft cut into the core; assembled collar touches the body face and merges their CSG union",
    }
    for name, (selector, count) in PARTS.items():
        path = render(selector, out / f"{name}.stl")
        info = inspect_mesh(path)
        assert info["components"] == count, (name, info)
        assert abs(info["bounds_mm"][0][2]) < 0.001, (name, "not on bed")
        assert all(b - a <= 250.01 for a, b in zip(*info["bounds_mm"])), name
        info["sha256"] = sha256(path)
        info["size_mm"] = [b - a for a, b in zip(*info["bounds_mm"])]
        report["parts"][name] = info
        if name.startswith("parts/"):
            report["layers"][name] = [inspect_layers(path, step) for step in (0.2, 0.28)]
            if name == "parts/hinge-pin":
                assert all(x["passed"] for x in report["layers"][name]), report["layers"][name]
        sliced = slice_model(path, Path(name).name)
        report["slicing"][name] = sliced
        no_support = slice_model(path, Path(name).name + "-no-support", supports=False)
        report["no_support_slicing"][name] = no_support
        assert no_support["support_extrusion_mm"] < 1e-6
        # Full bridge moves include anchors, so bore diameter cannot bound their length.
        print(f'{name}: {count} solids; auto support={sliced["support_volume_mm3"]:.3f} mm3; support-disabled longest bridge={no_support["max_bridge_xy_move_mm"]:.3f} mm', flush=True)

    for name, (selector, count) in HARDWARE_PARTS.items():
        path = render(selector, out / f"{name}.stl")
        info = inspect_mesh(path)
        assert info["components"] == count, (name, info)
        if name != "parts/right-support":  # Standalone right support is an assembly reference.
            assert abs(info["bounds_mm"][0][2]) < 0.001, (name, "not on bed")
            assert all(b - a <= 250.01 for a, b in zip(*info["bounds_mm"])), (name, "exceeds 250 mm bed", info)
        info["size_mm"] = [b - a for a, b in zip(*info["bounds_mm"])]
        report["hardware"][name] = info | {"sha256": sha256(path), "slicer_verified": False, "load_verified": False}
        if name != "parts/right-support":
            no_support = slice_model(path, Path(name).name + "-no-support", supports=False)
            report["no_support_slicing"][name] = no_support
            assert no_support["support_extrusion_mm"] < 1e-6
            report["hardware"][name]["slicer_verified"] = True
        print(f"{name}: {count} closed solids; physical fit/load unverified", flush=True)

    for name, part, section_y, center in (
        ("leaf-left", "leaf", 12.345, (4.6, 4.5)),
        ("leaf-right", "leaf", 37.345, (46.6, 4.5)),
        ("left-support", "left-support", 37.345, (10, 38)),
        ("right-pip", "right-pip", 12.345, (140, 47.3)),
    ):
        path = out / "parts" / f"{part}.stl"
        info = measure_wall(path, section_y, center)
        assert info["wall_mm"] >= 2 - 1e-4, (name, "hinge wall below 2 mm", info)
        assert abs(info["bore_radius_max_mm"] - 2.3) < 1e-4, (name, "bore changed", info)
        report["hinge_walls"][name] = info | {"sha256": sha256(path), "section_y_mm": section_y,
                                                   "bore_center_xz_mm": center}
        print(f'{name}: minimum hinge wall={info["wall_mm"]:.6f} mm', flush=True)

    def probe(selector, defines=(), expected="clear"):
        suffix = "-".join(str(x).replace("=", "-") for x in defines)
        path = render(selector, work / f"{selector}-{suffix}.stl", defines)
        volume = signed_volume(triangles_from(path)) - 1
        assert abs(volume) < 0.01 if expected == "clear" else volume > 0.01, (selector, defines, volume)
        report["probes"][f"{selector} {suffix}".strip()] = {"extra_volume_mm3": volume, "expected": expected}

    for width in (430, 500, 501, 550, 565, 565.5, 566, 620, 637.5, 770, 770.25, 771, 975, 975.125, 976, 1000):
        for selector in ("joint-collision", "hardware-collision", "thread-collision"):
            probe(selector, [f"W={width}"])
        for selector, name in (("print-left-support", "left-support"), ("print-rod-extension", "rod-extension")):
            path = render(selector, work / f"{name}-W{width}.stl", [f"W={width}"])
            info = inspect_mesh(path)
            expected = 2 if name == "rod-extension" else 1
            assert info["components"] == expected, (width, name, info)
            assert all(b - a <= 250.01 for a, b in zip(*info["bounds_mm"])), (width, name, "exceeds bed", info)
            report["variant_hardware"][f"{name} W{width}"] = info | {"sha256": sha256(path)}
        print(f"W={width}: chain/hinge collisions clear and hardware fits 250 mm", flush=True)

    for width in (430, 550, 1000):
        for angle in range(0, 360, 45):
            probe("pip-rotation-check", [f"W={width}", f"joint_angle={angle}"])
        for selector in ("pip-pull-left", "pip-pull-right"):
            probe(selector, [f"W={width}"], expected="blocked")

    # These poses retain W=620 and every printed part; only the clamp is tightened.
    report["fixed_kit_motion"] = {
        "printed_width_mm": 620, "travel_range_mm": [0, 75],
        "poses_mm": list(range(0, 76, 5)) + [37.3],
        "method": "Discrete CSG intersections, not a dynamics solver or physical motion test",
    }
    for travel in report["fixed_kit_motion"]["poses_mm"]:
        for selector in ("joint-collision", "hardware-collision", "thread-collision"):
            probe(selector, ["W=620", f"clamp_travel={travel}"])
        print(f"Fixed W620 kit: travel={travel} mm, hinge/hardware/thread checks clear", flush=True)
    for angle in range(0, 360, 5):
        probe("pip-rotation-check", ["W=620", f"joint_angle={angle}"])

    for selector in ("thread-phase-probe", "chain-phase-probe"):
        probe(selector, ["W=1000"], expected="blocked")
    for width in (430, 620, 1000):
        probe("rod-joint-collision", [f"W={width}"])
        for selector in ("rod-joint-stop-probe", "rod-joint-phase-probe"):
            probe(selector, [f"W={width}"], expected="blocked")

    # Positive control: a closed T-shaped part that genuinely requires support.
    control_source = work / "unsupported-control.scad"
    control_source.write_text("cube([3,3,3]);translate([-3,-3,3])cube([9,9,1]);\n")
    control = work / "unsupported-control.stl"
    run([args.openscad, "--backend", "Manifold", "--hardwarnings", "--export-format", "binstl", "-o", control, control_source])
    control_layers = inspect_layers(control)
    control_slice = slice_model(control, "unsupported-control")
    assert not control_layers["passed"]
    assert control_slice["support_extrusion_mm"] > 0
    report["positive_control"] = {"layers": control_layers, "slicing": control_slice,
                                  "result": "both geometric gate and automatic slicer detect unsupported control"}

    for selector, name, camera in (
        ("print-leaf", "leaf", "0,0,0,35,0,25,500"),
        ("print-fit-kit", "fit-kit", "0,0,0,35,0,25,500"),
        ("three-leaves", "three-leaves", "0,0,0,65,0,30,500"),
        ("display", "assembly", "0,0,0,65,0,30,1100"),
        ("display", "assembly-rear", "0,0,0,65,0,210,1100"),
        ("leaf-section", "leaf-section", "0,0,0,90,0,0,100"),
    ):
        render(selector, out / f"{name}.png", image=True, camera=camera)
    run([args.slicer, "--datadir", work / "slicer-data", "--load", HERE / "verification.ini",
         "--no-support-material", "--export-3mf", "--dont-arrange", "--center", "125,125",
         "--output", out / "leaf.3mf", out / "parts" / "leaf.stl"])
    assembly_path = render("display", out / "accordion.stl")
    assembly_info = inspect_mesh(assembly_path)
    config = report["configuration"]
    assert assembly_info["components"] == config["leaf_count"] + config["pin_count"] + config["extension_count"] + 3, assembly_info
    report["assembly"] = assembly_info | {"sha256": sha256(assembly_path)}
    report["print_quantities"] = {
        "parts/leaf.stl": config["leaf_count"], "parts/hinge-pin.stl": config["pin_count"],
        "parts/left-support.stl": 1, "parts/right-pip.stl": 1,
        "parts/rod-socket.stl": config["extension_count"],
        "parts/rod-shaft.stl": config["extension_count"],
    }
    report["physical_part_count"] = config["leaf_count"] + config["pin_count"] + 3 + 2 * config["extension_count"]
    report["rod_print_alternative"] = "Print rod-extension.stl extension_count times instead of separate socket/shaft files; do not print both inventories"
    assert abs(assembly_info["bounds_mm"][1][0] - config["width_mm"]) < 0.001, assembly_info
    tightened_path = render("display", out / "assembly-tightened.stl", ["W=620", "clamp_travel=75"])
    tightened_info = inspect_mesh(tightened_path)
    assert tightened_info["components"] == 38, tightened_info
    assert abs(tightened_info["bounds_mm"][1][0] - 545) < 0.001, tightened_info
    report["fixed_kit_motion"]["tightened_assembly"] = tightened_info | {"sha256": sha256(tightened_path)}
    render("display", out / "assembly-tightened.png", ["W=620", "clamp_travel=75"], image=True,
           camera="0,0,0,65,0,30,1100")
    large_path = render("display", work / "assembly-W1000.stl", ["W=1000"])
    large_info = inspect_mesh(large_path)
    config = report["configurations"]["1000.0"]
    assert large_info["components"] == config["leaf_count"] + config["pin_count"] + config["extension_count"] + 3, large_info
    assert abs(large_info["bounds_mm"][1][0] - 1000) < 0.001, large_info
    report["assembly_W1000"] = large_info | {"sha256": sha256(large_path)}
    render("display", work / "assembly-W1000.png", ["W=1000"], image=True, camera="0,0,0,65,0,30,1800")
    render("display", work / "assembly-W1000-rear.png", ["W=1000"], image=True, camera="0,0,0,65,0,210,1800")
    (HERE / "docs" / "parts").mkdir(parents=True, exist_ok=True)
    for selector, name in (("print-leaf", "leaf"), ("print-hinge-pin", "hinge-pin"),
                           ("print-left-support", "left-support"), ("female", "female"),
                           ("right-support", "right-support"), ("print-test-male", "test-male"),
                           ("print-test-female", "test-female"), ("print-pip-coupon", "pip-coupon"),
                           ("print-rod-extension", "rod-extension"),
                           ("print-rod-socket", "rod-socket"),
                           ("print-rod-shaft", "rod-shaft"),
                           ("rod-extension", "rod-extension-assembled")):
        render(selector, HERE / "docs" / "parts" / f"{name}.png", image=True)
    baseline = inspect_mesh(HERE / "archive" / "v4" / "exports" / "parts" / "leaf.stl")
    report["comparison"] = {
        "v4_leaf_sha256": sha256(HERE / "archive" / "v4" / "exports" / "parts" / "leaf.stl"),
        "v4_leaf_volume_mm3": baseline["volume_mm3"],
        "v41_one_piece_volume_mm3": report["parts"]["parts/leaf"]["volume_mm3"],
        "cad_volume_ratio_to_v4": report["parts"]["parts/leaf"]["volume_mm3"] / baseline["volume_mm3"],
        "v4_full_outer_bearing_mm": 6.373107562779287,
        "v41_full_bearing_mm": 24.7,
    }
    report["documentation_images_sha256"] = {p.name: sha256(p) for p in (HERE / "docs" / "parts").glob("*.png")}
    assert all(sha256(HERE / name) == digest for name, digest in report["sources_sha256"].items()), "Source changed during build; rerun before publishing the audit"
    report["delivered_sha256"] = {str(p.relative_to(out)).replace("\\", "/"): sha256(p)
                                  for p in out.rglob("*") if p.is_file() and p.name != "audit.json"}
    (out / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("V4.2 parametric build, collisions, circular-roof diagnostics and support-disabled slices complete.", flush=True)


if __name__ == "__main__":
    main()
