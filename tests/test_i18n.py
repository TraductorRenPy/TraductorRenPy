import ast
import unittest
from pathlib import Path

from traductor import i18n, workflow
from traductor.engines import ENGINES
from traductor.i18n_en import EN, LOG_PATTERNS
from traductor.uitweaks import MODES

PKG = Path(__file__).resolve().parent.parent / "traductor"


def literal_calls(path: Path, func_names):
    """Textos constantes pasados como primer argumento a tr(...) / self._run(...)."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        first = node.args[0]
        if name in func_names and isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.append(first.value)
    return found


class I18nTests(unittest.TestCase):
    def setUp(self):
        self.saved = i18n.current()

    def tearDown(self):
        i18n.set_language(self.saved)

    def test_every_gui_text_has_an_english_version(self):
        texts = literal_calls(PKG / "gui.py", {"tr", "_run"})
        self.assertGreater(len(texts), 100)
        missing = sorted({t for t in texts if t not in EN})
        self.assertEqual(missing, [], "faltan en i18n_en.EN")

    def test_workflow_engine_and_mode_texts_are_translated(self):
        texts = [s.title for s in workflow.STEPS] + [s.what for s in workflow.STEPS]
        texts += [cls.key_help for cls in ENGINES.values() if cls.key_help]
        texts += list(MODES.values())
        self.assertEqual(sorted({t for t in texts if t not in EN}), [])

    def test_translation_placeholders_match_the_original(self):
        import re

        for es, en in EN.items():
            self.assertEqual(sorted(re.findall(r"\{(\w+)\}", es)), sorted(re.findall(r"\{(\w+)\}", en)), es)
        for es, en in LOG_PATTERNS:
            self.assertTrue(set(re.findall(r"\{(\w+)\}", en)) <= set(re.findall(r"\{(\w+)\}", es)), es)

    def test_tr_switches_language_and_formats(self):
        i18n.set_language("es")
        self.assertEqual(i18n.tr("Ayuda"), "Ayuda")
        self.assertEqual(i18n.tr("Licencia {name}. Software libre.", name="MIT"), "Licencia MIT. Software libre.")
        i18n.set_language("en")
        self.assertEqual(i18n.tr("Ayuda"), "Help")
        self.assertEqual(i18n.tr("Licencia {name}. Software libre.", name="MIT"), "MIT license. Free software.")
        self.assertEqual(i18n.tr("texto sin traducción"), "texto sin traducción")

    def test_log_patterns(self):
        i18n.set_language("en")
        self.assertEqual(i18n.tr_log("Escritos 4 archivos; ids y comentarios intactos."),
                         "Wrote 4 files; ids and comments intact.")
        self.assertEqual(i18n.tr_log("  Lote 3/24: 20/20 traducidos."), "  Batch 3/24: 20/20 translated.")
        self.assertEqual(i18n.tr_log("tl/spanish: 9545 -> 9643 entradas (+98)."), "tl/spanish: 9545 -> 9643 entries (+98).")
        self.assertEqual(
            i18n.tr_log("Escritas 516 traducciones (8 reparadas); fallaron validación: 0; sin traducir: 0."),
            "Written 516 translations (8 repaired); failed validation: 0; untranslated: 0.",
        )
        self.assertEqual(
            i18n.tr_log("Se escribirían 3 traducciones (0 reparadas); fallaron validación: 1; sin traducir: 2."),
            "Would write 3 translations (0 repaired); failed validation: 1; untranslated: 2.",
        )
        self.assertEqual(i18n.tr_log("ERROR: Elige la carpeta del juego."), "ERROR: Choose the game folder.")
        self.assertEqual(i18n.tr_log("mensaje desconocido 123"), "mensaje desconocido 123")
        self.assertEqual(
            i18n.tr_log("1337 entradas: 670 traducidas, 516 pendientes, 141 ya en español, 10 sin texto traducible (nombres, '...', variables)"),
            "1337 entries: 670 translated, 516 pending, 141 already in Spanish, 10 without translatable text (names, '...', variables)",
        )

    def test_log_is_untouched_in_spanish(self):
        i18n.set_language("es")
        self.assertEqual(i18n.tr_log("Escritos 4 archivos; ids y comentarios intactos."),
                         "Escritos 4 archivos; ids y comentarios intactos.")

    def test_resolve_and_system_detection(self):
        self.assertEqual(i18n.resolve("es"), "es")
        self.assertEqual(i18n.resolve("en"), "en")
        self.assertIn(i18n.resolve("auto"), ("es", "en"))


if __name__ == "__main__":
    unittest.main()
