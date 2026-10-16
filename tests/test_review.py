import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from traductor import languages, pipeline, review
from traductor.engines import BadResponse, Batch, Engine, EngineError, Item
from traductor.engines import llm
from traductor.engines.microsoft import MicrosoftEngine
from traductor.glossary import Glossary
from traductor.pending import scan_tl

TL = '''# game/script.rpy:1
translate Spanish ep1_a_11111111:

    # mg "Are you thinking of pledging our friendly fraternity?"
    mg "¿Estás pensando en comprometer nuestra fraternidad amiga?"

# game/script.rpy:2
translate Spanish ep1_b_22222222:

    # mc "I don't know, to be honest."
    mc "No lo sé, para ser honesto."

# game/script.rpy:3
translate Spanish ep1_c_33333333:

    # mc "{i}Wow{/i}!"
    mc "{i}Guau{/i}!"

# game/script.rpy:4
translate Spanish ep1_d_44444444:

    # mc "Not translated yet."
    mc "Not translated yet."

translate Spanish strings:

    # game/screens.rpy:9
    old "Description"
    new "Descripción"
'''

EXTRA = '''translate Spanish strings:

    old "Extra text that this app translated."
    new "Texto extra que tradujo esta app."
'''


class FakeReviewer(Engine):
    name = "fake"
    label = "Falso"
    can_review = True

    def __init__(self):
        self.cfg = {}
        self.batches = []

    def review(self, batch: Batch):
        self.batches.append(batch)
        out = {}
        for it in batch.items:
            if "pledging" in it.text:
                out[it.id] = "¿Estás pensando en unirte a nuestra fraternidad?"
            elif "Wow" in it.text:
                out[it.id] = "¡Guau!"  # pierde las etiquetas {i}: debe descartarse
            elif "honest" in it.text:
                continue  # no devuelve esa línea
            else:
                out[it.id] = it.current  # estaba bien
        return out


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.tl = self.dir / "juego" / "game" / "tl" / "Spanish"
        self.tl.mkdir(parents=True)
        (self.tl / "script.rpy").write_text(TL, encoding="utf-8")
        (self.tl / "zz_extra_strings.rpy").write_text(EXTRA, encoding="utf-8")
        self.report = scan_tl(self.tl)

    def units(self):
        return review.build_units(self.report, {"mg": "Magnar", "mc": "Perseo"})

    def test_only_existing_translations_are_reviewed(self):
        texts = [u.text for u in self.units()]
        self.assertIn("Are you thinking of pledging our friendly fraternity?", texts)
        self.assertIn("Description", texts)
        self.assertNotIn("Not translated yet.", texts)  # pendiente: eso lo traduce el paso normal
        self.assertNotIn("Extra text that this app translated.", texts)  # lo escribió esta app (zz_*)

    def test_each_unit_carries_the_scene_as_context(self):
        unit = next(u for u in self.units() if "honest" in u.text)
        self.assertEqual(unit.who, "Perseo")
        self.assertEqual(unit.before[0], ("Magnar", "Are you thinking of pledging our friendly fraternity?"))
        self.assertEqual(unit.after[0][1], "{i}Wow{/i}!")

    def test_review_keeps_good_lines_fixes_bad_ones_and_rejects_broken_formatting(self):
        engine = FakeReviewer()
        cache = review.ReviewCache(self.dir / "revision.json")
        result = review.run_review(self.units(), engine, Glossary([]), cache, batch_size=20)
        self.assertEqual((result.reviewed, result.changed, result.rejected, result.skipped), (3, 1, 1, 1))
        changed = cache.changed()
        self.assertEqual(
            changed,
            {(
                "Are you thinking of pledging our friendly fraternity?",
                "¿Estás pensando en comprometer nuestra fraternidad amiga?",
            ): "¿Estás pensando en unirte a nuestra fraternidad?"},
        )
        self.assertIn("Wow", [r["src"] for r in cache.items.values() if r.get("rejected")][0])
        stats = review.stats(self.units(), cache)
        self.assertEqual((stats["total"], stats["reviewed"], stats["changed"], stats["rejected"]), (4, 3, 1, 1))

    def test_reviewed_lines_are_not_sent_again(self):
        cache = review.ReviewCache(self.dir / "revision.json")
        review.run_review(self.units(), FakeReviewer(), Glossary([]), cache)
        again = FakeReviewer()
        review.run_review(self.units(), again, Glossary([]), review.ReviewCache(self.dir / "revision.json"))
        sent = [i.text for b in again.batches for i in b.items]
        self.assertEqual(sent, ["I don't know, to be honest."])  # solo la que no devolvió el motor

    def test_an_english_answer_is_rejected(self):
        unit = review.ReviewUnit("Hello there", "Hola", None)
        self.assertEqual(review._decide(unit, "Hello there"), ("Hola", "devolvió el inglés sin traducir"))
        self.assertEqual(review._decide(unit, ""), ("Hola", "respuesta vacía"))
        self.assertEqual(review._decide(unit, "Hola a todos"), ("Hola a todos", ""))

    def test_fatal_errors_keep_what_was_reviewed(self):
        class Dies(FakeReviewer):
            def review(self, batch):
                if len(self.batches) >= 1:
                    raise EngineError("Se agotó la cuota diaria del servicio.", fatal=True)
                return super().review(batch)

        cache = review.ReviewCache(self.dir / "revision.json")
        units = [review.ReviewUnit(f"Line {i}", f"Línea {i}", None) for i in range(6)]
        with self.assertRaises(EngineError):
            review.run_review(units, Dies(), Glossary([]), cache, batch_size=2)
        self.assertEqual(len(review.ReviewCache(self.dir / "revision.json").items), 2)  # lo del primer lote

    def test_bad_responses_split_the_batch(self):
        class Picky(FakeReviewer):
            def review(self, batch):
                if len(batch.items) > 1:
                    raise BadResponse("no es JSON")
                return super().review(batch)

        cache = review.ReviewCache(self.dir / "revision.json")
        result = review.run_review(self.units(), Picky(), Glossary([]), cache, batch_size=20)
        self.assertEqual(result.reviewed, 3)

    def test_apply_replaces_only_the_matching_translation_and_keeps_ids_and_comments(self):
        pair = ("Are you thinking of pledging our friendly fraternity?",
                "¿Estás pensando en comprometer nuestra fraternidad amiga?")
        new_text, n = review.apply_to_text(TL, {pair: "¿Estás pensando en unirte a nuestra fraternidad?"})
        self.assertEqual(n, 1)
        self.assertIn('mg "¿Estás pensando en unirte a nuestra fraternidad?"', new_text)
        self.assertIn('# mg "Are you thinking of pledging our friendly fraternity?"', new_text)  # el original no cambia
        self.assertIn("translate Spanish ep1_a_11111111:", new_text)
        # una pareja distinta (otra traducción del mismo original) no se toca
        _, none = review.apply_to_text(TL, {(pair[0], "otra traducción"): "x"})
        self.assertEqual(none, 0)
        # las entradas `old/new` también se corrigen
        text, n2 = review.apply_to_text(TL, {("Description", "Descripción"): "Descripción del personaje"})
        self.assertEqual(n2, 1)
        self.assertIn('new "Descripción del personaje"', text)

    def test_apply_to_tl_skips_files_written_by_this_app(self):
        pair = ("Extra text that this app translated.", "Texto extra que tradujo esta app.")
        files, total = review.apply_to_tl(self.tl, {pair: "otra"})
        self.assertEqual((files, total), ({}, 0))

    def test_report_lists_where_each_change_is(self):
        cache = review.ReviewCache(self.dir / "revision.json")
        review.run_review(self.units(), FakeReviewer(), Glossary([]), cache)
        text = review.report_text(self.units(), cache)
        self.assertIn("1 cambios sugeridos", text)
        self.assertIn("ANTES: ¿Estás pensando en comprometer nuestra fraternidad amiga?", text)
        self.assertIn("AHORA: ¿Estás pensando en unirte a nuestra fraternidad?", text)
        self.assertIn("script.rpy", text)
        self.assertIn("Respuestas descartadas", text)


class PipelineReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "juego"
        self.tl = root / "game" / "tl" / "Spanish"
        self.tl.mkdir(parents=True)
        (self.tl / "script.rpy").write_text(TL, encoding="utf-8")
        self.info = SimpleNamespace(root=root, game_dir=root / "game", need_collect=False, name="Juego")
        self.ws = pipeline.Workspace(Path(self.tmp.name) / "ws")
        self.ws.base.mkdir()
        patcher = mock.patch.object(pipeline, "suggest_glossary", return_value=Glossary([]))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_notes_reach_the_engine_and_the_review_is_saved_without_touching_the_game(self):
        pipeline.save_notes(self.ws, "Novela universitaria. «pledge» = ingresar a una fraternidad.")
        engine = FakeReviewer()
        with mock.patch.object(pipeline, "create_engine", return_value=engine):
            result = pipeline.review_translations(self.info, self.ws, "Spanish", "gemini", {}, 20)
        self.assertEqual(result.changed, 1)
        self.assertIn("pledge", engine.notes)
        self.assertTrue(self.ws.review_cache_file.is_file())
        self.assertIn("unirte a nuestra fraternidad", self.ws.review_report_file.read_text(encoding="utf-8-sig"))
        self.assertIn("comprometer", (self.tl / "script.rpy").read_text(encoding="utf-8"))  # aún sin aplicar

    def test_apply_writes_with_backup_and_a_second_apply_does_nothing(self):
        with mock.patch.object(pipeline, "create_engine", return_value=FakeReviewer()):
            pipeline.review_translations(self.info, self.ws, "Spanish", "gemini", {}, 20)
        self.assertEqual(pipeline.apply_review(self.info, self.ws, "Spanish"), 1)
        text = (self.tl / "script.rpy").read_text(encoding="utf-8")
        self.assertIn("unirte a nuestra fraternidad", text)
        self.assertNotIn("comprometer nuestra", text)
        backups = list(self.ws.backups.glob("tl_Spanish_antes_de_mejorar_*"))
        self.assertEqual(len(backups), 1)
        self.assertIn("comprometer", (backups[0] / "script.rpy").read_text(encoding="utf-8"))
        self.assertEqual(pipeline.apply_review(self.info, self.ws, "Spanish"), 0)

    def test_engines_that_cannot_review_are_refused_before_anything_is_sent(self):
        engine = MicrosoftEngine({"api_key": "x"})
        with mock.patch.object(pipeline, "create_engine", return_value=engine):
            with self.assertRaises(EngineError) as ctx:
                pipeline.review_translations(self.info, self.ws, "Spanish", "microsoft", {}, 20)
        self.assertTrue(ctx.exception.fatal)

    def test_status_counts_lines_and_requests(self):
        st = pipeline.review_status(self.info, self.ws, "Spanish", batch_size=2)
        self.assertEqual((st["total"], st["pending"], st["requests"]), (4, 4, 2))

    def test_notes_are_trimmed_and_removed_when_empty(self):
        pipeline.save_notes(self.ws, "  hola  ")
        self.assertEqual(pipeline.load_notes(self.ws), "hola")
        pipeline.save_notes(self.ws, "   ")
        self.assertEqual(pipeline.load_notes(self.ws), "")
        self.assertFalse(self.ws.notes_file.exists())


