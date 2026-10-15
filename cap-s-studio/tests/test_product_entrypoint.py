from __future__ import annotations

import sys
import types
import unittest
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from cap_s import launcher


class ProductEntrypointTests(unittest.TestCase):
    def test_source_package_contains_the_dedicated_cap_s_entrypoint(self) -> None:
        from build_portable import make_source_zip

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            examples = output / "ExampleData"
            examples.mkdir()
            path = make_source_zip(output, examples)
            with zipfile.ZipFile(path) as archive:
                self.assertIn("CapSStudio/main.py", archive.namelist())
                self.assertIn("CapSStudio/cap_s/gui.py", archive.namelist())
                self.assertIn(b"from cap_s.launcher import run", archive.read("CapSStudio/main.py"))
                self.assertFalse(any("skin_analysis/" in name for name in archive.namelist()))

    def test_launches_the_cap_s_error_band_app_without_a_classic_gui(self) -> None:
        gui = types.ModuleType("cap_s.gui")
        gui.ErrorBandViewerApp = type("ErrorBandViewerApp", (), {})
        with patch.dict(sys.modules, {"cap_s.gui": gui}):
            self.assertIs(launcher._load_app_class(), gui.ErrorBandViewerApp)

    def test_legacy_argument_cannot_switch_the_cap_s_product_to_skin_analysis(self) -> None:
        gui = types.ModuleType("cap_s.gui")
        gui.ErrorBandViewerApp = type("ErrorBandViewerApp", (), {})
        with patch.dict(sys.modules, {"cap_s.gui": gui}), patch.object(sys, "argv", ["main.py", "--classic"]):
            self.assertIs(launcher._load_app_class(), gui.ErrorBandViewerApp)


if __name__ == "__main__":
    unittest.main()
