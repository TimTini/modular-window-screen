"""Read-only geometric layer sampling for one binary STL.

This is a cross-section check, not a slicer or physical printability proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
PROJECT = Path(__file__).resolve().parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
from audit import triangles_from

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def _section(triangles: np.ndarray, normals: np.ndarray, height: float) -> np.ndarray:
    z = triangles[:, :, 2]
    segments = []
    for triangle, normal in zip(triangles[(z.min(1) < height) & (z.max(1) > height)],
                                normals[(z.min(1) < height) & (z.max(1) > height)]):
        points = []
        for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]),
                     (triangle[2], triangle[0])):
            da, db = a[2] - height, b[2] - height
            if da * db < 0:
                points.append((a + (b - a) * (-da) / (db - da))[:2])
        if len(points) == 2:
            points = np.asarray(points)
            if np.dot(points[1] - points[0], [-normal[1], normal[0]]) < 0:
                points = points[::-1]
            segments.append(points)
    return np.asarray(segments, dtype=float).reshape((-1, 2, 2))

def _find(parent, value: int) -> int:
    while parent[value] != value:
        parent[value] = parent[parent[value]]
        value = parent[value]
    return value

def _contour_counts(segments: np.ndarray) -> tuple[int, int]:
    if not len(segments):
        return 0, 0
    vertices, inverse = np.unique(np.round(segments.reshape(-1, 2), 5), axis=0,
                                  return_inverse=True)
    edges = inverse.reshape(-1, 2)
    parent = list(range(len(vertices)))
    for a, b in edges:
        parent[_find(parent, int(a))] = _find(parent, int(b))
    areas = {}
    for (a, b), (start, end) in zip(edges, segments):
        root = _find(parent, int(a))
        areas[root] = areas.get(root, 0.0) + float(start[0] * end[1] - start[1] * end[0]) / 2.0
    area_limit = max(1e-8, float(np.ptp(vertices, axis=0).prod()) * 1e-9)
    contours = sum(abs(area) > area_limit for area in areas.values())
    materials = sum(area > area_limit for area in areas.values())
    return int(contours), int(materials)

def _inside(points: np.ndarray, segments: np.ndarray) -> np.ndarray:
    if not len(points) or not len(segments):
        return np.zeros(len(points), dtype=bool)
    start, end = segments[:, 0], segments[:, 1]
    px, py = points[:, 0, None], points[:, 1, None]
    crossing = ((start[None, :, 1] > py) != (end[None, :, 1] > py))
    denominator = end[:, 1] - start[:, 1]
    x_cross = start[:, 0] + np.divide(
        (end[:, 0] - start[:, 0]) * (py - start[:, 1]), denominator,
        out=np.zeros((len(points), len(segments))), where=np.abs(denominator) > 1e-12)
    return np.logical_xor.reduce(crossing & (px < x_cross), axis=1)

def _distance_to_segments(points: np.ndarray, segments: np.ndarray) -> np.ndarray:
    start, end = segments[:, 0], segments[:, 1]
    direction = end - start
    length2 = np.einsum("ij,ij->i", direction, direction)
    delta = points[:, None, :] - start[None, :, :]
    fraction = np.clip(np.divide(np.einsum("pij,ij->pi", delta, direction), length2,
                                 out=np.zeros((len(points), len(segments))),
                                 where=length2 > 1e-18), 0, 1)
    nearest = delta - fraction[:, :, None] * direction[None, :, :]
    return np.sqrt(np.einsum("pij,pij->pi", nearest, nearest)).min(axis=1)

def _growth(previous: np.ndarray, current: np.ndarray) -> tuple[float, list[float] | None]:
    if not len(previous) or not len(current):
        return 0.0, None
    points = np.concatenate((current.reshape(-1, 2), current.mean(axis=1)))
    outside = points[~_inside(points, previous)]
    if not len(outside):
        return 0.0, None
    distances = _distance_to_segments(outside, previous)
    index = int(np.argmax(distances))
    return float(distances[index]), outside[index].tolist()

def inspect_layers(path, layer_height: float = 0.2) -> dict:
    """Return a JSON-serializable geometric report for one binary STL."""
    source = Path(path).resolve()
    if layer_height <= 0:
        raise ValueError("layer_height must be positive")
    triangles = triangles_from(source)
    normals = np.cross(triangles[:, 1] - triangles[:, 0],
                       triangles[:, 2] - triangles[:, 0])
    z_min, z_max = triangles[:, :, 2].min(), triangles[:, :, 2].max()
    span = float(z_max - z_min)
    offset = min(1e-5, max(1e-7, span * 1e-7))
    vertex_z = triangles[:, :, 2].reshape(-1)
    plane_count = max(1, int(np.ceil(span / layer_height))) if span > offset else 0
    heights = []
    for nominal in z_min + np.arange(plane_count) * layer_height:
        height = float(nominal + offset)
        while np.any(np.isclose(vertex_z, height, rtol=0, atol=offset * 0.5)):
            height += offset
        if height < z_max - offset * 0.5:
            heights.append(height)

    previous = np.empty((0, 2, 2), dtype=float)
    contours, materials, max_growth = [], [], 0.0
    max_height, max_point = None, None
    for height in heights:
        current = _section(triangles, normals, height)
        contour_count, material_count = _contour_counts(current)
        contours.append(contour_count)
        materials.append(material_count)
        growth, point = _growth(previous, current)
        if growth > max_growth:
            max_growth, max_height, max_point = growth, height, point
        previous = current

    growth_limit = float(layer_height + 0.005)
    report = {
        "layercount": len(heights),
        "sampled_layer_height_mm": float(layer_height),
        "sample_plane_offset_mm": offset,
        "min_geometric_contours": min(contours, default=0),
        "max_geometric_contours": max(contours, default=0),
        "min_material_components": min(materials, default=0),
        "max_material_components": max(materials, default=0),
        "geometric_contour_counts": sorted(set(contours)),
        "material_component_counts": sorted(set(materials)),
        "max_sampled_boundary_growth_mm": max_growth,
        "max_growth_height_mm": max_height,
        "max_growth_xy_mm": max_point,
        "growth_limit_mm": growth_limit,
        "passed": bool(max_growth <= growth_limit),
        "sourceSTLsha256": _sha256(source),
        "sampling_limitation": (
            "Cross-sections sample endpoints and segment midpoints only; this is not "
            "proof of slicer behavior, support requirements, or physical printability."
        ),
    }
    return report

def main() -> int:
    parser = argparse.ArgumentParser(description="Sample geometric layers of one binary STL")
    parser.add_argument("path", type=Path)
    parser.add_argument("--layer-height", type=float, default=0.2)
    args = parser.parse_args()
    report = inspect_layers(args.path, args.layer_height)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
