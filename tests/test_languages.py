import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from traductor import languages
from traductor.engines import Batch, Item, create_engine
from traductor.engines.llm import system_prompt
from traductor.glossary import suggest_terms
from traductor.pending import ALREADY_SPANISH, PENDING, parse_tl_text

TL = 'translate {lang} a_b:\n\n    # c "Sí, claro, no hay problema para mí."\n    c "Sí, claro, no hay problema para mí."\n'


class LanguageTests(unittest.TestCase):
    def test_table_and_helpers(self):
        self.assertEqual(languages.get("spanish").ms, "es")
        self.assertEqual(languages.get("PORTUGUESE").ms, "pt")
        self.assertEqual(languages.get("klingon").code, "klingon")  # desconocido: se acepta
        self.assertEqual(languages.code_from_label(languages.LANGUAGES["french"].label), "french")
        self.assertEqual(languages.code_from_label("Swedish"), "swedish")
        self.assertEqual(languages.label_for("german"), languages.LANGUAGES["german"].label)
        self.assertTrue(languages.is_spanish("SpanishTE"))
        self.assertFalse(languages.is_spanish("portuguese"))

    def test_prompt_names_the_target_language(self):
        for code, word in (("spanish", "Spanish"), ("portuguese", "Portuguese"), ("french", "French")):
            prompt = system_prompt(languages.get(code))
            self.assertIn(word, prompt)
            self.assertNotIn("@TARGET@", prompt)
        self.assertNotIn("Spanish", system_prompt(languages.get("german")))

    def test_already_spanish_only_when_target_is_spanish(self):
        es = parse_tl_text(TL.format(lang="spanish"), target="spanish")[0]
        pt = parse_tl_text(TL.format(lang="portuguese"), target="portuguese")[0]
        self.assertEqual(es.status, ALREADY_SPANISH)
        self.assertEqual(pt.status, PENDING)  # para otro idioma no se supone nada

    def test_role_translations_only_for_spanish(self):
        chars = {"n": "Narrator", "m": "Eileen"}
        self.assertEqual({t.src: t.dst for t in suggest_terms(chars, "spanish")}, {"Narrator": "Narrador", "Eileen": ""})
        self.assertEqual({t.src: t.dst for t in suggest_terms(chars, "french")}, {"Eileen": ""})


class _H(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, body))
        if self.path.endswith("/chat/completions"):
            reply = {"choices": [{"message": {"content": json.dumps({"translations": [{"id": "1", "text": "ok"}]})}}]}
        else:
            reply = [{"translations": [{"text": "ok", "to": "x"}]}]
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class EngineTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _H)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _H.seen.clear()
        self.batch = Batch([Item("1", "Hello")])

    def test_llm_sends_the_target_in_the_prompt(self):
        cfg = {"grok": {"api_key": "k", "base_url": self.url}}
        create_engine("grok", cfg, "portuguese").translate(self.batch)
        _, body = _H.seen[0]
        self.assertIn("Brazilian Portuguese", body["messages"][0]["content"])

    def test_microsoft_uses_the_language_code(self):
        cfg = {"microsoft": {"api_key": "k", "base_url": self.url}}
        create_engine("microsoft", cfg, "french").translate(self.batch)
        path, _ = _H.seen[0]
        self.assertIn("to=fr", path)


if __name__ == "__main__":
    unittest.main()
