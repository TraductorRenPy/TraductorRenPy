import tempfile
import unittest
from pathlib import Path

from traductor import extras
from traductor.extras import KNOWN, PROBABLE, scan_source

SOURCE = r'''
define c = Character("Marcus")
define config.name = "My Game Title With Words"

screen hud():
    text "Open diary"
    text "[score]"
    text "H"
    textbutton "Graphics" action Preference("display", "window")
    label "CALENDAR STATUS"
    text _("Already marked text here")
    text "Texto ya en español, no hace falta"
    add "gui/overlay.png"

label start:
    c "This is normal dialogue and it must be ignored."
    "Narration is also handled by translate blocks."
    c happy "Dialogue with attributes."
    menu:
        "A menu choice handled by Ren'Py":
            pass
    $ name = renpy.input("What is your character's first name? (8 Letter Max)")
    $ renpy.notify("Saved game, come back soon")
    $ c("A say called from python code")
    $ peek1 = "{image=evil} Dude, shut the fuck up. I'm trying to listen."
    $ hint = 'It\'s a single quoted string, with an apostrophe.'
    $ debug = "short"
    print("Error: this state doesn't exist ! Please check the docs.")
    $ color = "#ff00aa"
    play music "audio/theme song.ogg"
    $ x = "gui/some_image_name.png"
    $ y = "›"
    $ z = _("Marked with underscore function in code")

init python:
    notes = {
        1: "Eileen noticed the way you looked at her.",
        2: "ok",
    }
'''


class ExtrasTests(unittest.TestCase):
    def setUp(self):
        self.found = {f.text: f for f in scan_source(SOURCE, "game/a.rpy", ["c"])}

    def test_known_contexts(self):
        for text in (
            "Open diary", "Graphics", "CALENDAR STATUS",
            "What is your character's first name? (8 Letter Max)",
            "Saved game, come back soon", "A say called from python code",
        ):
            self.assertIn(text, self.found, text)
            self.assertEqual(self.found[text].kind, KNOWN, text)

    def test_probable_sentences(self):
        for text in (
            "{image=evil} Dude, shut the fuck up. I'm trying to listen.",
            "Eileen noticed the way you looked at her.",
        ):
            self.assertEqual(self.found[text].kind, PROBABLE, text)

    def test_single_quotes_are_normalized(self):
        self.assertIn("It's a single quoted string, with an apostrophe.", self.found)

    def test_ignored(self):
        ignored = (
            "[score]", "H", "Already marked text here", "Texto ya en español, no hace falta",
            "This is normal dialogue and it must be ignored.",
            "Narration is also handled by translate blocks.", "Dialogue with attributes.",
            "A menu choice handled by Ren'Py", "short", "ok", "#ff00aa", "gui/overlay.png",
            "audio/theme song.ogg", "gui/some_image_name.png", "\\u203A",
            "Marked with underscore function in code",
            "Error: this state doesn't exist ! Please check the docs.",
            "My Game Title With Words",
        )
        for text in ignored:
            self.assertNotIn(text, self.found, text)

    def test_line_numbers(self):
        self.assertEqual(SOURCE.splitlines()[self.found["Open diary"].line - 1].strip(), 'text "Open diary"')


class WriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tl = Path(self.tmp.name) / "tl" / "spanish"
        self.tl.mkdir(parents=True)
        (self.tl / "common.rpy").write_text(
            'translate spanish strings:\n\n    old "Graphics"\n    new "Gráficos"\n', encoding="utf-8"
        )
        self.found = [
            extras.Found("Open diary", "game/a.rpy", 3, KNOWN),
            extras.Found("Graphics", "game/a.rpy", 5, KNOWN),  # ya existe en otro archivo
            extras.Found('He said \\"hi\\"', "game/b.rpy", 9, KNOWN),
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def test_existing_olds_in_any_file(self):
        self.assertEqual(extras.existing_olds(self.tl), {"Graphics"})

    def test_write_skips_existing_and_formats(self):
        self.assertEqual(extras.write_extra_strings(self.tl, "spanish", self.found), 2)
        raw = (self.tl / extras.EXTRA_FILE).read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", raw)
        text = raw.decode("utf-8-sig")
        self.assertIn("translate spanish strings:", text)
        self.assertIn('    # game/a.rpy:3\n    old "Open diary"\n    new "Open diary"', text)
        self.assertNotIn('old "Graphics"', text)
        self.assertIn('old "He said \\"hi\\""', text)

    def test_second_run_adds_nothing_and_keeps_prior_content(self):
        extras.write_extra_strings(self.tl, "spanish", self.found)
        self.assertEqual(extras.write_extra_strings(self.tl, "spanish", self.found), 0)
        more = self.found + [extras.Found("Sound", "game/c.rpy", 1, KNOWN)]
        self.assertEqual(extras.write_extra_strings(self.tl, "spanish", more), 1)
        text = (self.tl / extras.EXTRA_FILE).read_text(encoding="utf-8-sig")
        self.assertEqual(text.count('old "Open diary"'), 1)  # sin duplicar nunca
        self.assertIn('old "Sound"', text)

    def test_new_strings_become_pending_and_all_olds_unique(self):
        from traductor.pending import scan_tl

        extras.write_extra_strings(self.tl, "spanish", self.found)
        report = scan_tl(self.tl)
        self.assertEqual(sorted(e.original for e in report.pending), ['He said \\"hi\\"', "Open diary"])
        olds = [e.original for e in report.entries if e.kind == "string"]
        self.assertEqual(len(olds), len(set(olds)))

    def test_scan_dirs_skips_tl_and_zz_files_and_dedupes(self):
        game = Path(self.tmp.name) / "game"
        (game / "tl").mkdir(parents=True)
        (game / "a.rpy").write_text('screen s():\n    text "Open diary"\n', encoding="utf-8")
        (game / "b.rpy").write_text('screen t():\n    text "Open diary"\n', encoding="utf-8")
        (game / "tl" / "x.rpy").write_text('screen u():\n    text "From tl folder"\n', encoding="utf-8")
        (game / "zz_extra.rpy").write_text('screen v():\n    text "From zz file"\n', encoding="utf-8")
        found = extras.scan_dirs([game])
        self.assertEqual([f.text for f in found], ["Open diary"])
        self.assertEqual(found[0].file, "game/a.rpy")


if __name__ == "__main__":
    unittest.main()
