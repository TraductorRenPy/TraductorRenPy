import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from traductor import credit, eta, notify, translate
from traductor.common import Cancelled
from traductor.engines import Engine, EngineError
from traductor.engines import base as engines_base
from traductor.glossary import Glossary, Term
from traductor.translate import Cache, Unit, run_job

ROOT = Path(__file__).resolve().parent.parent


class EtaTests(unittest.TestCase):
    def test_uses_recent_pace_not_the_average(self):
        # 100 lotes rápidos (1 s) y luego 20 lentos (10 s cada uno)
        samples = [(0.0, 0)] + [(float(i), i) for i in range(1, 101)]
        samples += [(100.0 + 10 * k, 100 + k) for k in range(1, 21)]
        remaining = eta.remaining_seconds(samples, 120, 220)
        self.assertAlmostEqual(remaining, 100 * 10, delta=1)  # ritmo reciente: 10 s por lote
        average = 300.0 / 120 * 100  # el promedio total diría ~250 s: muy optimista
        self.assertGreater(remaining, average * 3)

    def test_none_when_not_enough_data(self):
        self.assertIsNone(eta.remaining_seconds([(0.0, 0)], 0, 10))
        self.assertIsNone(eta.remaining_seconds([(0.0, 0), (1.0, 1)], 10, 10))  # ya terminó

    def test_stalled_recent_progress_falls_back_to_overall_pace(self):
        samples = [(0.0, 0), (10.0, 10), (20.0, 10), (30.0, 10)]
        # en la ventana reciente no hubo avance: se usa el ritmo total (10 lotes en 30 s)
        self.assertAlmostEqual(eta.remaining_seconds(samples, 10, 20, window=2), 30.0)


class SlowEngine(Engine):
    name = "slow"
    label = "Lento"

    def __init__(self, delay=0.05, fatal_on=None):
        self.cfg = {}
        self.delay = delay
        self.fatal_on = fatal_on
        self.threads = set()
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self._lock = threading.Lock()

    def translate(self, batch):
        with self._lock:
            self.calls += 1
            n = self.calls
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.threads.add(threading.get_ident())
        try:
            time.sleep(self.delay)
            if self.fatal_on and n == self.fatal_on:
                raise EngineError("Se agotó la cuota diaria del servicio.", fatal=True)
            return {i.id: "ES:" + i.text for i in batch.items}
        finally:
            with self._lock:
                self.active -= 1


def make_units(n):
    return [Unit(f"line {i}", None) for i in range(n)]


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Cache(Path(self.tmp.name) / "cache.json")

    def test_runs_several_batches_at_once_and_translates_everything(self):
        engine = SlowEngine()
        units = make_units(40)
        result = run_job(units, engine, Glossary([]), self.cache, batch_size=2, workers=4)
        self.assertEqual(result.translated, 40)
        self.assertEqual(result.failed, [])
        self.assertGreater(engine.max_active, 1)
        self.assertLessEqual(engine.max_active, 4)
        self.assertTrue(all(self.cache.get(u.text) == "ES:" + u.text for u in units))
        self.assertEqual(len(Cache(self.cache.path).items), 40)  # también quedó guardado en disco

    def test_single_worker_is_the_normal_sequential_mode(self):
        engine = SlowEngine(delay=0.0)
        run_job(make_units(10), engine, Glossary([]), self.cache, batch_size=2, workers=1)
        self.assertEqual(engine.max_active, 1)

    def test_fatal_error_stops_the_job_and_keeps_what_was_done(self):
        engine = SlowEngine(fatal_on=4)
        with self.assertRaises(EngineError) as ctx:
            run_job(make_units(60), engine, Glossary([]), self.cache, batch_size=2, workers=3)
        self.assertTrue(ctx.exception.fatal)
        self.assertLess(engine.calls, 30)  # no siguió enviando lotes
        self.assertGreater(len(Cache(self.cache.path).items), 0)

    def test_cancel_waits_only_for_sent_batches(self):
        engine = SlowEngine(delay=0.05)
        cancel = threading.Event()
        threading.Timer(0.12, cancel.set).start()
        with self.assertRaises(Cancelled):
            run_job(make_units(200), engine, Glossary([]), self.cache, batch_size=2, workers=3, cancel=cancel)
        self.assertLess(engine.calls, 50)
        self.assertEqual(engine.active, 0)
        self.assertGreater(len(Cache(self.cache.path).items), 0)

    def test_workers_are_capped(self):
        engine = SlowEngine(delay=0.02)
        run_job(make_units(60), engine, Glossary([]), self.cache, batch_size=1, workers=99)
        self.assertLessEqual(engine.max_active, translate.MAX_WORKERS)


