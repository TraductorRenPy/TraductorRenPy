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
from traductor.glossary import Glossary
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


if __name__ == "__main__":
    unittest.main()
