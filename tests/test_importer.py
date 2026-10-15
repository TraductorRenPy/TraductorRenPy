import tempfile
import unittest
from pathlib import Path

from traductor import importer, translate
from traductor.pending import TlReport, parse_tl_text

REFERENCE = '''# game/script.rpy:1
translate spanish start_aaaaaaaa:

    # c "Hello [name]!"
    c "¡Hola, [name]!"

# game/script.rpy:2
translate spanish start_bbbbbbbb:

    # j "How are you?"
    j "How are you?"

# game/script.rpy:3
translate spanish start_cccccccc:

    # "Two {i}tags{/i} here."
    "Dos etiquetas aquí."

# game/script.rpy:4
translate spanish old_label_dddddddd:

    # c "See you later."
    c "Hasta luego."

translate spanish strings:

    old "Start"
    new "Comenzar"

    old "Quit"
    new "Quit"
'''

# tl decompilado: sin los comentarios con el inglés
REFERENCE_NO_COMMENTS = '''translate spanish start_eeeeeeee:

    c "Buenos días."
'''

TARGET = '''# game/script.rpy:1
translate spanish start_aaaaaaaa:

    # c "Hello [name]!"
    c "Hello [name]!"

# game/script.rpy:2
translate spanish start_bbbbbbbb:

    # j "How are you?"
    j "How are you?"

# game/script.rpy:3
translate spanish start_cccccccc:

    # "Two {i}tags{/i} here."
    "Two {i}tags{/i} here."

# game/script.rpy:4
translate spanish new_label_ffffffff:

    # c "See you later."
    c "See you later."

# game/script.rpy:5
translate spanish start_eeeeeeee:

    # c "Good morning."
    c "Good morning."

# game/script.rpy:6
translate spanish start_gggggggg:

    # c "Brand new line."
    c "Brand new line."

# game/script.rpy:7
translate spanish start_hhhhhhhh:

    # c "One."
    c "One."

    # c "Two."
    c "Two."

translate spanish strings:

    old "Start"
    new "Start"

    old "Quit"
    new "Quit"
'''


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        tl = self.dir / "tl"
        tl.mkdir()
        (tl / "a.rpy").write_text(REFERENCE, encoding="utf-8-sig")
        (tl / "b.rpy").write_text(REFERENCE_NO_COMMENTS, encoding="utf-8")
        self.ref = importer.load_reference(tl)
        self.report = TlReport(Path("."), parse_tl_text(TARGET, "script.rpy"))
        self.cache = translate.Cache(self.dir / "c.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_reference(self):
        self.assertEqual(self.ref.by_id["start_aaaaaaaa"], "¡Hola, [name]!")
        self.assertEqual(self.ref.by_id["start_eeeeeeee"], "Buenos días.")  # sin comentario
        self.assertNotIn("start_bbbbbbbb", self.ref.by_id)  # sin traducir en la referencia
        self.assertEqual(self.ref.strings, {"Start": "Comenzar"})  # Quit == Quit se ignora
        self.assertEqual(self.ref.by_text["See you later."], "Hasta luego.")
        self.assertNotIn("Good morning.", self.ref.by_text)

    def test_apply_matches_by_id_and_text(self):
        res = importer.apply_reference(self.report, self.ref, self.cache)
        self.assertEqual(self.cache.get("Hello [name]!"), "¡Hola, [name]!")  # por id
        self.assertEqual(self.cache.get("Good morning."), "Buenos días.")  # por id, sin comentario
        self.assertEqual(self.cache.get("See you later."), "Hasta luego.")  # por texto (id cambió)
        self.assertEqual(self.cache.get("Start"), "Comenzar")  # string
        self.assertEqual((res.by_id, res.by_text), (2, 2))

    def test_rejects_changed_tokens(self):
        self.assertIsNone(self.cache.get("Two {i}tags{/i} here."))
        res = importer.apply_reference(self.report, self.ref, self.cache)
        self.assertIsNone(self.cache.get("Two {i}tags{/i} here."))  # faltan {i} {/i}
        self.assertEqual(res.rejected_tokens, 1)

    def test_remaining_counts_what_is_left(self):
        res = importer.apply_reference(self.report, self.ref, self.cache)
        # sin importar: How are you?, Two tags (tokens), Brand new line, One., Two., Quit
        self.assertEqual(res.remaining, 6)
        self.assertIsNone(self.cache.get("Brand new line."))
        self.assertIsNone(self.cache.get("One."))  # la referencia no los tiene

    def test_multi_dialogue_blocks_match_by_position(self):
        ref_tl = self.dir / "tl2"
        ref_tl.mkdir()
        (ref_tl / "m.rpy").write_text(
            'translate spanish start_hhhhhhhh:\n\n    voice "a.ogg"\n    c "Uno."\n    c "Dos."\n',
            encoding="utf-8",
        )
        ref = importer.load_reference(ref_tl)
        self.assertEqual(ref.by_id, {"start_hhhhhhhh": "Uno.", "start_hhhhhhhh#2": "Dos."})
        importer.apply_reference(self.report, ref, self.cache)
        self.assertEqual(self.cache.get("One."), "Uno.")
        self.assertEqual(self.cache.get("Two."), "Dos.")

    def test_language_name_matching(self):
        pick = importer._pick_language
        self.assertEqual(pick(["PortTE", "SpanishTE"], "spanish", lambda m: None), "SpanishTE")
        self.assertEqual(pick(["Spanish", "SpanishTE"], "spanish", lambda m: None), "Spanish")
        self.assertEqual(pick(["Spanish"], "spanish", lambda m: None), "Spanish")
        self.assertEqual(pick(["french"], "spanish", lambda m: None), "french")  # único idioma
        with self.assertRaises(FileNotFoundError):
            pick(["PortTE", "french"], "spanish", lambda m: None)

    def test_imported_engine_tag(self):
        importer.apply_reference(self.report, self.ref, self.cache)
        row = self.cache.items[translate.text_key("Hello [name]!")]
        self.assertEqual(row["engine"], "importada")

    def test_translate_job_skips_imported(self):
        importer.apply_reference(self.report, self.ref, self.cache)

        class Fake(translate.Engine):
            name = "fake"
            label = "x"

            def __init__(self):
                self.cfg, self.seen = {}, []

            def translate(self, batch):
                self.seen += [i.text for i in batch.items]
                return {i.id: "ES:" + i.text for i in batch.items}

        engine = Fake()
        units = translate.build_units(self.report)
        translate.run_job(units, engine, translate.Glossary(), self.cache)
        self.assertNotIn("Hello [name]!", engine.seen)
        self.assertIn("Brand new line.", engine.seen)


if __name__ == "__main__":
    unittest.main()
