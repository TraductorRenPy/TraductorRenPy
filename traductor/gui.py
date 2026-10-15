"""Ventana principal (tkinter): guía paso a paso y modo automático."""

import queue
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable, Optional

from . import __version__, about, i18n, languages, pipeline, report, sdk, settings, uitweaks, workflow
from .common import Cancelled
from .detect import GameInfo, analyze, find_game_root
from .engines import ENGINES
from .glossary import Glossary, find_characters, suggest_terms
from .i18n import tr
from .pending import TlReport
from .translate import Cache, apply_cache

HELP_ES = """\
CÓMO TRADUCIR UN JUEGO

1. Elige la carpeta del juego
   La que contiene la carpeta «game» (puede estar dentro de otras carpetas).

2. Elige el idioma de la traducción, tu motor y pega tu clave
   Gemini (Google) tiene nivel gratuito. El botón «Conseguir clave…» abre la
   página donde se crea. Cada persona usa su propia clave, que se guarda cifrada
   solo en este equipo.

3. Pulsa «▶ Traducir este juego automáticamente»
   La app hace todos los pasos y solo te pregunta lo necesario:
   • si tienes una versión anterior ya traducida (para aprovecharla),
   • si quieres gastar tu API en lo que falta (te dice cuántos textos son),
   • si quieres instalar la traducción en el juego.

4. Abre el juego
   Debe iniciar en el idioma elegido. Si algo no te gusta, se puede deshacer
   (ver abajo).

LA LISTA «QUÉ HACER AHORA»
Muestra cada paso con ✓ (hecho), ▶ (el que sigue) o · (pendiente). El botón
«Hacer el siguiente paso» ejecuta justo el que toca. Puedes parar y seguir otro
día: la app recuerda dónde ibas.

QUÉ TOCA LA APP EN TU JUEGO
• Escribe la traducción en game/tl/<idioma>/ y crea game/zz_<idioma>.rpy.
• Antes de escribir, guarda un respaldo en la carpeta de trabajo (subcarpeta
  «respaldos»). Para deshacer, copia ese respaldo de vuelta sobre game/tl/<idioma>.
• Los scripts del juego no se modifican.

REN'PY SDK
Hace falta el Ren'Py SDK (gratis, renpy.org). La app intenta encontrarlo sola;
si no, usa el botón «Buscar SDK».

TEXTO DENTRO DE IMÁGENES
Las letras dibujadas dentro de una imagen (carteles, fondos con texto) no se
pueden traducir con esta app; solo el texto que el juego escribe como texto.

USO RESPONSABLE
Traduce solo juegos que tengas derecho a traducir y no compartas los scripts
extraídos ni las traducciones de juegos ajenos sin permiso de sus autores.

PASO A PASO (MANUAL)
Debajo hay un botón por cada paso, por si quieres repetir uno o hacerlo a mano.
«Usar una traducción anterior» sirve también con parches de traducción de otras
personas: elige su carpeta y la app toma lo ya traducido y traduce solo lo que falte.
"""

HELP_EN = """\
HOW TO TRANSLATE A GAME

1. Choose the game folder
   The one that contains the "game" folder (it can be inside other folders).

2. Choose the translation language and your engine, and paste your key
   Gemini (Google) has a free tier. The "Get key…" button opens the page where
   it is created. Everyone uses their own key, which is stored encrypted only
   on this computer.

3. Press "▶ Translate this game automatically"
   The app runs every step and only asks what it needs:
   • whether you have an earlier translated version (to reuse it),
   • whether you want to spend your API quota on what is missing (it tells you
     how many texts that is),
   • whether you want to install the translation into the game.

4. Open the game
   It should start in the chosen language. If you don't like something it can be
   undone (see below).

THE "WHAT TO DO NOW" LIST
It shows each step as ✓ (done), ▶ (next) or · (pending). The "Do the next step"
button runs exactly the one that is due. You can stop and continue another day:
the app remembers where you were.

WHAT THE APP TOUCHES IN YOUR GAME
• It writes the translation into game/tl/<language>/ and creates game/zz_<language>.rpy.
• Before writing, it saves a backup in the work folder ("respaldos" subfolder).
  To undo, copy that backup back over game/tl/<language>.
• The game's scripts are never modified.

REN'PY SDK
The Ren'Py SDK (free, renpy.org) is required. The app tries to find it by
itself; if it can't, use the "Find SDK" button.

TEXT INSIDE IMAGES
Letters drawn inside an image (signs, backgrounds with text) cannot be
translated with this app; only text the game writes as text.

RESPONSIBLE USE
Only translate games you have the right to translate, and do not share extracted
scripts or translations of other people's games without their authors' permission.

STEP BY STEP (MANUAL)
Below there is one button per step, in case you want to repeat one or do it by
hand. "Use an earlier translation" also works with translation patches made by
other people: pick their folder and the app takes what is already translated and
translates only what is missing.
"""

