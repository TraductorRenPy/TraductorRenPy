import unittest
from urllib.parse import parse_qs, urlparse

from traductor import report


class SanitizeTests(unittest.TestCase):
    def test_removes_paths_emails_keys_and_known_paths(self):
        key = "AIzaSy" + "A" * 33
        text = f"Juego en D:\\Mis Juegos\\Godson\\game y /home/ana/x; mail ana@example.com; clave {key}"
        out = report.sanitize(text, known_paths=["D:\\Mis Juegos\\Godson"])
        self.assertNotIn("Godson", out)
        self.assertNotIn("ana@example.com", out)
        self.assertNotIn(key, out)
        self.assertNotIn("/home/ana", out)

    def test_game_text_lines_are_dropped(self):
        lines = ["Todo bien", "SIN TRADUCIR: «Hello my secret line»", "fin"]
        out = report.clean_log(lines)
        self.assertEqual(out, ["Todo bien", report.OMITTED, "fin"])

    def test_diagnostics_has_version_and_log(self):
        text = report.build_diagnostics(["línea 1"], "gemini", "spanish", "es")
        self.assertIn("TraductorRenPy", text)
        self.assertIn("gemini", text)
        self.assertIn("línea 1", text)


class IssueUrlTests(unittest.TestCase):
    def test_prefilled_and_short(self):
        url = report.issue_url("https://github.com/u/r/", "Problem", "x" * 20000)
        self.assertLessEqual(len(url), 6600)
        parts = urlparse(url)
        self.assertEqual(parts.path, "/u/r/issues/new")
        self.assertEqual(parse_qs(parts.query)["title"], ["Problem"])
        self.assertIn("body", parse_qs(parts.query))


if __name__ == "__main__":
    unittest.main()
