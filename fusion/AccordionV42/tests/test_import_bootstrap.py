"""Regression for loading the Fusion entrypoint directly by file path."""

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[3]
PACKAGE_DIR = PROJECT_DIR / "fusion" / "AccordionV42"
ENTRYPOINT = PACKAGE_DIR / "AccordionV42.py"


class ImportBootstrapTests(unittest.TestCase):
    def test_isolated_file_load_resolves_sibling_modules(self):
        script = r"""
import importlib.util
import pathlib
import sys
import types

entrypoint = pathlib.Path(sys.argv[1]).resolve()
package = entrypoint.parent
foreign = types.ModuleType("NativeThreads")
foreign.__file__ = str(package.parent / "Accordion" / "NativeThreads.py")
if sys.argv[2] in ("stale", "mixed"):
    sys.path.insert(0, str(package.parent))
    sys.path.insert(1, str(package))
    sys.modules["NativeThreads"] = foreign
if sys.argv[2] == "mixed":
    contract = types.ModuleType("Contract")
    contract.__file__ = str(package.parent / "Other" / "Contract.py")
    geometry = types.ModuleType("Geometry")
    geometry.__file__ = str(package / "Geometry.py")
    geometry.Contract = contract
    sys.modules["Contract"] = contract
    sys.modules["Geometry"] = geometry

spec = importlib.util.spec_from_file_location("fusion_entrypoint", entrypoint)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

for name in ("Contract", "Geometry", "NativeThreads"):
    sibling = getattr(module, name)
    assert pathlib.Path(sibling.__file__).resolve().parent == package, (
        name, sibling.__file__, package
    )
assert module.Geometry.Contract is module.Contract
assert module.NativeThreads is not foreign
assert sys.path[0] == str(package)
"""
        for scenario in ("clean", "stale", "mixed"):
            with self.subTest(scenario=scenario):
                result = subprocess.run(
                    [sys.executable, "-I", "-c", script, str(ENTRYPOINT), scenario],
                    cwd=Path(sys.executable).parent,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=f"isolated import failed:\n{result.stdout}\n{result.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