_ICONS = {"hecho": "✓", "omitido": "–", "siguiente": "▶", "pendiente": "·"}
UI_CHOICES = [("auto", "Automático / Auto"), ("es", "Español"), ("en", "English")]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        cfg = settings.load()
        self.ui_setting = cfg.get("ui_language", "auto")
        i18n.set_language(i18n.resolve(self.ui_setting))
        self.title(f"TraductorRenPy {__version__}")
        self.geometry("1100x940")
        self.minsize(960, 700)

        self.game_var = tk.StringVar(value=cfg["game_dir"])
        self.sdk_var = tk.StringVar(value=cfg["sdk_path"])
        self.unrpyc_var = tk.StringVar(value=cfg["unrpyc_path"])
        self.work_var = tk.StringVar(value=cfg["workspace_dir"])
        self.lang_var = tk.StringVar(value=languages.label_for(cfg["language"]))
        self.ui_var = tk.StringVar(value=dict(UI_CHOICES).get(self.ui_setting, "Automático / Auto"))
        self.engines_cfg = cfg["engines"]
        self.engine_var = tk.StringVar(value=ENGINES[cfg["engine"]].label if cfg["engine"] in ENGINES else "")
        self.key_var = tk.StringVar()
        self.opt_var = tk.StringVar()  # modelo (Grok/Gemini) o región (Microsoft)
        self.url_var = tk.StringVar()
        self.batch_var = tk.IntVar(value=cfg["batch_size"])
        self._shown_engine: Optional[str] = None

        self.info: Optional[GameInfo] = None
        self.ws: Optional[pipeline.Workspace] = None
        self.report: Optional[TlReport] = None
        self.events: "queue.Queue" = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self._eta_start: Optional[float] = None
        self._refresh_job = None
        self._validated = None  # resultado del último "Revisar" (para confirmar la instalación)

        self._after_ids = []
        self._snap = {}  # copia de los ajustes para los hilos de trabajo (ver _take_snapshot)
        self._build()
        self.game_var.trace_add("write", lambda *a: self._schedule_refresh())
        self._after(100, self._pump)
        self._after(300, self._refresh_guide)
        if not sdk.find_renpy_exe(self.sdk_var.get().strip()):
            self._after(600, lambda: self.detect_sdk(silent=True))

    def _after(self, ms, fn):
        """Como `after`, pero recuerda la tarea para cancelarla al cerrar la ventana."""
        job = self.after(ms, fn)
        self._after_ids.append(job)
        return job

    def destroy(self):
        for job in self._after_ids:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._after_ids.clear()
        super().destroy()

    # --- construcción de la interfaz -----------------------------------

    def _build(self):
        pad = {"padx": 6, "pady": 3}
        cfg = ttk.LabelFrame(self, text=tr("Configuración"))
        cfg.pack(fill="x", padx=8, pady=(8, 4))
        cfg.columnconfigure(1, weight=1)
        rows = [
            (tr("Carpeta del juego"), self.game_var, self._browse_game),
            (tr("Ren'Py SDK (carpeta o renpy.exe)"), self.sdk_var, self._browse_sdk),
            (tr("unrpyc.py (opcional: ya viene incluido)"), self.unrpyc_var, self._browse_unrpyc),
            (tr("Carpeta de trabajo"), self.work_var, self._browse_work),
        ]
        for r, (label, var, cmd) in enumerate(rows):
            ttk.Label(cfg, text=label).grid(row=r, column=0, sticky="w", **pad)
            ttk.Entry(cfg, textvariable=var).grid(row=r, column=1, sticky="ew", **pad)
            ttk.Button(cfg, text=tr("Examinar…"), command=cmd).grid(row=r, column=2, **pad)
        ttk.Button(cfg, text=tr("Buscar SDK"), command=self.detect_sdk).grid(row=1, column=3, **pad)
        last = len(rows)
        ttk.Label(cfg, text=tr("Idioma de la traducción")).grid(row=last, column=0, sticky="w", **pad)
        lang_row = ttk.Frame(cfg)
        lang_row.grid(row=last, column=1, sticky="w", **pad)
        self.lang_box = ttk.Combobox(lang_row, textvariable=self.lang_var, width=32, values=languages.labels())
        self.lang_box.pack(side="left")
        ttk.Label(lang_row, text="   " + tr("Idioma de la interfaz")).pack(side="left")
        self.ui_box = ttk.Combobox(
            lang_row, textvariable=self.ui_var, state="readonly", width=18, values=[l for _, l in UI_CHOICES]
        )
        self.ui_box.pack(side="left", padx=(6, 0))
        self.ui_box.bind("<<ComboboxSelected>>", lambda e: self._ui_language_changed())

        eng = ttk.LabelFrame(
            self, text=tr("Motor de traducción (uno por trabajo; cada persona usa su propia clave, guardada cifrada en este equipo)")
        )
        eng.pack(fill="x", padx=8, pady=4)
        eng.columnconfigure(3, weight=1)
        ttk.Label(eng, text=tr("Motor")).grid(row=0, column=0, sticky="w", **pad)
        self.engine_box = ttk.Combobox(
            eng, textvariable=self.engine_var, state="readonly", width=22,
            values=[e.label for e in ENGINES.values()],
        )
        self.engine_box.grid(row=0, column=1, **pad)
        self.engine_box.bind("<<ComboboxSelected>>", lambda e: self._load_engine_fields())
        ttk.Label(eng, text=tr("Clave API")).grid(row=0, column=2, sticky="e", **pad)
        ttk.Entry(eng, textvariable=self.key_var, show="•").grid(row=0, column=3, sticky="ew", **pad)
        ttk.Button(eng, text=tr("Conseguir clave…"), command=self.get_key_help).grid(row=1, column=4, columnspan=2, **pad)
        self.opt_label = ttk.Label(eng, text=tr("Modelo"))
        self.opt_label.grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(eng, textvariable=self.opt_var, width=26).grid(row=1, column=1, **pad)
        ttk.Label(eng, text=tr("URL base")).grid(row=1, column=2, sticky="e", **pad)
        ttk.Entry(eng, textvariable=self.url_var).grid(row=1, column=3, sticky="ew", **pad)
        ttk.Label(eng, text=tr("Líneas por lote")).grid(row=0, column=4, sticky="e", **pad)
        ttk.Spinbox(eng, from_=1, to=100, textvariable=self.batch_var, width=5).grid(row=0, column=5, **pad)
        self._load_engine_fields()

        self.step_buttons = []

        # --- guía: qué hacer ahora ---
        guide = ttk.LabelFrame(self, text=tr("Qué hacer ahora"))
        guide.pack(fill="x", padx=8, pady=4)
        top = ttk.Frame(guide)
        top.pack(fill="x", padx=6, pady=(6, 2))
        style = ttk.Style(self)
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=(14, 6))
        self.auto_btn = ttk.Button(
            top, text=tr("▶  Traducir este juego automáticamente"), style="Big.TButton", command=self.run_auto
        )
        self.auto_btn.pack(side="left")
        self.step_buttons.append(self.auto_btn)
        self.next_btn = ttk.Button(top, text=tr("Hacer el siguiente paso"), command=self.step_next)
        self.next_btn.pack(side="left", padx=10)
        self.step_buttons.append(self.next_btn)
        ttk.Button(top, text=tr("Ayuda"), command=self.open_help).pack(side="left")
        ttk.Button(top, text=tr("Acerca de"), command=self.open_about).pack(side="left", padx=(6, 0))
        if about.REPO_URL:
            ttk.Button(top, text=tr("Reportar un problema"), command=self.open_report).pack(side="left", padx=(6, 0))
        if about.FEEDBACK_URL:
            ttk.Button(top, text=tr("Dar opinión"), command=self.open_feedback).pack(side="left", padx=(6, 0))
        self.cancel_btn = ttk.Button(top, text=tr("Cancelar"), command=self.cancel.set, state="disabled")
        self.cancel_btn.pack(side="right")
        if about.DONATE_URL:
            ttk.Button(top, text=tr("♥ Apoyar el proyecto"), command=self.open_donate).pack(side="right", padx=8)
        self.guide_text = tk.Text(guide, height=11, wrap="word", state="disabled", relief="flat",
                                  background=self.cget("background"), font=("Segoe UI", 10))
        self.guide_text.pack(fill="x", padx=8, pady=(2, 6))
        self.guide_text.tag_configure("hecho", foreground="#2e7d32")
        self.guide_text.tag_configure("omitido", foreground="#888888")
        self.guide_text.tag_configure("pendiente", foreground="#666666")
        self.guide_text.tag_configure("siguiente", foreground="#0b57d0", font=("Segoe UI", 10, "bold"))
        self.guide_text.tag_configure("what", foreground="#0b57d0", lmargin1=24, lmargin2=24)

        # --- botones manuales (un botón por paso) ---
        manual = ttk.LabelFrame(self, text=tr("Paso a paso (manual)"))
        manual.pack(fill="x", padx=8, pady=4)
        actions = {
            "analizar": self.step_analyze,
            "extraer": self.step_collect,
            "decompilar": self.step_decompile,
            "generar": self.step_generate,
            "extras": self.step_extras,
            "importar": self.step_import,
            "glosario": self.open_glossary,
            "traducir": self.step_translate,
            "validar": self.step_validate,
            "instalar": self.step_install,
        }
        row_a = ttk.Frame(manual)
        row_a.pack(fill="x", padx=6, pady=(4, 0))
        row_b = ttk.Frame(manual)
        row_b.pack(fill="x", padx=6, pady=(2, 4))
        for i, step in enumerate(workflow.STEPS, 1):
            b = ttk.Button(row_a if i <= 5 else row_b, text=f"{i}. {tr(step.title)}", command=actions[step.id])
            b.pack(side="left", padx=(0, 6))
            self.step_buttons.append(b)
        for text, cmd in [(tr("Ver pendientes"), self.step_pending), (tr("Caja de diálogo…"), self.open_ui_tweaks)]:
            b = ttk.Button(row_b, text=text, command=cmd)
            b.pack(side="right", padx=(6, 0))
            self.step_buttons.append(b)

        prog = ttk.Frame(self)
        prog.pack(fill="x", padx=8, pady=2)
        self.progress = ttk.Progressbar(prog, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.eta_var = tk.StringVar()
        ttk.Label(prog, textvariable=self.eta_var, width=46, anchor="e").pack(side="right", padx=(8, 0))

        mid = ttk.PanedWindow(self, orient="horizontal")
        mid.pack(fill="both", expand=True, padx=8, pady=4)

        left = ttk.LabelFrame(mid, text=tr("Juego detectado"))
        self.summary = tk.Text(left, width=48, height=8, wrap="word", state="disabled")
        self.summary.pack(fill="both", expand=True, padx=4, pady=4)
        mid.add(left, weight=1)

        right = ttk.Notebook(mid)
        pend_tab = ttk.Frame(right)
        right.add(pend_tab, text=tr("Pendientes por archivo (tl)"))
        trans_tab = ttk.Frame(right)
        right.add(trans_tab, text=tr("Traducciones"))
        self.trans_tree = ttk.Treeview(trans_tab, columns=("who", "en", "es"), show="headings", height=6)
        for c, w, t in [("who", 60, tr("Habla")), ("en", 260, tr("Original")), ("es", 260, tr("Traducción"))]:
            self.trans_tree.heading(c, text=t)
            self.trans_tree.column(c, width=w, anchor="w")
        self.trans_tree.pack(fill="both", expand=True, padx=4, pady=4)
        cols = ("archivo", "entradas", "pendientes", "sin_texto")
        self.tree = ttk.Treeview(pend_tab, columns=cols, show="headings", height=6)
        for c, w, t in [
            ("archivo", 200, tr("Archivo")),
            ("entradas", 70, tr("Entradas")),
            ("pendientes", 80, tr("Pendientes")),
            ("sin_texto", 110, tr("Sin texto / ya traducido")),
        ]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w" if c == "archivo" else "e")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        mid.add(right, weight=2)

        self.log_box = scrolledtext.ScrolledText(self, height=9, state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    # --- guía -----------------------------------------------------------

    def _schedule_refresh(self):
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self._after(700, self._refresh_guide)

    def _refresh_guide(self):
        """Redibuja la lista de pasos según lo que ya se hizo con este juego."""
        self._refresh_job = None
        text = self.guide_text
        text.configure(state="normal")
        text.delete("1.0", "end")
        try:
            self._ensure_info_sync()
        except Exception as exc:
            msg = (
                tr("Elige la carpeta del juego para empezar.")
                if not self.game_var.get().strip()
                else i18n.tr_log(str(exc))
            )
            text.insert("end", msg)
            text.configure(state="disabled")
            self.next_btn.configure(text=tr("Hacer el siguiente paso"))
            return
        steps = workflow.load_state(self.ws.base)
        current = workflow.next_step(self.info, steps)
        for row in workflow.checklist(self.info, steps):
            title = tr(row["title"]) + (" " + tr("(opcional)") if row["optional"] else "")
            text.insert("end", f"{_ICONS[row['status']]}  {title}\n", row["status"])
            if row["status"] == "siguiente":
                text.insert("end", f"{tr(row['what'])}\n", "what")
        if current is None:
            text.insert("end", "\n" + tr("Todo listo: abre el juego, debe iniciar en el idioma elegido."), "hecho")
        text.configure(state="disabled")
        if current is None:
            self.next_btn.configure(text=tr("Todo listo"))
        else:
            self.next_btn.configure(
                text=tr("Hacer el siguiente paso: {title}", title=tr(workflow.STEP_BY_ID[current].title))
            )

    def _mark(self, step_id: str, skipped: bool = False):
        if self.ws is not None:
            workflow.mark(self.ws.base, step_id, skipped)
        self.events.put(("call", self._refresh_guide))

    def open_help(self):
        win = tk.Toplevel(self)
        win.title(tr("Ayuda"))
        win.geometry("660x640")
        box = scrolledtext.ScrolledText(win, wrap="word", font=("Segoe UI", 10))
        box.pack(fill="both", expand=True, padx=8, pady=8)
        box.insert("1.0", HELP_EN if i18n.current() == "en" else HELP_ES)
        box.configure(state="disabled")

    def open_about(self):
        win = tk.Toplevel(self)
        win.title(tr("Acerca de"))
        win.resizable(False, False)
        ttk.Label(win, text=f"{about.APP_NAME} {about.VERSION}", font=("Segoe UI", 14, "bold")).pack(
            padx=24, pady=(16, 2)
        )
        ttk.Label(
            win,
            text=tr("Traduce juegos hechos con Ren'Py a otros idiomas.") + "\n"
                 + tr("Licencia {name}. Software libre.", name=about.LICENSE_NAME),
            justify="center",
        ).pack(padx=24, pady=4)
        ttk.Label(win, text=tr("unrpyc (MIT) viene incluido. Ren'Py es de sus autores."), foreground="#666666").pack(
            padx=24, pady=2
        )
        row = ttk.Frame(win)
        row.pack(pady=(10, 4))
        if about.REPO_URL:
            ttk.Button(row, text=tr("Página del proyecto"), command=lambda: webbrowser.open(about.REPO_URL)).pack(
                side="left", padx=4
            )
        if about.REPO_URL:
            ttk.Button(row, text=tr("Reportar un problema"), command=self.open_report).pack(side="left", padx=4)
        if about.FEEDBACK_URL:
            ttk.Button(row, text=tr("Dar opinión"), command=self.open_feedback).pack(side="left", padx=4)
        if about.DONATE_URL:
            ttk.Button(row, text=tr("♥ Apoyar el proyecto"), command=self.open_donate).pack(side="left", padx=4)
        ttk.Button(win, text=tr("Cerrar"), command=win.destroy).pack(pady=(4, 16))

    def open_donate(self):
        if about.DONATE_URL:
            webbrowser.open(about.DONATE_URL)

    def open_feedback(self):
        if about.FEEDBACK_URL:
            webbrowser.open(about.FEEDBACK_URL)

    def open_report(self):
        """Muestra el diagnóstico (sin datos privados) y abre un issue de GitHub ya rellenado."""
        if not about.REPO_URL:
            return
        paths = [self.game_var.get(), self.sdk_var.get(), self.unrpyc_var.get(), self.work_var.get(),
                 str(settings.APP_DIR)]
        text = self.log_box.get("1.0", "end").splitlines()
        diag = report.build_diagnostics(
            text, self.engine_var.get(), self._language(), i18n.current(), paths
        )
        win = tk.Toplevel(self)
        win.title(tr("Reportar un problema"))
        win.geometry("640x520")
        ttk.Label(win, text=tr("Describe qué pasó (opcional):")).pack(anchor="w", padx=10, pady=(10, 2))
        desc = tk.Text(win, height=4, wrap="word")
        desc.pack(fill="x", padx=10)
        ttk.Label(
            win,
            text=tr("Esto se publicará tal cual en GitHub. Se quitaron rutas, correos y claves; "
                    "revísalo antes de enviar:"),
            wraplength=600, foreground="#666666",
        ).pack(anchor="w", padx=10, pady=(8, 2))
        box = scrolledtext.ScrolledText(win, wrap="word", font=("Consolas", 9))
        box.pack(fill="both", expand=True, padx=10, pady=2)
        box.insert("1.0", diag)

        def full_body() -> str:
            what = desc.get("1.0", "end").strip()
            return (what + "\n\n" if what else "") + "```\n" + box.get("1.0", "end").strip() + "\n```\n"

        def send():
            webbrowser.open(report.issue_url(about.REPO_URL, "Problem report", full_body()))

        def copy():
            self.clipboard_clear()
            self.clipboard_append(full_body())

        row = ttk.Frame(win)
        row.pack(pady=8)
        ttk.Button(row, text=tr("Abrir en GitHub"), command=send).pack(side="left", padx=4)
        ttk.Button(row, text=tr("Copiar"), command=copy).pack(side="left", padx=4)
        ttk.Button(row, text=tr("Cerrar"), command=win.destroy).pack(side="left", padx=4)

    # --- diálogos de ruta ----------------------------------------------

    def _browse_game(self):
        d = filedialog.askdirectory(title=tr("Carpeta del juego"), initialdir=self.game_var.get() or None)
        if d:
            self.game_var.set(d)
            self.info = None

    def _browse_sdk(self):
        d = filedialog.askdirectory(title=tr("Carpeta del Ren'Py SDK"), initialdir=self.sdk_var.get() or None)
        if d:
            self.sdk_var.set(d)

    def _browse_unrpyc(self):
        f = filedialog.askopenfilename(title="unrpyc.py", filetypes=[("Python", "*.py"), (tr("Todos"), "*.*")])
        if f:
            self.unrpyc_var.set(f)

    def _browse_work(self):
        d = filedialog.askdirectory(title=tr("Carpeta de trabajo"), initialdir=self.work_var.get() or None)
        if d:
            self.work_var.set(d)

    def detect_sdk(self, silent: bool = False):
        """Busca el Ren'Py SDK en el equipo; si no está, ofrece abrir la descarga."""
        found = sdk.autodetect()
        if found:
            self.sdk_var.set(str(found[0]))
            self.log(tr("Ren'Py SDK encontrado: {path}", path=found[0]))
        elif not silent:
            if messagebox.askyesno(
                tr("Ren'Py SDK"),
                tr("No encontré el Ren'Py SDK en este equipo.\n\nEs gratis y se descarga de renpy.org. "
                   "¿Abrir la página de descarga?"),
            ):
                webbrowser.open(sdk.SDK_DOWNLOAD_URL)

    def _ui_language_changed(self):
        code = next((c for c, label in UI_CHOICES if label == self.ui_var.get()), "auto")
        self.ui_setting = code
        self._save_settings()
        messagebox.showinfo(
            "TraductorRenPy",
            "Reinicia la aplicación para aplicar el idioma.\nRestart the application to apply the language.",
        )

    # --- ejecución en segundo plano --------------------------------------

    def log(self, msg: str):
        self.events.put(("log", i18n.tr_log(msg)))

    def _set_progress(self, done: int, total: int):
        self.events.put(("progress", done, total))

    def _pump(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if ev[0] == "log":
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", ev[1] + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                elif ev[0] == "progress":
                    self.progress.configure(maximum=max(ev[2], 1), value=ev[1])
                    self._update_eta(ev[1], ev[2])
                elif ev[0] == "call":
                    ev[1]()
        except queue.Empty:
            pass
        if self._after_ids:
            self._after_ids = self._after_ids[-20:]  # no crecer sin límite
        self._after(100, self._pump)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        seconds = int(seconds)
        h, rest = divmod(seconds, 3600)
        m, s = divmod(rest, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def _update_eta(self, done: int, total: int):
        """Tiempo transcurrido y restante estimado según el ritmo hasta ahora."""
        now = time.monotonic()
        if self._eta_start is None or done == 0:
            self._eta_start = now
        elapsed = now - self._eta_start
        if total and done >= total:
            self.eta_var.set(tr("Completado: {done}/{total} en {time}", done=done, total=total, time=self._fmt_time(elapsed)))
        elif done > 0:
            remaining = elapsed / done * (total - done)
            self.eta_var.set(
                tr("{done}/{total} · transcurrido {elapsed} · restante ~{remaining}",
                   done=done, total=total, elapsed=self._fmt_time(elapsed), remaining=self._fmt_time(remaining))
            )
        else:
            self.eta_var.set(tr("0/{total} · calculando…", total=total))

    def _set_busy(self, busy: bool):
        self.busy = busy
        for b in self.step_buttons:
            b.configure(state="disabled" if busy else "normal")
        self.cancel_btn.configure(state="normal" if busy else "disabled")
        if not busy:
            self.progress.configure(value=0)

    def _take_snapshot(self):
        """Copia de los ajustes de la ventana, tomada en el hilo principal: las tareas
        corren en otro hilo y no deben leer variables de Tk directamente."""
        self._snap = {
            "game": self.game_var.get().strip(),
            "work": self.work_var.get().strip(),
            "sdk": self.sdk_var.get().strip(),
            "unrpyc": self.unrpyc_var.get().strip(),
            "language": self._language(),
            "engine": self._engine_name(),
            "batch": self._batch_size(),
            "has_key": self._has_key(),
        }

    def _run(self, title: str, work: Callable[[], None], on_done: Optional[Callable[[], None]] = None):
        if self.busy:
            return
        self._save_settings()
        self._take_snapshot()
        self.cancel.clear()
        self._eta_start = None
        self.eta_var.set("")
        self._set_busy(True)
        self.log(f"=== {tr(title)} ===")

        def target():
            ok = False
            try:
                work()
                ok = True
            except Cancelled:
                self.log(tr("Cancelado por el usuario."))
            except Exception as exc:  # se muestra en el registro, no se pierde
                self.log(f"ERROR: {exc}")
                self.log(traceback.format_exc(limit=4))
            finally:
                def finish():
                    self._set_busy(False)
                    self._refresh_guide()
                    if ok and on_done:
                        on_done()

                self.events.put(("call", finish))

        threading.Thread(target=target, daemon=True).start()

    def _ask(self, fn: Callable):
        """Ejecuta `fn` (un diálogo) en el hilo de la interfaz y espera su resultado."""
        box, done = {}, threading.Event()

        def call():
            try:
                box["v"] = fn()
            finally:
                done.set()

        self.events.put(("call", call))
        done.wait()
        return box.get("v")

    def _engine_name(self) -> str:
        label = self.engine_var.get()
        return next((n for n, e in ENGINES.items() if e.label == label), "grok")

    def _load_engine_fields(self):
        """Muestra los campos del motor elegido (guardando antes los del anterior)."""
        self._store_engine_fields()
        name = self._engine_name()
        cls = ENGINES[name]
        cfg = {**cls.defaults, **self.engines_cfg.get(name, {})}
        self.key_var.set(cfg.get("api_key", ""))
        is_ms = "region" in cls.fields
        self.opt_label.configure(text=tr("Región") if is_ms else tr("Modelo"))
        self.opt_var.set(cfg.get("region", "") if is_ms else cfg.get("model", ""))
        self.url_var.set(cfg.get("base_url", ""))
        self._shown_engine = name

    def _store_engine_fields(self):
        name = self._shown_engine
        if name is None:
            return
        opt = "region" if "region" in ENGINES[name].fields else "model"
        self.engines_cfg[name] = {
            "api_key": self.key_var.get().strip(),
            opt: self.opt_var.get().strip(),
            "base_url": self.url_var.get().strip(),
        }

    def _save_settings(self):
        self._store_engine_fields()
        settings.save({
            "game_dir": self.game_var.get().strip(),
            "sdk_path": self.sdk_var.get().strip(),
            "unrpyc_path": self.unrpyc_var.get().strip(),
            "workspace_dir": self.work_var.get().strip(),
            "language": self._language(),
            "ui_language": self.ui_setting,
            "engine": self._engine_name(),
            "batch_size": self._batch_size(),
            "engines": self.engines_cfg,
        })

    def get_key_help(self):
        """Abre la página donde crear la clave y explica los pasos en el registro."""
        cls = ENGINES[self._engine_name()]
        self.log(tr("=== Cómo conseguir la clave de {name} ===", name=cls.label))
        self.log(tr(cls.key_help))
        self.log(tr("Pega la clave en «Clave API». Nunca la compartas ni la subas a git."))
        webbrowser.open(cls.key_url)

    def _batch_size(self) -> int:
        try:
            return max(1, int(self.batch_var.get()))
        except (tk.TclError, ValueError):
            return 20

    def _language(self) -> str:
        return languages.code_from_label(self.lang_var.get().strip())

    def _language_label(self) -> str:
        return languages.label_for(self._language())

    def _has_key(self) -> bool:
        self._store_engine_fields()
        return bool(self.engines_cfg.get(self._engine_name(), {}).get("api_key"))

    # --- acciones (se ejecutan en el hilo de trabajo) ----------------------

    def _do_analyze(self):
        path = self._snap["game"]
        if not path:
            raise ValueError("Elige la carpeta del juego.")
        info = analyze(path)
        self.info = info
        self.ws = pipeline.make_workspace(self._snap["work"], info)
        for line in info.summary().splitlines():
            self.log(line)
        self.events.put(("call", lambda: self._show_summary(i18n.tr_log_block(info.summary()))))

    def _ensure_info(self):
        if self.info is None or find_game_root(self._snap["game"]) != self.info.root:
            self._do_analyze()
        else:
            self.ws = pipeline.make_workspace(self._snap["work"], self.info)

    def _ensure_info_sync(self):
        """Como _ensure_info pero en el hilo de la interfaz (el análisis es rápido)."""
        path = self.game_var.get().strip()
        if not path:
            raise ValueError("Elige la carpeta del juego.")
        if self.info is None or find_game_root(path) != self.info.root:
            self.info = analyze(path)
            self.events.put(("call", lambda: self._show_summary(i18n.tr_log_block(self.info.summary()))))
        self.ws = pipeline.make_workspace(self.work_var.get().strip(), self.info)

    def _show_summary(self, text: str):
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    def _show_report(self, report: TlReport):
        self.tree.delete(*self.tree.get_children())
        for name, s in sorted(report.by_file().items()):
            self.tree.insert("", "end", values=(name, s["total"], s["pending"], s["trivial"]))
        self.tree.insert(
            "", 0,
            values=("TOTAL", len(report.entries), report.count("pending"), report.count("trivial")),
        )

    def _show_translations(self, report: TlReport, cache: Cache):
        self.trans_tree.delete(*self.trans_tree.get_children())
        for entry, dst in apply_cache(report, cache):
            self.trans_tree.insert("", "end", values=(entry.who or "", entry.original, dst))

    def _act_analyze(self):
        self._do_analyze()
        self._mark("analizar")

    def _act_collect(self):
        self._ensure_info()
        pipeline.collect_scripts(self.info, self.ws, self.log, self._set_progress, self.cancel)
        self._mark("extraer")

    def _act_decompile(self):
        self._ensure_info()
        failed = pipeline.decompile_scripts(
            self.info, self.ws, self._snap["unrpyc"], self.log, self.cancel
        )
        if failed:
            raise RuntimeError(f"{len(failed)} archivos no se pudieron decompilar.")
        self._mark("decompilar")

    def _act_generate(self):
        self._ensure_info()
        if sdk.find_renpy_exe(self._snap["sdk"]) is None:
            raise FileNotFoundError(
                "Falta la carpeta del Ren'Py SDK. Pulsa «Buscar SDK» o indícala arriba "
                "(la carpeta donde está renpy.exe)."
            )
        pipeline.generate_tl(
            self.info, self.ws, self._snap["sdk"], self._snap["language"], self.log, self.cancel
        )
        self._mark("generar")

    def _act_extras(self):
        self._ensure_info()
        pipeline.add_extra_strings(self.info, self.ws, self._snap["language"], self.log)
        report = pipeline.detect_pending(self.info, self.ws, self._snap["language"], self.log)
        self.events.put(("call", lambda: self._show_report(report)))
        self._mark("extras")

    def _act_import(self, ref_path: str):
        self._ensure_info()
        report, cache, _ = pipeline.import_previous(
            self.info, self.ws, self._snap["language"], ref_path,
            self._snap["unrpyc"], self.log, self.cancel,
        )
        self.events.put(("call", lambda: self._show_report(report)))
        self.events.put(("call", lambda: self._show_translations(report, cache)))
        self._mark("importar")

    def _act_translate(self):
        self._ensure_info()
        report, cache, _ = pipeline.translate_pending(
            self.info, self.ws, self._snap["language"], self._snap["engine"],
            self.engines_cfg, self._snap["batch"], self.log, self._set_progress, self.cancel,
        )
        self.events.put(("call", lambda: self._show_report(report)))
        self.events.put(("call", lambda: self._show_translations(report, cache)))
        self._mark("glosario")
        self._mark("traducir")

    def _act_validate(self):
        self._ensure_info()
        self._validated = pipeline.validate_translations(self.info, self.ws, self._snap["language"], self.log)
        self._mark("validar")

    def _act_install(self):
        self._ensure_info()
        pipeline.install_translations(self.info, self.ws, self._snap["language"], self.log)
        report = pipeline.detect_pending(self.info, self.ws, self._snap["language"], self.log)
        self.events.put(("call", lambda: self._show_report(report)))
        self._mark("instalar")
        self.log(tr("Listo. Abre el juego: debe iniciar en {lang}.", lang=languages.label_for(self._snap["language"])))

    # --- un paso con las preguntas de la guía (también lo usa el modo automático) ---

    def _do_step(self, step_id: str) -> bool:
        """Ejecuta un paso. Devuelve False si el usuario decide parar."""
        if step_id == "analizar":
            self._act_analyze()
        elif step_id == "extraer":
            self._act_collect()
        elif step_id == "decompilar":
            self._act_decompile()
        elif step_id == "generar":
            self._act_generate()
        elif step_id == "extras":
            self._act_extras()
        elif step_id == "importar":
            return self._step_import_with_questions()
        elif step_id == "traducir":
            return self._step_translate_with_confirmation()
        elif step_id == "validar":
            self._act_validate()
        elif step_id == "instalar":
            return self._step_install_with_confirmation()
        return True

    def _step_import_with_questions(self) -> bool:
        have = self._ask(lambda: messagebox.askyesno(
            tr("Traducción anterior"),
            tr("¿Tienes una versión anterior de este juego ya traducida, o un parche de "
               "traducción? La app la aprovecha y traduce solo lo que falte.\n\n"
               "Si no tienes ninguna, elige «No»."),
        ))
        ref = ""
        if have:
            ref = self._ask(lambda: filedialog.askdirectory(
                title=tr("Carpeta del juego o parche con la traducción previa"),
                initialdir=self.game_var.get() or None,
            ))
        if not ref:
            self.log(tr("Sin traducción anterior: se traduce todo con el motor."))
            self._mark("importar", skipped=True)
            return True
        self._act_import(ref)
        return True

    def _step_translate_with_confirmation(self) -> bool:
        if not self._snap["has_key"]:
            self._ask(lambda: messagebox.showinfo(
                tr("Falta la clave"),
                tr("Para traducir hace falta la clave de tu motor de traducción.\n\n"
                   "Pulsa «Conseguir clave…», pégala en «Clave API» y vuelve a empezar: "
                   "la app sigue donde se quedó."),
            ))
            self.log(tr("Detenido: falta la clave API. Pégala y pulsa de nuevo el botón."))
            return False
        self._ensure_info()
        n = pipeline.count_to_translate(self.info, self.ws, self._snap["language"])
        if n == 0:
            self.log(tr("No hay textos nuevos por traducir."))
            self._mark("traducir")
            return True
        label = ENGINES[self._snap["engine"]].label
        go = self._ask(lambda: messagebox.askyesno(
            tr("Traducir con {label}", label=label),
            tr("Faltan {n} textos por traducir con {label}.\n"
               "Esto usa tu cuota o saldo de la API (con Gemini gratis es sin costo, "
               "dentro de sus límites).\n\n¿Continuar?", n=n, label=label),
        ))
        if not go:
            self.log(tr("Detenido antes de traducir. Cuando quieras, vuelve a pulsar el botón."))
            return False
        self._act_translate()
        return True

    def _step_install_with_confirmation(self) -> bool:
        res = self._validated
        if res is None:
            self._act_validate()
            res = self._validated
        extra = tr("{n} líneas no pasaron la validación y quedarán sin traducir.\n", n=len(res.failed)) if res.failed else ""
        ok = self._ask(lambda: messagebox.askyesno(
            tr("Instalar la traducción"),
            tr("Se escribirán {n} traducciones en el juego.\n", n=res.applied) + extra
            + tr("\nSe guarda un respaldo antes de escribir (carpeta «respaldos»).\n\n¿Instalar ahora?"),
        ))
        if not ok:
            self.log(tr("Instalación cancelada. Pulsa de nuevo cuando quieras instalarla."))
            return False
        self._act_install()
        return True

    # --- botones de la guía ------------------------------------------------------

    def run_auto(self):
        """Hace todos los pasos que falten, preguntando solo lo necesario."""
        def work():
            if self.info is None or self.ws is None:
                self._act_analyze()
            self._ensure_info()
            guard, installed = 0, False
            while guard < 20:
                guard += 1
                steps = workflow.load_state(self.ws.base)
                nxt = workflow.next_step(self.info, steps)
                if nxt is None:
                    break
                self.log(f"-- {tr(workflow.STEP_BY_ID[nxt].title)} --")
                if not self._do_step(nxt):
                    return
                installed = installed or nxt == "instalar"
            if not installed:  # al instalar ya se avisó
                self.log(tr("Listo. Abre el juego: debe iniciar en {lang}.", lang=languages.label_for(self._snap["language"])))
        self._run("Traducir este juego (automático)", work)

    def step_next(self):
        def work():
            self._ensure_info()
            nxt = workflow.next_step(self.info, workflow.load_state(self.ws.base))
            if nxt is None:
                self.log(tr("No queda nada por hacer en este juego."))
                return
            self.log(f"-- {tr(workflow.STEP_BY_ID[nxt].title)} --")
            self._do_step(nxt)
        self._run("Siguiente paso", work)

    # --- botones manuales (un paso cada uno) ----------------------------------

    def step_analyze(self):
        self._run("Revisar el juego", self._act_analyze)

    def step_collect(self):
        self._run("Extraer los scripts", self._act_collect)

    def step_decompile(self):
        self._run("Decompilar con unrpyc", self._act_decompile)

    def step_generate(self):
        self._run("Crear la lista de textos con el SDK", self._act_generate)

    def step_extras(self):
        self._run("Buscar textos sin marcar", self._act_extras)

    def step_import(self):
        """Elegir un juego (otra versión) con traducción y usarla de base."""
        ref = filedialog.askdirectory(
            title=tr("Carpeta del juego o parche con la traducción previa"),
            initialdir=self.game_var.get() or None,
        )
        if not ref:
            return
        self._run("Usar traducción anterior", lambda: self._act_import(ref))

    def step_translate(self):
        self._run("Traducir lo que falta", self._act_translate)

    def step_validate(self):
        self._run("Revisar las traducciones (sin escribir)", self._act_validate)

    def step_install(self):
        self._run("Instalar en el juego", self._act_install)

    def step_pending(self):
        def work():
            self._ensure_info()
            self.report = pipeline.detect_pending(self.info, self.ws, self._snap["language"], self.log)
            report = self.report
            self.events.put(("call", lambda: self._show_report(report)))
        self._run("Ver pendientes", work)

    # --- ventanas auxiliares ----------------------------------------------------

    def open_ui_tweaks(self):
        """Elegir el aspecto de la caja de diálogo (archivo aparte, reversible)."""
        try:
            self._ensure_info_sync()
        except Exception as exc:
            self.log(f"ERROR: {exc}")
            return
        game_dir = self.info.game_dir
        win = tk.Toplevel(self)
        win.title(tr("Caja de diálogo"))
        win.resizable(False, False)
        ttk.Label(
            win,
            text=tr("Cambia solo el aspecto de la caja de texto, en el archivo\n"
                    "game/{file}. Los scripts del juego no se tocan.", file=uitweaks.FILE_NAME),
        ).pack(anchor="w", padx=12, pady=(10, 6))
        mode = tk.StringVar(value=uitweaks.current_mode(game_dir))
        for key, label in uitweaks.MODES.items():
            ttk.Radiobutton(win, text=tr(label), value=key, variable=mode).pack(anchor="w", padx=20, pady=2)

        def apply():
            uitweaks.apply(game_dir, mode.get())
            self.log(tr("Caja de diálogo: {mode}. Reinicia el juego para verlo.", mode=tr(uitweaks.MODES[mode.get()])))
            win.destroy()

        row = ttk.Frame(win)
        row.pack(fill="x", padx=12, pady=10)
        ttk.Button(row, text=tr("Aplicar"), command=apply).pack(side="right")
        ttk.Button(row, text=tr("Cancelar"), command=win.destroy).pack(side="right", padx=6)

    def open_glossary(self):
        try:
            self._ensure_info_sync()
        except Exception as exc:
            self.log(f"ERROR: {exc}")
            return
        info, ws = self.info, self.ws
        win = tk.Toplevel(self)
        win.title(f"{tr('Glosario')} — {info.name}")
        win.geometry("520x480")
        ttk.Label(
            win,
            text=tr("Una línea por término. «Nombre» = no se traduce; «Uncle = Tío» = se traduce siempre así.\n"
                    "Si lo dejas vacío, la app lo crea sola al traducir."),
            wraplength=490,
        ).pack(anchor="w", padx=8, pady=6)
        box = scrolledtext.ScrolledText(win, wrap="word")
        box.pack(fill="both", expand=True, padx=8)
        box.insert("1.0", Glossary.load(ws.glossary_file).to_text())

        def suggest():
            current = Glossary.from_text(box.get("1.0", "end"))
            added = current.add_missing(
                suggest_terms(find_characters(pipeline.script_dirs(info, ws)), self._language())
            )
            box.delete("1.0", "end")
            box.insert("1.0", current.to_text())
            self.log(tr("Glosario: {n} nombres sugeridos automáticamente.", n=added))

        def save():
            g = Glossary.from_text(box.get("1.0", "end"))
            g.save(ws.glossary_file)
            self.log(f"Glosario guardado: {len(g.terms)} términos en {ws.glossary_file}")
            workflow.mark(ws.base, "glosario")
            self._refresh_guide()
            win.destroy()

        row = ttk.Frame(win)
        row.pack(fill="x", padx=8, pady=8)
        ttk.Button(row, text=tr("Sugerir personajes"), command=suggest).pack(side="left")
        ttk.Button(row, text=tr("Guardar"), command=save).pack(side="right")
        ttk.Button(row, text=tr("Cancelar"), command=win.destroy).pack(side="right", padx=6)


def main():
    app = App()
    app.mainloop()
