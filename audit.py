"""Audit binary STL solids using the bundled numpy, without installing packages."""
import json
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def triangles_from(path):
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 80)[0]
    assert len(data) == 84 + count * 50, f'{path.name}: invalid binary STL'
    dtype = np.dtype([('normal', '<f4', 3), ('vertices', '<f4', (3, 3)), ('attr', '<u2')])
    return np.frombuffer(data, dtype=dtype, offset=84)['vertices'].astype(float)


def signed_volume(triangles):
    return float(np.einsum('ij,ij->i', triangles[:, 0],
                          np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6)


def inspect(path):
    triangles = triangles_from(path)
    vertices, inverse = np.unique(np.round(triangles.reshape(-1, 3), 5), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    _, edge_inverse, counts = np.unique(np.sort(edges, axis=1), axis=0,
                                        return_inverse=True, return_counts=True)
    assert np.all(counts == 2), f'{path.name}: open/nonmanifold edges'
    direction = np.where(edges[:, 0] < edges[:, 1], 1, -1)
    assert np.all(np.bincount(edge_inverse, weights=direction) == 0), f'{path.name}: winding'
    parent = list(range(len(vertices)))

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for a, b in edges:
        parent[find(int(a))] = find(int(b))
    components = len({find(i) for i in range(len(vertices))})
    volume = signed_volume(triangles)
    assert volume > 0, f'{path.name}: nonpositive volume'
    return {'bounds_mm': [vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()],
            'components': components, 'triangles': len(triangles), 'volume_mm3': volume,
            'watertight': True, 'winding_consistent': True}


def main():
    manifest = json.loads((ROOT / 'exports/parts.json').read_text(encoding='utf-8-sig'))
    report = {}
    for part in manifest['parts']:
        result = inspect(ROOT / 'exports' / (part['name'] + '.stl'))
        assert result['components'] == 1, f"{part['name']}: expected one connected solid"
        np.testing.assert_allclose(result['bounds_mm'][0], [0, 0, 0], atol=0.002)
        np.testing.assert_allclose(result['bounds_mm'][1], part['size_mm'], atol=0.002)
        assert max(part['size_mm'][:2]) <= manifest['max_module_length_mm'], 'print bed envelope'
        report[part['name']] = result
    # Coplanar mate faces have zero volume but OpenSCAD exports them as surfaces.
    # Printable parts above must be watertight; this witness is not a print part.
    fit_layout = inspect(ROOT / 'exports/fit-layout.stl')
    assert fit_layout['components'] == 9, 'Fit plate must contain 9 separate printed pieces'
    np.testing.assert_allclose(fit_layout['bounds_mm'], [[0,0,0],[177,189.5,36]], atol=0.002)
    report['fit-layout'] = fit_layout
    collision_volume = signed_volume(triangles_from(ROOT / 'exports/collision-check.stl'))
    np.testing.assert_allclose(collision_volume, 1, atol=0.0001,
                               err_msg='Unexpected interference beyond the 1 mm3 sentinel')
    report['collision-check'] = {'witness_volume_mm3': collision_volume,
                                 'additional_interference_mm3': collision_volume - 1,
                                 'coplanar_contact_surfaces_allowed': True}
    report['physical_print_verified'] = False
    report['window_fit_verified'] = False
    (ROOT / 'exports/audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Verified {len(manifest['parts'])} single-solid parts, 9-piece fit plate; collision witness = 1 mm3.")


if __name__ == '__main__':
    main()