class CooldownTests(unittest.TestCase):
    def test_other_requests_wait_for_a_shared_pause_but_the_owner_does_not(self):
        slept = []
        with mock.patch.object(engines_base, "_sleep", slept.append):
            engines_base._set_cooldown(30)
            engines_base._wait_cooldown()  # esta petición provocó la pausa: ya espera por su cuenta
            self.assertEqual(slept, [])
            t = threading.Thread(target=engines_base._wait_cooldown)
            t.start()
            t.join()
        self.assertEqual(len(slept), 1)
        self.assertGreater(slept[0], 20)
        engines_base._cooldown_until = 0.0  # no afectar a otras pruebas


class CreditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_finds_about_text_in_the_scripts(self):
        game = self.dir / "game"
        game.mkdir()
        (game / "options.rpy").write_text(
            'define config.name = _("X")\ndefine gui.about = _p("""Line one.\n\nLine two.""")\n', encoding="utf-8"
        )
        self.assertEqual(credit.find_about_text([game]), "Line one.\n\nLine two.")
        (game / "options.rpy").write_text("define config.name = _('X')\n", encoding="utf-8")
        self.assertIsNone(credit.find_about_text([game]))

    def _tl(self, new='"Una linea."'):
        tl = self.dir / "tl"
        tl.mkdir(exist_ok=True)
        f = tl / "options.rpy"
        f.write_text(f'translate spanish strings:\n\n    old "One line."\n    new {new}\n', encoding="utf-8")
        return tl, f

    def test_adds_credit_once(self):
        tl, f = self._tl()
        changes = {}
        cache = Cache(self.dir / "c.json")
        self.assertEqual(credit.add_credit(changes, tl, "One line.", "Traducción: Ana", cache), 1)
        self.assertIn('new "Una linea.\\n\\nTraducción: Ana"', changes[f])
        f.write_text(changes[f], encoding="utf-8")
        self.assertEqual(credit.add_credit({}, tl, "One line.", "Traducción: Ana", cache), 0)  # idempotente

    def test_untranslated_about_is_left_alone(self):
        tl, f = self._tl(new='""')
        self.assertEqual(credit.add_credit({}, tl, "One line.", "Crédito", Cache(self.dir / "c.json")), 0)

    def test_uses_the_cache_when_the_entry_was_just_translated(self):
        tl, f = self._tl(new='""')
        cache = Cache(self.dir / "c.json")
        cache.put("One line.", "Una línea.", "fake")
        changes = {}
        self.assertEqual(credit.add_credit(changes, tl, "One line.", "Crédito", cache), 1)
        self.assertIn("Una línea.\\n\\nCrédito", changes[f])

    def test_quotes_in_the_credit_are_escaped(self):
        tl, f = self._tl()
        changes = {}
        credit.add_credit(changes, tl, "One line.", 'Por "Ana"', Cache(self.dir / "c.json"))
        self.assertIn('Por \\"Ana\\"', changes[f])


class AppCreditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.tl = self.dir / "tl"
        self.tl.mkdir()
        self.f = self.tl / "options.rpy"
        self.f.write_text('translate Spanish strings:\n\n    old "One line."\n    new "Una linea."\n', encoding="utf-8")
        self.cache = Cache(self.dir / "c.json")

    def apply(self, personal=""):
        changes = {}
        n = credit.add_credit(changes, self.tl, "One line.", credit.build_credit("Spanish", personal), self.cache)
        if self.f in changes:
            self.f.write_text(changes[self.f], encoding="utf-8")
        return n

    def test_app_line_is_in_the_translation_language(self):
        self.assertEqual(credit.app_line("Spanish"), "Traducción con TraductorRenPy")
        self.assertEqual(credit.app_line("spanish_latam"), "Traducción con TraductorRenPy")
        self.assertEqual(credit.app_line("french"), "Traduit avec TraductorRenPy")
        self.assertEqual(credit.app_line("swedish"), "Translated with TraductorRenPy")  # idioma fuera de la lista

    def test_the_app_name_and_its_page_are_always_added(self):
        page = credit.project_page()
        self.assertTrue(page.startswith("github.com/"))  # sin «https://»
        self.assertEqual(self.apply(), 1)
        self.assertIn(
            'new "Una linea.\\n\\nTraducción con TraductorRenPy\\n' + page + '"', self.f.read_text(encoding="utf-8")
        )

    def test_without_a_project_page_only_the_name_is_added(self):
        with mock.patch.object(credit.about, "REPO_URL", ""):
            self.assertEqual(self.apply(), 1)
        self.assertIn('new "Una linea.\\n\\nTraducción con TraductorRenPy"', self.f.read_text(encoding="utf-8"))

    def test_installing_again_does_not_repeat_the_credit(self):
        self.apply()
        self.assertEqual(self.apply(), 0)
        self.assertEqual(self.f.read_text(encoding="utf-8").count("Traducción con TraductorRenPy"), 1)

    def test_an_extra_personal_credit_is_still_supported_by_the_module_for_later(self):
        self.apply("Traducción al español: Ana")
        self.assertIn("Traducción al español: Ana", self.f.read_text(encoding="utf-8"))
        self.assertEqual(self.apply("Beto"), 1)  # cambiar el alias reemplaza el anterior
        text = self.f.read_text(encoding="utf-8")
        self.assertIn("Beto", text)
        self.assertNotIn("Ana", text)


class NotifyTests(unittest.TestCase):
    def test_alert_never_raises(self):
        class Broken:
            def winfo_id(self):
                raise RuntimeError("sin ventana")

            def bell(self):
                raise RuntimeError("sin sonido")

        notify.alert(Broken(), True)
        notify.alert(Broken(), False)


class PackagedDocsTests(unittest.TestCase):
    def test_plain_text_instructions_warn_about_smartscreen(self):
        es = (ROOT / "docs" / "LEEME.txt").read_text(encoding="utf-8")
        en = (ROOT / "docs" / "READ_ME_FIRST.txt").read_text(encoding="utf-8")
        self.assertIn("Ejecutar de todas formas", es)
        self.assertIn("Run anyway", en)
        self.assertIn("renpy.org", es)
        self.assertIn("renpy.org", en)

    def test_release_notes_exist_and_mention_smartscreen(self):
        notes = (ROOT / ".github" / "release-notes.md").read_text(encoding="utf-8")
        self.assertIn("Run anyway", notes)
        self.assertIn("release-notes.md", (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))


class EdgeBreakRepairTests(unittest.TestCase):
    def test_restores_leading_and_trailing_line_breaks(self):
        from traductor import validate

        text, reasons, repaired = validate.validate("You rejected Hedwig.\\n", "Rechazaste a Hedwig.")
        self.assertEqual((text, reasons, repaired), ("Rechazaste a Hedwig.\\n", [], True))
        text, _, repaired = validate.validate("\\n\\nYou called Liam out.", "Le reclamaste a Liam.")
        self.assertEqual((text, repaired), ("\\n\\nLe reclamaste a Liam.", True))
        text, _, _ = validate.validate("\\nHi\\n", "\\nHola")  # uno de los dos bordes ya estaba
        self.assertEqual(text, "\\nHola\\n")

    def test_interior_breaks_and_missing_tags_are_still_rejected(self):
        from traductor import validate

        text, reasons, _ = validate.validate("One\\nTwo", "Uno Dos")  # falta un \n interior: no se inventa
        self.assertIsNone(text)
        self.assertTrue(reasons)
        text, reasons, _ = validate.validate("You {b}should{/b} care", "Deberia importarte")
        self.assertIsNone(text)