class ReviewPromptTests(unittest.TestCase):
    def test_review_message_carries_the_current_translation_and_the_prompt_the_notes(self):
        batch = Batch(items=[Item("1", "pledging", "Magnar", "comprometer")], before=[("Perseo", "Hi")], after=[])
        msg = llm.build_review_message(batch)
        self.assertIn('"current": "comprometer"', msg)
        self.assertIn('"speaker": "Magnar"', msg)
        self.assertNotIn("current", llm.build_user_message(batch))  # traducir no manda la traducción
        target = languages.get("spanish")
        prompt = llm.review_system_prompt(target, "Juego de fraternidades")
        self.assertIn("EXISTING", prompt)
        self.assertIn("Juego de fraternidades", prompt)
        self.assertNotIn("Juego de fraternidades", llm.review_system_prompt(target))
        self.assertIn("Juego de fraternidades", llm.system_prompt(target, "Juego de fraternidades"))

    def test_llm_engines_review_with_the_review_prompt(self):
        class Probe(llm.LLMEngine):
            name = "probe"
            label = "Probe"

            def _complete(self, system, user):
                self.system, self.user = system, user
                return '{"translations": [{"id": "1", "text": "unirte"}]}'

        engine = Probe({"api_key": "x"})
        engine.notes = "nota"
        out = engine.review(Batch(items=[Item("1", "pledging", None, "comprometer")]))
        self.assertEqual(out, {"1": "unirte"})
        self.assertIn("EXISTING", engine.system)
        self.assertIn("nota", engine.system)
        self.assertIn("comprometer", engine.user)

    def test_microsoft_cannot_review(self):
        self.assertFalse(MicrosoftEngine.can_review)
        with self.assertRaises(EngineError):
            MicrosoftEngine({"api_key": "x"}).review(Batch(items=[]))


if __name__ == "__main__":
    unittest.main()
