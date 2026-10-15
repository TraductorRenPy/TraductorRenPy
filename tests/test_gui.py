import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from traductor import about, i18n, settings


def all_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from all_widgets(child)


def button_texts(root):
    return [w.cget("text") for w in all_widgets(root) if w.winfo_class() == "TButton"]


class GuiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.multiple(
            settings, APP_DIR=Path(self.tmp.name), SETTINGS_FILE=Path(self.tmp.name) / "settings.json"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(i18n.set_language, "es")

    def make_app(self, ui="es"):
        from traductor.gui import App

        cfg = settings.load()
        cfg["ui_language"] = ui
        cfg["sdk_path"] = "no-existe"  # evita que busque el SDK real durante la prueba
        settings.save(cfg)
        try:
            app = App()
        except tk.TclError as exc:  # sin pantalla (CI sin entorno gráfico)
            self.skipTest(f"Tk no disponible: {exc}")
        self.addCleanup(self._safe_destroy, app)
        app.update()
        return app

    @staticmethod
    def _safe_destroy(app):
        try:
            app.destroy()
        except tk.TclError:
            pass  # ya estaba destruida

    def test_spanish_and_english_windows_build(self):
        es = self.make_app("es")
        self.assertIn("Ayuda", button_texts(es))
        en_app = self.make_app("en")
        texts = button_texts(en_app)
        self.assertIn("Help", texts)
        self.assertIn("About", texts)
        self.assertTrue(any("Translate this game automatically" in t for t in texts))
        self.assertTrue(any(t.startswith("1. Review the game") for t in texts))

    def test_donate_button_only_with_url(self):
        with mock.patch.object(about, "DONATE_URL", ""):
            app = self.make_app("es")
            self.assertFalse(any("Apoyar" in t for t in button_texts(app)))
        self._safe_destroy(app)
        with mock.patch.object(about, "DONATE_URL", "https://example.org/donate"):
            app2 = self.make_app("es")
            self.assertTrue(any("Apoyar" in t for t in button_texts(app2)))
            with mock.patch("webbrowser.open") as opened:
                app2.open_donate()
            opened.assert_called_once_with("https://example.org/donate")

    def test_report_and_feedback_buttons_only_with_urls(self):
        with mock.patch.object(about, "REPO_URL", ""), mock.patch.object(about, "FEEDBACK_URL", ""):
            app = self.make_app("es")
            texts = button_texts(app)
            self.assertFalse(any("Reportar" in t or "opinión" in t for t in texts))
        self._safe_destroy(app)
        with mock.patch.object(about, "REPO_URL", "https://github.com/u/r"), \
                mock.patch.object(about, "FEEDBACK_URL", "https://example.org/form"):
            app2 = self.make_app("es")
            texts = button_texts(app2)
            self.assertTrue(any("Reportar un problema" in t for t in texts))
            self.assertTrue(any("Dar opinión" in t for t in texts))
            with mock.patch("webbrowser.open") as opened:
                app2.open_feedback()
            opened.assert_called_once_with("https://example.org/form")
            app2.open_report()
            app2.update()

    def test_target_language_selector(self):
        app = self.make_app("es")
        self.assertEqual(app._language(), "spanish")
        app.lang_var.set("Français / French")
        self.assertEqual(app._language(), "french")
        app.lang_var.set("swedish")  # un idioma que no está en la lista se acepta tal cual
        self.assertEqual(app._language(), "swedish")

    def test_snapshot_lets_worker_threads_avoid_tk_variables(self):
        app = self.make_app("es")
        app.game_var.set("  C:\\mi juego  ")
        app.lang_var.set("Français / French")
        app.batch_var.set(37)
        app._take_snapshot()
        self.assertEqual(app._snap["game"], "C:\\mi juego")
        self.assertEqual(app._snap["language"], "french")
        self.assertEqual(app._snap["batch"], 37)
        self.assertIn(app._snap["engine"], ("grok", "gemini", "microsoft"))
        self.assertIsInstance(app._snap["has_key"], bool)

        import threading
        seen = {}

        def worker():  # un hilo no debe necesitar variables de Tk
            seen["language"] = app._snap["language"]

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        self.assertEqual(seen["language"], "french")

    def test_help_and_about_open(self):
        app = self.make_app("en")
        app.open_help()
        app.open_about()
        app.update()


if __name__ == "__main__":
    unittest.main()