TL_RETRY = '''# game/script.rpy:1
translate spanish start_aaaaaaaa:

    # c "Hello [name]!"
    c "Hello [name]!"

# game/script.rpy:3
translate spanish start_cccccccc:

    # "{i}Bad tag{/i}"
    "{i}Bad tag{/i}"
'''


class RetryFailedValidationTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace

        from traductor import pipeline

        self.pipeline = pipeline
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "juego"
        tl = root / "game" / "tl" / "spanish"
        tl.mkdir(parents=True)
        (tl / "script.rpy").write_text(TL_RETRY, encoding="utf-8")
        self.info = SimpleNamespace(root=root, game_dir=root / "game", need_collect=False, name="Juego")
        self.ws = pipeline.Workspace(Path(self.tmp.name) / "ws")
        self.ws.base.mkdir()
        cache = Cache(self.ws.cache_file)
        cache.put("Hello [name]!", "¡Hola [name]!", "fake")
        cache.put("{i}Bad tag{/i}", "Etiqueta mala", "fake")  # perdió las etiquetas: no pasa la validación
        cache.save()
        patcher = mock.patch.object(pipeline, "suggest_glossary", return_value=Glossary([]))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_lists_only_the_lines_that_fail_validation(self):
        bad = self.pipeline.failed_validation_originals(self.info, self.ws, "spanish")
        self.assertEqual(bad, ["{i}Bad tag{/i}"])

    def test_retry_removes_only_those_lines_keeps_a_backup_and_translates_again(self):
        engine = mock.Mock(label="Falso")
        with mock.patch.object(self.pipeline, "create_engine", return_value=engine), \
                mock.patch.object(self.pipeline, "translate_pending") as tp:
            n = self.pipeline.retry_failed_validation(
                self.info, self.ws, "spanish", "microsoft", {}, 20, workers=2
            )
        self.assertEqual(n, 1)
        cache = Cache(self.ws.cache_file)
        self.assertEqual(cache.get("Hello [name]!"), "¡Hola [name]!")  # lo válido no se toca
        self.assertIsNone(cache.get("{i}Bad tag{/i}"))
        backups = list(self.ws.backups.glob("traducciones_antes_de_reintentar_*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(Cache(backups[0]).get("{i}Bad tag{/i}"), "Etiqueta mala")  # la copia conserva todo
        tp.assert_called_once()
        self.assertEqual(tp.call_args.args[3], "microsoft")  # con el motor elegido
        self.assertEqual(tp.call_args.kwargs["workers"], 2)

    def test_nothing_to_retry(self):
        cache = Cache(self.ws.cache_file)
        cache.put("{i}Bad tag{/i}", "{i}Etiqueta{/i}", "fake")
        cache.save()
        with mock.patch.object(self.pipeline, "create_engine", return_value=mock.Mock(label="X")), \
                mock.patch.object(self.pipeline, "translate_pending") as tp:
            self.assertEqual(self.pipeline.retry_failed_validation(self.info, self.ws, "spanish", "gemini", {}), 0)
        tp.assert_not_called()
        self.assertFalse(self.ws.backups.exists() and list(self.ws.backups.glob("*.json")))

    def test_missing_key_changes_nothing(self):
        with mock.patch.object(self.pipeline, "create_engine", side_effect=EngineError("Falta la clave", fatal=True)):
            with self.assertRaises(EngineError):
                self.pipeline.retry_failed_validation(self.info, self.ws, "spanish", "gemini", {})
        self.assertEqual(Cache(self.ws.cache_file).get("{i}Bad tag{/i}"), "Etiqueta mala")


class HelpAndTutorialTests(unittest.TestCase):
    def test_tutorials_exist_in_both_languages_and_cover_the_main_features(self):
        from traductor import help_text

        for lang, needles in (
            ("es", ("Reintentar las que fallaron la validacion", "Peticiones simultaneas", "Credito en \"Acerca de\"",
                    "Ejecutar de todas formas", "Avisar al terminar")),
            ("en", ("Retry the lines that failed validation", "Simultaneous requests", "Credit in \"About\"",
                    "Run anyway", "Notify when done")),
        ):
            path = help_text.tutorial_path(lang)
            self.assertIsNotNone(path, lang)
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                self.assertIn(needle, text, f"{lang}: falta «{needle}» en el tutorial")

    def test_in_app_help_mentions_the_new_features(self):
        from traductor.help_text import HELP_EN, HELP_ES

        for text in (HELP_ES, HELP_EN):
            self.assertTrue(len(text) > 1500)
        HELP_ES, HELP_EN = " ".join(HELP_ES.split()), " ".join(HELP_EN.split())  # el texto se parte en renglones
        for needle in ("Reintentar las que fallaron la validación", "Peticiones simultáneas",
                       "Traducción con TraductorRenPy", "Avisar al terminar", "Windows protegió su PC"):
            self.assertIn(needle, HELP_ES)
        for needle in ("Retry the lines that failed validation", "Simultaneous requests",
                       "Translated with TraductorRenPy", "Notify when done", "Windows protected your PC"):
            self.assertIn(needle, HELP_EN)

    def test_help_button_labels_exist_in_the_interface(self):
        from traductor import i18n_en

        # lo que la ayuda en inglés llama «Retry the lines that failed validation» es el texto real del botón
        self.assertEqual(i18n_en.EN["Reintentar las que fallaron la validación"], "Retry the lines that failed validation")
        self.assertEqual(i18n_en.EN["Peticiones simultáneas"], "Simultaneous requests")
        self.assertEqual(i18n_en.EN["Avisar al terminar"], "Notify when done")


class ExistingTranslationIsRespectedTests(unittest.TestCase):
    """Glosario sobre traducciones que ya venían hechas por otra persona."""

    TL = (
        "translate Spanish strings:\n\n"
        '    old "Patrick"\n    new "Patricio"\n\n'
        '    old "Godson"\n    new "Ahijado"\n\n'
        '    old "Thanks, Patrick!"\n    new "Thanks, Patrick!"\n'
    )

    def run_apply(self, titles):
        from traductor import install

        with tempfile.TemporaryDirectory() as d:
            tl = Path(d) / "Spanish"
            tl.mkdir()
            (tl / "a.rpy").write_text(self.TL, encoding="utf-8")
            cache = Cache(Path(d) / "c.json")
            cache.put("Thanks, Patrick!", "¡Gracias, Patrick!", "fake")
            glossary = Glossary([Term("Patrick"), Term("Godson")])
            result = install.apply_cache_to_tl(tl, cache, glossary, titles=titles)
            return result, result.changes.get(tl / "a.rpy", self.TL)

    def test_only_the_game_title_is_forced_on_entries_already_translated(self):
        result, text = self.run_apply(titles=["Godson"])
        self.assertIn('new "Patricio"', text)  # el nombre que adaptó la otra traducción se respeta
        self.assertIn('new "Godson"', text)  # el título del juego sí se corrige
        self.assertIn("¡Gracias, Patrick!", text)  # y lo que traduce esta app usa el glosario
        self.assertEqual(result.glossary_fixed, 1)

    def test_without_titles_the_previous_behavior_is_kept(self):
        result, text = self.run_apply(titles=None)
        self.assertIn('new "Patrick"', text)
        self.assertEqual(result.glossary_fixed, 2)


if __name__ == "__main__":
    unittest.main()
