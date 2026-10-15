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

    def test_language_change_restarts_the_app_only_when_confirmed(self):
        app = self.make_app("es")
        app.ui_var.set("English")
        with mock.patch("tkinter.messagebox.askyesno", return_value=False) as ask, \
                mock.patch("subprocess.Popen") as popen:
            app._ui_language_changed()
        ask.assert_called_once()
        popen.assert_not_called()
        self.assertEqual(i18n.current(), "es")  # sigue en el idioma anterior hasta reiniciar
        self.assertEqual(settings.load()["ui_language"], "en")  # pero la elección queda guardada

        with mock.patch("tkinter.messagebox.askyesno", return_value=True), \
                mock.patch("subprocess.Popen") as popen:
            app._ui_language_changed()
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], app.restart_command())

    def test_language_change_does_not_restart_during_a_job(self):
        app = self.make_app("es")
        app.busy = True
        app.ui_var.set("English")
        with mock.patch("tkinter.messagebox.showinfo") as info, \
                mock.patch("tkinter.messagebox.askyesno") as ask, \
                mock.patch("subprocess.Popen") as popen:
            app._ui_language_changed()
        info.assert_called_once()
        ask.assert_not_called()
        popen.assert_not_called()
        app.busy = False

    def test_restart_command(self):
        from traductor.gui import App
        with mock.patch.object(settings, "FROZEN", True):
            self.assertEqual(App.restart_command(), [__import__("sys").executable])
        with mock.patch.object(settings, "FROZEN", False):
            cmd = App.restart_command()
        self.assertTrue(cmd[1].endswith("main.py"))

    def test_advanced_fields_are_saved_and_clamped(self):
        from traductor import translate

        app = self.make_app("es")
        app.workers_var.set(99)
        self.assertEqual(app._workers(), translate.MAX_WORKERS)
        app.workers_var.set(3)
        app.notify_var.set(False)
        app._save_settings()
        saved = settings.load()
        self.assertEqual((saved["workers"], saved["notify"]), (3, False))
        self.assertNotIn("credit", saved)  # el crédito de la app no se configura
        app._take_snapshot()
        self.assertEqual(app._snap["workers"], 3)

    def test_notifies_only_for_long_jobs_and_never_when_cancelled(self):
        app = self.make_app("es")
        with mock.patch("tkinter.messagebox.showinfo") as info, \
                mock.patch("tkinter.messagebox.showwarning") as warn, \
                mock.patch("traductor.notify.alert") as alert:
            app._notify_finished("Traducir", True, None, 5)  # corto: sin aviso
            app._notify_finished("Traducir", False, None, 500)  # cancelado: sin aviso
            info.assert_not_called()
            app._notify_finished("Traducir", True, None, 120)
            info.assert_called_once()
            app._notify_finished("Traducir", False, "Se agotó la cuota diaria", 120)
            warn.assert_called_once()
            self.assertIn("cuota diaria", warn.call_args.args[1])
            self.assertEqual(alert.call_count, 2)
            app.notify_var.set(False)
            app._notify_finished("Traducir", True, None, 120)
            self.assertEqual(alert.call_count, 2)  # desactivado

    def test_retry_failed_validation_button_asks_before_retrying(self):
        app = self.make_app("es")
        self.assertIn("Reintentar las que fallaron la validación", button_texts(app))
        app._take_snapshot()
        with mock.patch.object(app, "_ensure_info"), \
                mock.patch("traductor.pipeline.failed_validation_originals", return_value=["a", "b"]), \
                mock.patch("traductor.pipeline.detect_pending"), \
                mock.patch("traductor.pipeline.retry_failed_validation") as retry:
            with mock.patch.object(app, "_ask", return_value=False):
                app._act_retry_failed()
            retry.assert_not_called()
            with mock.patch.object(app, "_ask", return_value=True):
                app._act_retry_failed()
            retry.assert_called_once()
        with mock.patch.object(app, "_ensure_info"), \
                mock.patch("traductor.pipeline.failed_validation_originals", return_value=[]), \
                mock.patch("traductor.pipeline.retry_failed_validation") as retry:
            app._act_retry_failed()  # nada que reintentar: ni pregunta ni reintenta
            retry.assert_not_called()

    def test_help_window_has_a_button_that_opens_the_tutorial(self):
        app = self.make_app("es")
        app.open_help()
        app.update()
        with mock.patch("os.startfile", create=True) as start, mock.patch("webbrowser.open") as wb:
            app.open_tutorial()
        self.assertEqual(start.call_count + wb.call_count, 1)
        with mock.patch("traductor.gui.tutorial_path", return_value=None), \
                mock.patch("tkinter.messagebox.showinfo") as info:
            app.open_tutorial()
        info.assert_called_once()

    def test_font_check_asks_before_writing_and_does_not_repeat(self):
        from types import SimpleNamespace

        from traductor import fonts
        from tests.test_fonts import truetype

        app = self.make_app("es")
        game = Path(self.tmp.name) / "game"
        game.mkdir()
        chars = fonts.needed_chars("Spanish")
        mapping = {ord(c): i + 1 for i, c in enumerate(chars)}
        sizes = [10] * (len(chars) + 1)
        sizes[mapping[ord("ñ")]] = 0  # ñ vacía, como Audrey-Bold.otf
        (game / "Deco.ttf").write_bytes(truetype(mapping, sizes))
        (game / "options.rpy").write_text('define gui.text_font = "Deco.ttf"\n', encoding="utf-8")
        app.info = SimpleNamespace(game_dir=game, root=game)
        app.ws = SimpleNamespace(scripts=Path(self.tmp.name) / "no-hay")
        app._snap = {"language": "Spanish"}
        fix = game / fonts.fix_filename("Spanish")

        with mock.patch.object(app, "_ask", return_value=False) as ask:
            app._check_fonts()
        ask.assert_called_once()
        self.assertFalse(fix.exists())  # sin permiso no se escribe nada

        with mock.patch.object(app, "_ask", return_value=True):
            app._check_fonts()
        text = fix.read_text(encoding="utf-8-sig")
        self.assertIn("translate Spanish python:", text)
        self.assertIn("Deco.ttf", text)

        with mock.patch.object(app, "_ask") as ask:
            app._check_fonts()  # ya hay reemplazo: no vuelve a preguntar
        ask.assert_not_called()

    def test_existing_language_name_is_used_with_its_exact_capitalization(self):
        from types import SimpleNamespace

        app = self.make_app("es")
        root = Path(self.tmp.name) / "juego"
        app.info = SimpleNamespace(root=root, name="Juego", tl_languages=["Arabic", "Spanish"])
        app._snap = {"game": str(root), "work": self.tmp.name, "language": "spanish"}
        with mock.patch("traductor.gui.find_game_root", return_value=root):
            app._ensure_info()
        self.assertEqual(app._snap["language"], "Spanish")  # el que ya usa la otra traducción
        app.update()  # procesa las tareas pendientes de la ventana
        app._pump()
        self.assertEqual(app.lang_var.get(), "Spanish")  # y se ve el nombre exacto en el campo
        app._snap["language"] = "swedish"  # un idioma que el juego no tiene se respeta tal cual
        with mock.patch("traductor.gui.find_game_root", return_value=root):
            app._ensure_info()
        self.assertEqual(app._snap["language"], "swedish")

    def test_clearing_the_game_folder_empties_the_panels(self):
        app = self.make_app("es")
        app._show_summary("Proyecto: otro juego")
        app.tree.insert("", "end", values=("a.rpy", 1, 1, 0))
        app.trans_tree.insert("", "end", values=("", "Hi", "Hola"))
        app.game_var.set("")
        app._refresh_guide()
        self.assertEqual(app.summary.get("1.0", "end").strip(), "")
        self.assertEqual(app.tree.get_children(), ())
        self.assertEqual(app.trans_tree.get_children(), ())
        self.assertIsNone(app.info)

    def test_start_over_options_clean_only_what_they_say(self):
        from types import SimpleNamespace

        from traductor import workflow

        app = self.make_app("es")
        base = Path(self.tmp.name) / "ws-juego"
        base.mkdir()
        (base / "traducciones.json").write_text("{}", encoding="utf-8")
        workflow.state_path(base).write_text('{"steps": {"analizar": {"done": true}}}', encoding="utf-8")
        app.ws = SimpleNamespace(base=base)
        app.game_var.set("C:/juego")
        with mock.patch.object(app, "_ensure_info_sync"), mock.patch.object(app, "_refresh_guide"):
            app._do_reset("lista")  # solo el progreso: la caché se conserva
            self.assertFalse(workflow.state_path(base).exists())
            self.assertTrue((base / "traducciones.json").exists())
            with mock.patch("tkinter.messagebox.askyesno", return_value=False):
                app._do_reset("todo")  # sin confirmar no se borra nada
            self.assertTrue(base.exists())
            app.ws = SimpleNamespace(base=base)
            with mock.patch("tkinter.messagebox.askyesno", return_value=True):
                app._do_reset("todo")
            self.assertFalse(base.exists())
        self.assertEqual(app.game_var.get(), "")

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
