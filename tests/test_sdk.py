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
