"""Configuración local del usuario (nunca dentro del proyecto ni de git).

Las claves de API se guardan cifradas (ver `keystore.py`).
"""

import json
import os
import sys
from pathlib import Path

from . import keystore

FROZEN = bool(getattr(sys, "frozen", False))  # ejecutándose como .exe (PyInstaller)
PROJECT_DIR = Path(__file__).resolve().parent.parent
# Dónde están los archivos incluidos (vendor/unrpyc, ...): junto al código o dentro del .exe.
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))
APP_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "TraductorRenPy"
SETTINGS_FILE = APP_DIR / "settings.json"
# Carpeta de trabajo por defecto: junto al proyecto, o en Documentos si es el .exe.
DEFAULT_WORKSPACE = (
    Path.home() / "Documents" / "TraductorRenPy" / "trabajo" if FROZEN else PROJECT_DIR / "trabajo"
)

DEFAULTS = {
    "game_dir": "",
    "sdk_path": "",
    "unrpyc_path": "",
    "workspace_dir": str(DEFAULT_WORKSPACE),
    "language": "spanish",  # idioma destino (nombre de la carpeta tl/)
    "ui_language": "auto",  # idioma de la interfaz: auto | es | en
    "engine": "grok",  # un motor por trabajo
    "batch_size": 20,
    "workers": 1,  # peticiones simultáneas (modo avanzado, para cuentas de pago)
    "notify": True,  # avisar al terminar o fallar un trabajo largo
    "credit": "",  # crédito opcional de la traducción en «Acerca de» del juego
    # Claves y modelos por motor. Solo viven en este archivo local, cifradas.
    "engines": {"grok": {}, "gemini": {}, "microsoft": {}},
}


def load() -> dict:
    data = json.loads(json.dumps(DEFAULTS))
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return data
    engines = saved.pop("engines", {})
    data.update(saved)
    for name, cfg in engines.items():
        merged = data["engines"].setdefault(name, {})
        merged.update(cfg)
        if "api_key" in merged:
            merged["api_key"] = keystore.unprotect(merged["api_key"])
    return data


def save(data: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    out = json.loads(json.dumps(data))
    for cfg in out.get("engines", {}).values():
        if cfg.get("api_key"):
            cfg["api_key"] = keystore.protect(cfg["api_key"])
    SETTINGS_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
