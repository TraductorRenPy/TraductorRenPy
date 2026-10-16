import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from traductor import about, updates


class VersionTests(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(updates.parse_version("v1.0.8"), (1, 0, 8))
        self.assertEqual(updates.parse_version("1.2.3-beta"), (1, 2, 3))
        self.assertEqual(updates.parse_version("sin numeros"), ())
        self.assertTrue(updates.is_newer("v1.0.8", "1.0.7"))
        self.assertTrue(updates.is_newer("1.10.0", "1.9.9"))  # compara números, no texto
        self.assertFalse(updates.is_newer("1.0.7", "1.0.7"))
        self.assertFalse(updates.is_newer("1.0.6", "1.0.7"))
        self.assertFalse(updates.is_newer("", "1.0.7"))

    def test_api_url_only_for_github_repositories(self):
        self.assertEqual(
            updates.api_url("https://github.com/TraductorRenPy/TraductorRenPy"),
            "https://api.github.com/repos/TraductorRenPy/TraductorRenPy/releases/latest",
        )
        self.assertEqual(updates.api_url("https://github.com/u/r/"), "https://api.github.com/repos/u/r/releases/latest")
        self.assertEqual(updates.api_url("https://example.org/x"), "")
        self.assertEqual(updates.api_url(""), "")


class FakeGitHub(BaseHTTPRequestHandler):
    payload = {"tag_name": "v9.9.9", "html_url": "https://github.com/u/r/releases/tag/v9.9.9"}
    status = 200
    seen_agent = None

    def do_GET(self):
        FakeGitHub.seen_agent = self.headers.get("User-Agent")
        self.send_response(FakeGitHub.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(FakeGitHub.payload).encode("utf-8"))

    def log_message(self, *args):
        pass


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/releases/latest"
        FakeGitHub.payload = {"tag_name": "v9.9.9", "html_url": "https://github.com/u/r/releases/tag/v9.9.9"}
        FakeGitHub.status = 200

    def test_reports_a_newer_release_and_sends_only_the_app_name(self):
        ok, info = updates.check("1.0.7", self.url)
        self.assertTrue(ok)
        self.assertEqual((info.version, info.url), ("9.9.9", "https://github.com/u/r/releases/tag/v9.9.9"))
        self.assertTrue(FakeGitHub.seen_agent.startswith("TraductorRenPy/"))

    def test_no_notice_when_up_to_date(self):
        FakeGitHub.payload = {"tag_name": "v1.0.7", "html_url": "https://github.com/u/r/releases/tag/v1.0.7"}
        self.assertEqual(updates.check("1.0.7", self.url), (True, None))

    def test_failures_are_silent(self):
        FakeGitHub.status = 500
        self.assertEqual(updates.check("1.0.7", self.url), (False, None))
        FakeGitHub.status = 200
        FakeGitHub.payload = {"nada": "util"}
        self.assertEqual(updates.check("1.0.7", self.url), (False, None))
        FakeGitHub.payload = {"tag_name": "v9.9.9", "html_url": "javascript:alert(1)"}  # solo enlaces https
        self.assertEqual(updates.check("1.0.7", self.url), (False, None))
        self.assertEqual(updates.check("1.0.7", "http://127.0.0.1:1/nada"), (False, None))  # sin servidor

    def test_no_request_without_a_github_repository(self):
        with mock.patch.object(about, "REPO_URL", ""):
            self.assertIsNone(updates.fetch_latest())


if __name__ == "__main__":
    unittest.main()
