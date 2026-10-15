import tempfile
import unittest
from pathlib import Path

from traductor import install, translate
from traductor.pending import scan_tl
from traductor.validate import check, repair_tags, validate


class ValidateTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(check("Hi [name]! {i}Wow{/i}\\n", "¡Hola, [name]! {i}Guau{/i}\\n"), [])

    def test_missing_and_extra_tokens(self):
        r = check("Hi [name]", "Hola")
        self.assertTrue(any("tokens distintos" in x for x in r))
        self.assertTrue(check("Hi", "Hola [name]"))

    def test_syntax_breakers(self):
        self.assertTrue(any("comillas" in x for x in check("Hi", 'Dijo "hola"')))
        self.assertEqual(check("Hi", 'Dijo \\"hola\\"'), [])  # comillas escapadas nuevas: válidas
        self.assertEqual(check('Say \\"hi\\"', "Di hola"), [])  # y quitarlas también
        self.assertTrue(any("salto" in x for x in check("Hi", "a\nb")))
        self.assertTrue(any("barra" in x for x in check("Hi", "Hola\\")))
        self.assertTrue(check("Hi", "  "))

    def test_repair_closing_tag(self):
        orig = "{i}{alpha=.5}Hello{/alpha}{/i}"
        bad = "{i}{alpha=.5}Hola{/alpha}{i}"
        self.assertTrue(check(orig, bad))
        self.assertEqual(repair_tags(orig, bad), "{i}{alpha=.5}Hola{/alpha}{/i}")
        text, reasons, repaired = validate(orig, bad)
        self.assertEqual((text, reasons, repaired), ("{i}{alpha=.5}Hola{/alpha}{/i}", [], True))

    def test_q_prefix_artifact_is_stripped(self):
        text, reasons, repaired = validate("Hello there", "q=Hola, ¿qué tal?")
        self.assertEqual((text, reasons, repaired), ("Hola, ¿qué tal?", [], True))
        # si el original ya empezaba con q=, se respeta
        self.assertEqual(validate("q=1", "q=2")[0], "q=2")

    def test_no_repair_when_variable_differs(self):
        self.assertIsNone(repair_tags("Hi [name]", "Hola [nombre]"))
        text, reasons, _ = validate("Hi [name]", "Hola [nombre]")
        self.assertIsNone(text)
        self.assertTrue(reasons)


