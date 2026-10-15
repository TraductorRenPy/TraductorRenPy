import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from traductor import translate
from traductor.engines import BadResponse, Batch, Engine, EngineError, Item, create_engine
from traductor.engines import base as engines_base
from traductor.engines.llm import parse_translations
from traductor.engines.microsoft import protect, restore
from traductor.glossary import Glossary, Term, find_characters, suggest_terms
from traductor.pending import parse_tl_text
from traductor.pending import TlReport
from traductor.textutil import fix_quotes, tokens


class TextUtilTests(unittest.TestCase):
    def test_tokens(self):
        t = r'{i}Hola{/i} [name] %s %(x)d \n \" [a[0]]'
        self.assertEqual(
            tokens(t), ["{i}", "{/i}", "[name]", "%s", "%(x)d", r"\n", r"\"", "[a[0]]"]
        )

    def test_fix_quotes(self):
        self.assertEqual(fix_quotes('Dijo "hola" y \\"adiós\\"'), 'Dijo \\"hola\\" y \\"adiós\\"')
        self.assertEqual(fix_quotes("sin comillas"), "sin comillas")


class GlossaryTests(unittest.TestCase):
    def test_text_roundtrip_and_relevant(self):
        g = Glossary.from_text("Marie\nUncle = Tío\n# comentario\nMarie")
        self.assertEqual([(t.src, t.dst) for t in g.terms], [("Marie", ""), ("Uncle", "Tío")])
        self.assertEqual(Glossary.from_text(g.to_text()).terms, g.terms)
        rel = g.relevant(["I saw Marie today", "Mariecita"])
        self.assertEqual([t.src for t in rel], ["Marie"])

    def test_find_characters(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tl").mkdir()
            (Path(d) / "a.rpy").write_text(
                'define c = Character("Chris", color="#fff")\n'
                "define j = Character(_('Jack'))\n"
                'default m = Character("[mom_name]")\n',
                encoding="utf-8",
            )
            (Path(d) / "tl" / "b.rpy").write_text('define x = Character("Ignorado")\n')
            chars = find_characters([Path(d)])
        self.assertEqual(chars, {"c": "Chris", "j": "Jack", "m": "[mom_name]"})
        self.assertEqual([t.src for t in suggest_terms(chars)], ["Chris", "Jack"])


class GlossarySuggestionTests(unittest.TestCase):
    def test_names_vs_descriptions(self):
        chars = {
            "m": "Eileen", "u": "Unknown Man", "h": "Him", "p": "Pizza Guy", "n": "Narrator",
            "t": "Therapist", "b": "Bianca's Children", "f": "First Child", "s": "Second Child",
            "c": "CEO", "j": "JAY", "k": "Kyle", "mom": "Mom", "x": "[mom_name]", "d": "Cheesecake",
        }
        got = {t.src: t.dst for t in suggest_terms(chars)}
        self.assertEqual(
            got,
            {
                "Eileen": "", "CEO": "", "JAY": "", "Kyle": "", "Cheesecake": "",
                "Unknown Man": "Hombre desconocido", "Pizza Guy": "Repartidor de pizza",
                "Narrator": "Narrador", "Therapist": "Terapeuta", "Mom": "Mamá",
            },
        )
        # sin traducción fija = se deja fuera para que el motor lo traduzca con contexto
        for name in ("Him", "First Child", "Second Child", "Bianca's Children"):
            self.assertNotIn(name, got)

    def test_game_title_is_found(self):
        from traductor.glossary import find_game_titles

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tl").mkdir()
            (Path(d) / "options.rpy").write_text(
                'define config.name = _("Demo Game")\ndefine config.version = "1.0"\n', encoding="utf-8"
            )
            (Path(d) / "tl" / "x.rpy").write_text('define config.name = _("Ignorado")\n', encoding="utf-8")
            (Path(d) / "other.rpy").write_text("define config.name = 'Mi Juego'\n", encoding="utf-8")
            self.assertEqual(sorted(find_game_titles([Path(d)])), ["Demo Game", "Mi Juego"])

    def test_job_creates_glossary_when_missing(self):
        from traductor import pipeline

        with tempfile.TemporaryDirectory() as d:
            game = Path(d) / "g"
            (game / "game" / "tl" / "spanish").mkdir(parents=True)
            (game / "game" / "script.rpy").write_text(
                'define m = Character("Eileen")\ndefine p = Character("Pizza Guy")\n', encoding="utf-8"
            )
            (game / "game" / "tl" / "spanish" / "script.rpy").write_text(
                'translate spanish s_aaaaaaaa:\n\n    # m "Hello."\n    m "Hello."\n', encoding="utf-8"
            )
            from traductor.detect import analyze

            info = analyze(game)
            ws = pipeline.make_workspace(Path(d) / "ws", info)
            logs = []
            cfg = {"gemini": {"api_key": "k", "base_url": "http://127.0.0.1:9", "min_interval": "0"}}
            saved = engines_base._sleep
            engines_base._sleep = lambda s: None  # sin esperas de reintento
            try:
                pipeline.translate_pending(info, ws, "spanish", "gemini", cfg, log=logs.append)
            except EngineError:
                pass  # no hay servidor: solo interesa el glosario
            finally:
                engines_base._sleep = saved
            self.assertTrue(ws.glossary_file.is_file())
            self.assertTrue(any("Glosario creado" in m for m in logs))
            self.assertEqual(
                sorted((t.src, t.dst) for t in Glossary.load(ws.glossary_file).terms),
                [("Eileen", ""), ("Pizza Guy", "Repartidor de pizza")],
            )


class MicrosoftMarkupTests(unittest.TestCase):
    def test_protect_and_restore(self):
        glossary = [Term("Marie"), Term("Uncle", "Tío")]
        html_text = protect('Hi [name], Marie & {i}Uncle{/i}!', glossary)
        self.assertIn('<span class="notranslate">[name]</span>', html_text)
        self.assertIn('<span class="notranslate">Marie</span>', html_text)
        self.assertIn('<mstrans:dictionary translation="Tío">Uncle</mstrans:dictionary>', html_text)
        self.assertIn("&amp;", html_text)
        simulated = html_text.replace("Hi", "Hola")
        self.assertEqual(restore(simulated), "Hola [name], Marie & {i}Uncle{/i}!")


class ParseTests(unittest.TestCase):
    def test_parse_variants(self):
        good = '{"translations":[{"id":"1","text":"Hola"},{"id":2,"text":"Adiós"}]}'
        self.assertEqual(parse_translations(good), {"1": "Hola", "2": "Adiós"})
        self.assertEqual(parse_translations("```json\n" + good + "\n```"), {"1": "Hola", "2": "Adiós"})
        self.assertEqual(parse_translations("Claro:\n" + good), {"1": "Hola", "2": "Adiós"})
        self.assertEqual(parse_translations('[{"id":"1","text":"x"}]'), {"1": "x"})
        with self.assertRaises(EngineError):
            parse_translations("no json")


SAMPLE_TL = '''
# game/script.rpy:1
translate spanish start_aaaaaaaa:

    # c "Hello [name]!"
    c "Hello [name]!"

# game/script.rpy:2
translate spanish start_bbbbbbbb:

    # j "How are you?"
    j "How are you?"

# game/script.rpy:3
translate spanish start_cccccccc:

    # c "Hello [name]!"
    c "Hello [name]!"

# game/script.rpy:4
translate spanish start_dddddddd:

    # "Done."
    "Hecho."

translate spanish strings:

    old "Start"
    new "Start"
'''


class FakeEngine(Engine):
    name = "fake"
    label = "Falso"

    def __init__(self, drop=()):
        self.cfg = {}
        self.calls = []
        self.drop = drop

    def translate(self, batch):
        self.calls.append(batch)
        return {
            i.id: "ES:" + i.text for i in batch.items if i.text not in self.drop
        }


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = translate.Cache(Path(self.tmp.name) / "c.json")
        self.report = TlReport(Path("."), parse_tl_text(SAMPLE_TL, "script.rpy"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_units_dedupe_and_context(self):
        units = translate.build_units(self.report, {"c": "Chris"})
        self.assertEqual([u.text for u in units], ["Hello [name]!", "How are you?", "Start"])
        how = units[1]
        self.assertEqual(how.who, "j")
        self.assertEqual(how.before, [("Chris", "Hello [name]!")])
        self.assertEqual(how.after, [("Chris", "Hello [name]!")])
        self.assertEqual(units[2].before, [])  # las strings no llevan contexto

    def test_job_translates_and_caches(self):
        engine = FakeEngine()
        units = translate.build_units(self.report)
        res = translate.run_job(units, engine, Glossary(), self.cache, batch_size=2)
        self.assertEqual((res.translated, res.from_cache, res.failed), (3, 0, []))
        self.assertEqual(len(engine.calls), 2)
        self.assertEqual(self.cache.get("Start"), "ES:Start")
        # segunda corrida: todo sale de la caché, sin llamar al motor
        engine2 = FakeEngine()
        res2 = translate.run_job(
            units, engine2, Glossary(), translate.Cache(self.cache.path), batch_size=2
        )
        self.assertEqual((res2.translated, res2.from_cache), (0, 3))
        self.assertEqual(engine2.calls, [])

    def test_missing_items_are_retried_then_failed(self):
        engine = FakeEngine(drop=("Start",))
        units = translate.build_units(self.report)
        res = translate.run_job(units[:2] + units[2:], engine, Glossary(), self.cache, batch_size=10)
        self.assertEqual(res.failed, ["Start"])
        self.assertEqual(res.translated, 2)

    def test_quotes_are_escaped_in_cache(self):
        class Quoting(FakeEngine):
            def translate(self, batch):
                return {i.id: 'Dijo "hola"' for i in batch.items}

        units = translate.build_units(self.report)[:1]
        translate.run_job(units, Quoting(), Glossary(), self.cache)
        self.assertEqual(self.cache.get("Hello [name]!"), 'Dijo \\"hola\\"')

    def test_bad_response_splits_batch(self):
        class Flaky(FakeEngine):
            def translate(self, batch):
                if len(batch.items) > 2:  # lotes grandes -> JSON roto
                    raise BadResponse("no es JSON")
                return super().translate(batch)

        units = translate.build_units(self.report)  # 3 textos únicos
        res = translate.run_job(units, Flaky(), Glossary(), self.cache, batch_size=10)
        self.assertEqual((res.translated, res.failed), (3, []))

    def test_single_unparseable_line_fails_alone(self):
        class Bad(FakeEngine):
            def translate(self, batch):
                if any(i.text == "Start" for i in batch.items):
                    raise BadResponse("no es JSON")
                return super().translate(batch)

        units = translate.build_units(self.report)
        res = translate.run_job(units, Bad(), Glossary(), self.cache, batch_size=10)
        self.assertEqual((res.translated, res.failed), (2, ["Start"]))

    def test_real_newlines_become_escapes(self):
        class Newline(FakeEngine):
            def translate(self, batch):
                return {i.id: "Línea uno\nlínea dos" for i in batch.items}

        translate.run_job(translate.build_units(self.report)[:1], Newline(), Glossary(), self.cache)
        self.assertEqual(self.cache.get("Hello [name]!"), "Línea uno\\nlínea dos")

    def test_glossary_only_relevant_terms(self):
        engine = FakeEngine()
        g = Glossary([Term("Hello"), Term("Zzz")])
        translate.run_job(translate.build_units(self.report)[:1], engine, g, self.cache)
        self.assertEqual([t.src for t in engine.calls[0].glossary], ["Hello"])

    def test_fatal_error_stops(self):
        class Fatal(FakeEngine):
            def translate(self, batch):
                raise EngineError("clave mala", fatal=True)

        with self.assertRaises(EngineError):
            translate.run_job(translate.build_units(self.report), Fatal(), Glossary(), self.cache)


class _Handler(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, dict(self.headers), body))
        if self.headers.get("Authorization") == "Bearer bad":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"no"}')
            return
        if self.path.endswith("/chat/completions"):
            items = json.loads(body["messages"][1]["content"])["items"]
            content = json.dumps({"translations": [{"id": i["id"], "text": "G:" + i["text"]} for i in items]})
            reply = {"choices": [{"message": {"content": content}}]}
        elif ":generateContent" in self.path:
            items = json.loads(body["contents"][0]["parts"][0]["text"])["items"]
            content = json.dumps({"translations": [{"id": i["id"], "text": "M:" + i["text"]} for i in items]})
            reply = {"candidates": [{"content": {"parts": [{"text": content}]}}]}
        else:  # Microsoft
            reply = [{"translations": [{"text": "MS:" + r["Text"], "to": "es"}]} for r in body]
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class HttpEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _Handler.seen.clear()
        self.batch = Batch(
            [Item("1", "Hi [name]", "Chris")],
            before=[("Jack", "Hey")],
            glossary=[Term("Chris")],
        )

    def cfg(self, **extra):
        return {"api_key": "k", "base_url": self.url, **extra}

    def test_grok(self):
        out = create_engine("grok", {"grok": self.cfg()}).translate(self.batch)
        self.assertEqual(out, {"1": "G:Hi [name]"})
        path, headers, body = _Handler.seen[0]
        self.assertEqual(path, "/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer k")
        sent = json.loads(body["messages"][1]["content"])
        self.assertEqual(sent["glossary"], [{"term": "Chris", "keep": True}])
        self.assertEqual(sent["context_before"], [{"speaker": "Jack", "text": "Hey"}])

    def test_gemini_key_in_header_not_url(self):
        out = create_engine("gemini", {"gemini": self.cfg(min_interval="0")}).translate(self.batch)
        self.assertEqual(out, {"1": "M:Hi [name]"})
        path, headers, body = _Handler.seen[0]
        self.assertNotIn("key", path)
        self.assertEqual({k.lower(): v for k, v in headers.items()}["x-goog-api-key"], "k")
        self.assertTrue(all(s["threshold"] == "BLOCK_NONE" for s in body["safetySettings"]))

    def test_microsoft(self):
        engine = create_engine("microsoft", {"microsoft": self.cfg(region="westus")})
        out = engine.translate(self.batch)
        self.assertEqual(out, {"1": "MS:Hi [name]"})
        path, headers, body = _Handler.seen[0]
        self.assertIn("to=es", path)
        self.assertEqual(headers["Ocp-Apim-Subscription-Region"], "westus")
        self.assertIn("notranslate", body[0]["Text"])

    def test_bad_key_is_fatal_and_not_leaked(self):
        engine = create_engine("grok", {"grok": self.cfg(api_key="bad")})
        with self.assertRaises(EngineError) as ctx:
            engine.translate(self.batch)
        self.assertTrue(ctx.exception.fatal)
        self.assertNotIn("bad", str(ctx.exception).replace("bad_", ""))

    def test_missing_key(self):
        with self.assertRaises(EngineError):
            create_engine("grok", {})

    def test_retry_on_503(self):
        calls = {"n": 0}
        real = _Handler.do_POST

        def flaky(handler):
            calls["n"] += 1
            if calls["n"] == 1:
                handler.rfile.read(int(handler.headers["Content-Length"]))
                handler.send_response(503)
                handler.end_headers()
                return
            real(handler)

        engines_base._sleep, saved = (lambda s: None), engines_base._sleep
        _Handler.do_POST = flaky
        try:
            out = create_engine("grok", {"grok": self.cfg()}).translate(self.batch)
        finally:
            _Handler.do_POST = real
            engines_base._sleep = saved
        self.assertEqual(out, {"1": "G:Hi [name]"})
        self.assertEqual(calls["n"], 2)


class QuotaTests(unittest.TestCase):
    """429 con retryDelay (límite por minuto) y con cuota diaria agotada."""

    def run_server(self, bodies):
        queue = list(bodies)

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                code, payload = queue.pop(0) if queue else (200, None)
                if payload is None:
                    content = json.dumps({"translations": [{"id": "1", "text": "Hola"}]})
                    payload = {"candidates": [{"content": {"parts": [{"text": content}]}}]}
                data = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close()))
        return f"http://127.0.0.1:{server.server_port}"

    def engine(self, url):
        return create_engine("gemini", {"gemini": {"api_key": "k", "base_url": url, "min_interval": "0"}})

    def setUp(self):
        self.sleeps = []
        saved = engines_base._sleep
        engines_base._sleep = self.sleeps.append
        self.addCleanup(setattr, engines_base, "_sleep", saved)
        self.batch = Batch([Item("1", "Hello")])

    def test_per_minute_limit_waits_retry_delay(self):
        limit = {"error": {"details": [{"retryDelay": "23s"}], "message": "quota per minute"}}
        url = self.run_server([(429, limit), (429, limit)])
        self.assertEqual(self.engine(url).translate(self.batch), {"1": "Hola"})
        self.assertEqual(self.sleeps, [24.0, 24.0])

    def test_daily_quota_is_fatal(self):
        daily = {"error": {"message": "x", "details": [{"quotaId": "GenerateRequestsPerDayPerProject"}]}}
        url = self.run_server([(429, daily)])
        with self.assertRaises(EngineError) as ctx:
            self.engine(url).translate(self.batch)
        self.assertTrue(ctx.exception.fatal)
        self.assertIn("mañana", str(ctx.exception))

    def test_throttle_spaces_calls(self):
        url = self.run_server([])
        engine = create_engine("gemini", {"gemini": {"api_key": "k", "base_url": url, "min_interval": "5"}})
        engine.translate(self.batch)
        self.assertEqual(self.sleeps, [])  # la primera llamada no espera
        engine.translate(self.batch)
        self.assertEqual(len(self.sleeps), 1)
        self.assertTrue(0 < self.sleeps[0] <= 5)


if __name__ == "__main__":
    unittest.main()
