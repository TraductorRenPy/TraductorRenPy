import tempfile
import unittest
from pathlib import Path

from traductor import uitweaks


class UiTweaksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.game = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_render_has_no_leftover_placeholders(self):
        for mode in ("text", "compact"):
            code = uitweaks.render(mode)
            self.assertNotIn("@", code)
            self.assertIn("style.say_window.background", code)
            self.assertIn('{alpha=.5}', code)  # las llaves del filtro quedan intactas
            self.assertIn(f"modo: {mode}", code.splitlines()[0])

    def test_soft_mode_only_touches_outlines(self):
        code = uitweaks.render("soft")
        self.assertNotIn("@", code)
        self.assertIn("style.say_dialogue.outlines", code)
        self.assertIn("style.say_label.outlines", code)
        for forbidden in ("background", "color", "ysize", "filter"):
            self.assertNotIn(forbidden, code)
        path = uitweaks.apply(self.game, "soft")
        self.assertEqual(uitweaks.current_mode(self.game), "soft")
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_soft_mode_overrides_custom_say_screen_with_inline_outlines(self):
        (self.game / "tl").mkdir()
        (self.game / "tl" / "x.rpy").write_text("screen say(who, what):\n    text what\n", encoding="utf-8")
        (self.game / "a.rpy").write_text(
            "screen say(who, what):\n    text what outlines [(1, \"#fff\", 0, 0)]\n", encoding="utf-8"
        )
        (self.game / "b.rpy").write_text(
            "init 10 screen say(who, what):\n"
            "    style_prefix \"say\"\n"
            "    fixed:\n"
            "        text who id \"who\":\n"
            "            outlines [(absolute(5), \"#000000E6\", absolute(1), absolute(2)), (absolute(2), \"#000\", 0, 0)]\n"
            "        text what id \"what\":\n"
            "            size 40\n"
            "            outlines [(absolute(5), \"#000000E6\", absolute(1), absolute(2))]\n"
            "\n"
            "screen other():\n"
            "    text \"otra\"\n",
            encoding="utf-8",
        )
        path = uitweaks.apply(self.game, "soft")
        code = path.read_text(encoding="utf-8-sig")
        self.assertIn("init 999 screen say(who, what):", code)
        self.assertEqual(code.count('[(_tb_px, "#00000090", 0, 0)]'), 4)  # 2 de estilo + 2 de pantalla
        self.assertNotIn("absolute(5)", code)
        self.assertIn('text who id "who":', code)  # el resto de la pantalla se conserva
        self.assertIn("size 40", code)
        self.assertNotIn("screen other", code)  # solo la pantalla say
        self.assertNotIn("(1, \"#fff\"", code)  # la de menor prioridad no se usa

    def test_init_offset_decides_which_say_screen_wins(self):
        # b.rpy: init 10 (explícito) | c.rpy: `init offset = 160` + `init screen say` => 160 > 10
        (self.game / "b.rpy").write_text(
            'init 10 screen say(who, what):\n    text what:\n        color "#111111"\n'
            '        outlines [(5, "#000", 0, 0)]\n',
            encoding="utf-8",
        )
        (self.game / "c.rpy").write_text(
            'init offset = 160\n\ninit screen say(who, what):\n'
            '    text who:\n        color custom_name_color_for(who)\n        outlines [(3, "#000", 0, 2)]\n'
            '    text what:\n        outlines [(5, "#000", 0, 0)]\n',
            encoding="utf-8",
        )
        (self.game / "d.rpy").write_text(
            'init offset = 0\n\nscreen say(who, what):\n    text what:\n        outlines [(9, "#000", 0, 0)]\n',
            encoding="utf-8",
        )
        code = uitweaks.apply(self.game, "soft").read_text(encoding="utf-8-sig")
        self.assertIn("custom_name_color_for(who)", code)  # ganó la de c.rpy
        self.assertNotIn('color "#111111"', code)
        self.assertNotIn("(9,", code)
        self.assertEqual(code.count('[(_tb_px, "#00000090", 0, 0)]'), 4)

    def test_soft_mode_without_inline_outlines_adds_no_screen(self):
        (self.game / "a.rpy").write_text("screen say(who, what):\n    text what\n", encoding="utf-8")
        code = uitweaks.apply(self.game, "soft").read_text(encoding="utf-8-sig")
        self.assertNotIn("screen say", code)

    def test_text_mode_removes_background(self):
        self.assertIn("style.say_window.background = None", uitweaks.render("text"))

    def test_apply_current_and_revert(self):
        self.assertEqual(uitweaks.current_mode(self.game), "original")
        path = uitweaks.apply(self.game, "text")
        raw = path.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", raw)
        self.assertEqual(uitweaks.current_mode(self.game), "text")
        uitweaks.apply(self.game, "compact")
        self.assertEqual(uitweaks.current_mode(self.game), "compact")
        (self.game / "zz_ui_tweaks.rpyc").write_bytes(b"x")
        self.assertIsNone(uitweaks.apply(self.game, "original"))
        self.assertFalse(path.exists())
        self.assertFalse((self.game / "zz_ui_tweaks.rpyc").exists())

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            uitweaks.render("raro")


if __name__ == "__main__":
    unittest.main()