TL = '''﻿# TODO: Translation updated at 2026-10-15 01:21

# game/script.rpy:1
translate spanish start_aaaaaaaa:

    # c "Hello [name]!"
    c "Hello [name]!"

# game/script.rpy:2
translate spanish start_bbbbbbbb:

    # c "Already done."
    c "Ya hecho."

# game/script.rpy:3
translate spanish start_cccccccc:

    # "{i}Bad tag{/i}"
    "{i}Bad tag{/i}"

# game/script.rpy:4
translate spanish start_dddddddd:

    # j "Not in cache at all."
    j "Not in cache at all."

# game/script.rpy:5
translate spanish start_eeeeeeee:

    # j happy "Quote: \\"yes\\""
    j happy "Quote: \\"yes\\""

translate spanish strings:

    # game/options.rpy:15
    old "Start"
    new "Start"

    old "Quit"
    new "Salir"

translate spanish python:

    gui.x = 1
'''


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.tl = self.dir / "game" / "tl" / "spanish"
        self.tl.mkdir(parents=True)
        # con CRLF para comprobar que se normaliza a LF
        (self.tl / "script.rpy").write_bytes(TL.replace("\n", "\r\n").encode("utf-8"))
        self.cache = translate.Cache(self.dir / "c.json")
        self.cache.put("Hello [name]!", "¡Hola, [name]!", "t")
        self.cache.put("{i}Bad tag{/i}", "{i}Etiqueta mala{i}", "t")  # reparable
        self.cache.put('Quote: \\"yes\\"', 'Cita: "si"', "t")  # inválida (comillas)
        self.cache.put("Start", "Comenzar", "t")

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_counts(self):
        res = install.apply_cache_to_tl(self.tl, self.cache)
        self.assertEqual((res.applied, res.repaired, len(res.failed), res.untranslated), (3, 1, 1, 1))
        self.assertEqual(res.failed[0].file, "script.rpy")
        self.assertEqual(res.failed[0].line, 31)  # la línea traducida, no el comentario

    def test_write_preserves_everything_else(self):
        res = install.apply_cache_to_tl(self.tl, self.cache)
        before, after = install.write_changes(res, self.tl, self.dir / "bak", "t")
        raw = (self.tl / "script.rpy").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))  # BOM
        self.assertNotIn(b"\r", raw)  # LF
        text = raw.decode("utf-8-sig")
        self.assertIn('    c "¡Hola, [name]!"', text)
        self.assertIn('    # c "Hello [name]!"', text)  # comentario intacto
        self.assertIn('    "{i}Etiqueta mala{/i}"', text)  # tag reparado
        self.assertIn('    new "Comenzar"', text)
        self.assertIn('    old "Start"', text)
        self.assertIn('    c "Ya hecho."', text)
        self.assertIn('    j "Not in cache at all."', text)  # sin traducción: queda
        self.assertIn('    j happy "Quote: \\"yes\\""', text)  # fallo: queda en inglés
        self.assertEqual(len(before.pending) - len(after.pending), 3)
        self.assertTrue(any((self.dir / "bak").iterdir()))  # hay respaldo

    def test_second_run_changes_nothing(self):
        res = install.apply_cache_to_tl(self.tl, self.cache)
        install.write_changes(res, self.tl, self.dir / "bak", "t")
        again = install.apply_cache_to_tl(self.tl, self.cache)
        self.assertEqual((again.applied, again.changes), (0, {}))

    def test_block_with_voice_line_translates_the_real_dialogue(self):
        block = (
            '\ntranslate spanish evil_aaaaaaaa:\n\n'
            '    # voice my_audio["19"]\n'
            '    # nar "A knowing sense of shock."\n'
            '    voice my_audio["19"]\n'
            '    nar "A knowing sense of shock."\n'
        )
        with open(self.tl / "script.rpy", "ab") as f:
            f.write(block.encode("utf-8"))
        self.cache.put("A knowing sense of shock.", "Una sensación de sorpresa.", "t")
        res = install.apply_cache_to_tl(self.tl, self.cache)
        install.write_changes(res, self.tl, self.dir / "bak", "t")
        text = (self.tl / "script.rpy").read_text(encoding="utf-8-sig")
        self.assertIn('    nar "Una sensación de sorpresa."', text)
        self.assertIn('    voice my_audio["19"]', text)  # la línea de audio queda intacta
        self.assertIn('    # voice my_audio["19"]', text)

    def test_glossary_enforces_exact_terms_even_on_existing_translations(self):
        from traductor.glossary import Glossary, Term

        block = (
            '\n# game/options.rpy:17\ntranslate spanish title_aaaaaaaa:\n\n'
            '    # "Demo Game"\n    "Juego de Demostración"\n'
            'translate spanish strings:\n\n    old "Demo Game"\n    new "Juego de Demostración"\n\n'
            '    old "Unknown Man"\n    new "Unknown Man"\n'
        )
        with open(self.tl / "script.rpy", "ab") as f:
            f.write(block.encode("utf-8"))
        glossary = Glossary([Term("Demo Game"), Term("Unknown Man", "Hombre desconocido")])
        res = install.apply_cache_to_tl(self.tl, self.cache, glossary)
        install.write_changes(res, self.tl, self.dir / "bak", "t")
        text = (self.tl / "script.rpy").read_text(encoding="utf-8-sig")
        self.assertIn('    old "Demo Game"\n    new "Demo Game"', text)  # corregido
        self.assertIn('    # "Demo Game"\n    "Demo Game"', text)  # también en diálogos
        self.assertIn('    old "Unknown Man"\n    new "Hombre desconocido"', text)  # pendiente -> glosario
        self.assertGreaterEqual(res.glossary_fixed, 2)
        again = install.apply_cache_to_tl(self.tl, self.cache, glossary)
        self.assertEqual(again.glossary_fixed, 0)  # idempotente

    def test_duplicates_get_same_translation(self):
        extra = (
            '\n# game/script.rpy:9\ntranslate spanish start_ffffffff:\n\n'
            '    # c "Hello [name]!"\n    c "Hello [name]!"\n'
        )
        with open(self.tl / "script.rpy", "ab") as f:
            f.write(extra.encode("utf-8"))
        res = install.apply_cache_to_tl(self.tl, self.cache)
        self.assertEqual(res.applied, 4)

    def test_existing_language_setup_is_respected(self):
        game = self.dir / "game"
        mine = 'define config.default_language = "spanish"\nlabel before_main_menu:\n    $ renpy.change_language("spanish")\n    return\n'
        (game / "zz_spanish.rpy").write_text(mine, encoding="utf-8")
        install.write_language_file(game, "spanish", self.dir / "bak")
        self.assertEqual((game / "zz_spanish.rpy").read_text(encoding="utf-8"), mine)
        self.assertFalse((self.dir / "bak").exists())

    def test_language_file(self):
        game = self.dir / "game"
        path = install.write_language_file(game, "spanish", self.dir / "bak")
        raw = path.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn('define config.language = "spanish"', raw.decode("utf-8-sig"))
        self.assertNotIn(b"\r", raw)
        install.write_language_file(game, "spanish", self.dir / "bak")  # idempotente
        self.assertFalse((self.dir / "bak").exists())


if __name__ == "__main__":
    unittest.main()
