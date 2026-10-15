import json
import sys
import tempfile
import unittest
from pathlib import Path

from traductor import keystore, settings

KEY = "test-key-not-a-real-key-0123456789"


class KeystoreTests(unittest.TestCase):
    def test_plain_values_pass_through(self):
        self.assertEqual(keystore.protect(""), "")
        self.assertEqual(keystore.unprotect(""), "")
        self.assertEqual(keystore.unprotect("clave-sin-cifrar"), "clave-sin-cifrar")  # versión anterior

    @unittest.skipUnless(sys.platform == "win32", "DPAPI solo existe en Windows")
    def test_roundtrip_and_no_plaintext(self):
        blob = keystore.protect(KEY)
        self.assertTrue(blob.startswith(keystore.PREFIX))
        self.assertNotIn(KEY, blob)
        self.assertEqual(keystore.unprotect(blob), KEY)
        self.assertEqual(keystore.protect(blob), blob)  # no se cifra dos veces

    @unittest.skipUnless(sys.platform == "win32", "DPAPI solo existe en Windows")
    def test_tampered_blob_yields_empty_key(self):
        blob = keystore.protect(KEY)
        self.assertEqual(keystore.unprotect(blob[:-6] + "AAAAAA"), "")
        self.assertEqual(keystore.unprotect(keystore.PREFIX + "no-es-base64!!"), "")


class SettingsEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (settings.SETTINGS_FILE, settings.APP_DIR)
        settings.APP_DIR = Path(self.tmp.name)
        settings.SETTINGS_FILE = settings.APP_DIR / "settings.json"

    def tearDown(self):
        settings.SETTINGS_FILE, settings.APP_DIR = self.saved
        self.tmp.cleanup()

    @unittest.skipUnless(sys.platform == "win32", "DPAPI solo existe en Windows")
    def test_api_key_is_not_stored_in_plain_text(self):
        cfg = settings.load()
        cfg["engines"]["gemini"]["api_key"] = KEY
        cfg["engines"]["gemini"]["model"] = "gemini-x"
        settings.save(cfg)
        raw = settings.SETTINGS_FILE.read_text(encoding="utf-8")
        self.assertNotIn(KEY, raw)
        self.assertIn("gemini-x", raw)  # lo demás sí queda legible
        self.assertEqual(settings.load()["engines"]["gemini"]["api_key"], KEY)

    def test_old_plain_text_file_still_loads(self):
        settings.SETTINGS_FILE.write_text(
            json.dumps({"engine": "gemini", "engines": {"gemini": {"api_key": "vieja-clave"}}}),
            encoding="utf-8",
        )
        self.assertEqual(settings.load()["engines"]["gemini"]["api_key"], "vieja-clave")

    def test_defaults_exist(self):
        cfg = settings.load()
        for key in ("language", "ui_language", "workspace_dir", "engines"):
            self.assertIn(key, cfg)


if __name__ == "__main__":
    unittest.main()
