import unittest

from traductor.pending import PENDING, TRANSLATED, TRIVIAL, has_translatable_text, parse_tl_text

SAMPLE = '''﻿# TODO: Translation updated at 2026-10-15 01:21

# game/script.rpy:34
translate spanish start_46aff2d5:

    # "While there is no NTR."
    "Aunque no hay NTR."

# game/script.rpy:36
translate spanish start_8c1d63db:

    # "NTR Lite is no penetration."
    "NTR Lite is no penetration."

# game/script.rpy:55
translate spanish start_97f745ed:

    # c "That was [name]!"
    c "Eso fue [name]!"

# game/script.rpy:56
translate spanish start_aaaaaaaa:

    # c "Same line, still English!"
    c "Same line, still English!"

# game/script.rpy:57
translate spanish start_bbbbbbbb:

    # j "..."
    j "..."

# game/script.rpy:58
translate spanish start_cccccccc:

    # c "Hi."
    c "Hola."

    # c "Bye."
    c "Bye."

translate spanish strings:

    # game/options.rpy:15
    old "Demo Game"
    new "Demo Game"

    # game/screens.rpy:10
    old "Back"
    new "Atrás"

    old "He said \\"hi\\""
    new "Dijo \\"hola\\""

    old "[name]"
    new "[name]"

translate spanish python:

    gui.text_font = "x.ttf"
'''


class PendingTests(unittest.TestCase):
    def setUp(self):
        self.entries = {(e.kind, e.key): e for e in parse_tl_text(SAMPLE.lstrip("﻿"), "script.rpy")}

    def status(self, kind, key):
        return self.entries[(kind, key)].status

    def test_dialogue_translated(self):
        self.assertEqual(self.status("dialogue", "start_46aff2d5"), TRANSLATED)
        self.assertEqual(self.status("dialogue", "start_97f745ed"), TRANSLATED)

    def test_dialogue_pending_when_equal_to_comment(self):
        e = self.entries[("dialogue", "start_8c1d63db")]
        self.assertEqual(e.status, PENDING)
        self.assertEqual(e.who, None)
        self.assertEqual(e.original, "NTR Lite is no penetration.")
        self.assertEqual(self.entries[("dialogue", "start_aaaaaaaa")].who, "c")

    def test_dialogue_without_text_is_trivial(self):
        self.assertEqual(self.status("dialogue", "start_bbbbbbbb"), TRIVIAL)

    def test_each_dialogue_of_a_block_is_its_own_entry(self):
        self.assertEqual(self.status("dialogue", "start_cccccccc"), TRANSLATED)  # "Hi." -> "Hola."
        self.assertEqual(self.status("dialogue", "start_cccccccc#2"), PENDING)  # "Bye." sin traducir
        self.assertEqual(self.entries[("dialogue", "start_cccccccc#2")].original, "Bye.")

    def test_voice_and_other_statements_are_not_dialogue(self):
        text = (
            'translate spanish voiced_239ac509:\n\n'
            '    # voice my_audio["19"]\n'
            '    # nar "A knowing sense of shock plays on her face."\n'
            '    voice my_audio["19"]\n'
            '    nar "A knowing sense of shock plays on her face."\n'
        )
        entries = parse_tl_text(text, "x.rpy")
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual((e.key, e.who, e.status), ("voiced_239ac509", "nar", PENDING))
        self.assertEqual(e.original, "A knowing sense of shock plays on her face.")  # no "19"

    def test_decompiled_block_without_comments(self):
        text = 'translate spanish a_b:\n\n    voice "x.ogg"\n    c "Hola."\n    c "Adiós."\n'
        got = [(e.key, e.translated) for e in parse_tl_text(text)]
        self.assertEqual(got, [("a_b", "Hola."), ("a_b#2", "Adiós.")])

    def test_strings(self):
        self.assertEqual(self.status("string", "Demo Game"), PENDING)
        self.assertEqual(self.status("string", "Back"), TRANSLATED)
        self.assertEqual(self.status("string", 'He said \\"hi\\"'), TRANSLATED)
        self.assertEqual(self.status("string", "[name]"), TRIVIAL)

    def test_source_ref_and_python_block_ignored(self):
        self.assertEqual(self.entries[("dialogue", "start_46aff2d5")].source_ref, "game/script.rpy:34")
        self.assertEqual(self.entries[("string", "Demo Game")].source_ref, "game/options.rpy:15")
        self.assertNotIn(("dialogue", "python"), self.entries)

    def test_has_translatable_text(self):
        self.assertFalse(has_translatable_text("..."))
        self.assertFalse(has_translatable_text("{i}[name]{/i}"))
        self.assertFalse(has_translatable_text("%s\\n"))
        self.assertTrue(has_translatable_text("{i}Hello{/i}"))
        self.assertTrue(has_translatable_text("¡Sí!"))


if __name__ == "__main__":
    unittest.main()
