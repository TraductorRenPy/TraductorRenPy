"""Genera assets/screenshot-<idioma>.png con el juego de ejemplo (solo para desarrollo).

Uso:  python tools/make_screenshots.py en|es
Requiere Pillow y el Ren'Py SDK instalado. Usa una carpeta de trabajo temporal y rutas neutras.
"""
import ctypes
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ui = sys.argv[1] if len(sys.argv) > 1 else "en"
if sys.platform == "win32":
    ctypes.windll.shcore.SetProcessDpiAwareness(2)

from PIL import ImageGrab  # noqa: E402

from traductor import pipeline, sdk, settings, workflow  # noqa: E402
from traductor.detect import analyze  # noqa: E402

# Carpeta neutra (sin el nombre de usuario de nadie en la captura).
neutral = Path(r"C:\Users\Public") if Path(r"C:\Users\Public").is_dir() else Path(tempfile.gettempdir())
base = neutral / "TraductorRenPy-demo"
shutil.rmtree(base, ignore_errors=True)
base.mkdir(parents=True)
game_root = base / "demo_game"
shutil.copytree(ROOT / "examples" / "demo_game", game_root)
settings.APP_DIR = base
settings.SETTINGS_FILE = base / "settings.json"

sdk_dir = sdk.autodetect()[0]
cfg = settings.load()
cfg.update(
    game_dir=str(game_root), sdk_path=str(sdk_dir), ui_language=ui, language="spanish",
    engine="gemini", workspace_dir=str(base / "trabajo"),
)
settings.save(cfg)

# estado intermedio realista: analizado, tl generado y textos sin marcar añadidos
info = analyze(game_root)
ws = pipeline.make_workspace(cfg["workspace_dir"], info)
pipeline.generate_tl(info, ws, str(sdk_dir), "spanish")
pipeline.add_extra_strings(info, ws, "spanish")
report = pipeline.detect_pending(info, ws, "spanish")
for step in ("analizar", "generar", "extras"):
    workflow.mark(ws.base, step)

from traductor import i18n  # noqa: E402
from traductor.gui import App  # noqa: E402

app = App()
app.geometry("1100x960+40+10")
app.update()
for _ in range(8):  # deja que se dibuje la guía y se detecte el juego
    app.update()
    time.sleep(0.15)
app._show_report(report)
for msg in (
    "=== Review the game ===" if ui == "en" else "=== Revisar el juego ===",
    "Proyecto: " + str(game_root),
    ".rpy sueltos: 2",
    "Idiomas en tl/: spanish",
    "Resultado: todos los scripts están como .rpy; se puede generar tl directo.",
    "tl/spanish: 0 -> 338 entradas (+338).",
    "Textos sin marcar en los scripts: 5 (5 seguros, 0 probables).",
):
    app.log(msg)
app.sdk_var.set(r"C:\renpy-8.5.3-sdk")  # solo para mostrar: no se usa en esta captura
for _ in range(10):
    app.update()
    time.sleep(0.1)
app.attributes("-topmost", True)
app.lift()
app.update()
time.sleep(0.8)
x, y, w, h = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()
out = ROOT / "assets" / f"screenshot-{ui}.png"
out.parent.mkdir(exist_ok=True)
ImageGrab.grab((x, y, x + w, y + h)).save(out, optimize=True)
app.destroy()
shutil.rmtree(base, ignore_errors=True)
print("captura:", out)
