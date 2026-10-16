import sys
import tempfile
import unittest
from pathlib import Path

from traductor import sdk


def make_sdk(parent: Path, name: str) -> Path:
    d = parent / name
    d.mkdir(parents=True)
    (d / ("renpy.exe" if sys.platform == "win32" else "renpy.sh")).write_text("", encoding="utf-8")
    return d


class SdkDetectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_sdk_at_two_levels_newest_first(self):
        old = make_sdk(self.root, "renpy-7.6.3-sdk")
        new = make_sdk(self.root / "renpy", "renpy-8.5.3-sdk")  # como D:\...\Downloads\renpy\renpy-8.5.3-sdk
        make_sdk(self.root, "otra-cosa")  # no empieza por renpy
        (self.root / "renpy-vacio").mkdir()  # sin renpy.exe
        found = sdk.autodetect([self.root], extra_env=False)
        self.assertEqual(found, [new, old])

    def test_version_order_is_numeric_not_alphabetic(self):
        a = make_sdk(self.root, "renpy-8.10.0-sdk")
        b = make_sdk(self.root, "renpy-8.9.0-sdk")
        self.assertEqual(sdk.autodetect([self.root], extra_env=False), [a, b])

    def test_nothing_found(self):
        self.assertEqual(sdk.autodetect([self.root], extra_env=False), [])
        self.assertEqual(sdk.autodetect([self.root / "no-existe"], extra_env=False), [])

    def test_env_variable(self):
        import os
        d = make_sdk(self.root, "mi-sdk")
        os.environ["RENPY_SDK"] = str(d)
        try:
            self.assertEqual(sdk.autodetect([], extra_env=True), [d])
        finally:
            del os.environ["RENPY_SDK"]

    def test_default_roots_do_not_crash(self):
        self.assertIsInstance(sdk.autodetect(), list)


if __name__ == "__main__":
    unittest.main()


class SandboxTests(unittest.TestCase):
    def test_isolated_env_points_every_save_location_at_the_sandbox(self):
        import os
        import tempfile

        from traductor import sdk

        with tempfile.TemporaryDirectory() as d:
            env = sdk.isolated_env(Path(d) / "guardados")
            for key in ("APPDATA", "HOME", "XDG_DATA_HOME"):
                self.assertEqual(env[key], str(Path(d) / "guardados"))
            self.assertTrue((Path(d) / "guardados").is_dir())
            self.assertEqual(env.get("PATH"), os.environ.get("PATH"))  # lo demás del entorno se conserva

    def test_run_translate_launches_the_sdk_with_the_sandbox(self):
        import tempfile
        from unittest import mock

        from traductor import sdk

        class FakeProc:
            stdout = iter(())
            returncode = 0

            def wait(self, timeout=None):
                return 0

            def poll(self):
                return 0

            def kill(self):
                pass

        with tempfile.TemporaryDirectory() as d, mock.patch.object(sdk.subprocess, "Popen", return_value=FakeProc()) as popen:
            try:
                sdk.run_translate(Path("renpy.exe"), Path(d) / "juego", "Spanish", sandbox=Path(d) / "box")
            except Exception:
                pass  # solo interesa cómo se lanzó
        env = popen.call_args.kwargs["env"]
        self.assertEqual(env["APPDATA"], str(Path(d) / "box"))
