import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from traductor import decompile, settings

ROOT = Path(__file__).resolve().parent.parent


class PackagingTests(unittest.TestCase):
    def test_unrpyc_command_normal_and_frozen(self):
        unrpyc, target = Path("u/unrpyc.py"), Path("t")
        normal = decompile.unrpyc_command(unrpyc, target)
        self.assertEqual(normal, [sys.executable, str(unrpyc), str(target)])
        with mock.patch.object(decompile, "FROZEN", True):
            frozen = decompile.unrpyc_command(unrpyc, target)
        self.assertEqual(frozen, [sys.executable, "--unrpyc-run", str(unrpyc), str(target)])

    def test_default_unrpyc_location_is_the_bundled_one(self):
        self.assertEqual(decompile.DEFAULT_LOCATIONS[0], settings.RESOURCE_DIR / "vendor" / "unrpyc")
        self.assertIsNotNone(decompile.find_unrpyc(""), "vendor/unrpyc debe venir con el proyecto")

    def test_window_icon_ships_with_the_app(self):
        icon = settings.RESOURCE_DIR / "assets" / "icon.ico"
        self.assertTrue(icon.is_file(), "assets/icon.ico debe existir: la ventana y el .exe lo usan")
        self.assertEqual(icon.read_bytes()[:4], b"\x00\x00\x01\x00")  # cabecera de un .ico válido

    def test_main_unrpyc_run_flag_runs_the_script(self):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "fake_unrpyc.py"
            script.write_text(
                "import sys\nprint('ARGS', sys.argv[1:])\nprint('NAME', __name__)\n", encoding="utf-8"
            )
            out = subprocess.run(
                [sys.executable, str(ROOT / "main.py"), "--unrpyc-run", str(script), "carpeta"],
                capture_output=True, text=True, timeout=60,
            )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("ARGS ['carpeta']", out.stdout)
        self.assertIn("NAME __main__", out.stdout)


if __name__ == "__main__":
    unittest.main()
