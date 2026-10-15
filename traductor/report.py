"""Diagnóstico para «Reportar un problema»: texto útil y SIN datos privados.

Nada se envía solo: la app muestra el texto y abre una página de GitHub ya
rellenada; la persona lo revisa y decide si lo publica.
"""

import platform
import re
from pathlib import Path
from typing import Iterable, List
from urllib.parse import quote

from . import about

OMITTED = "<línea omitida: contiene texto del juego>"
# Líneas del registro que reproducen texto del juego.
_DROP_MARKERS = (
    "SIN TRADUCIR", "UNTRANSLATED", "Sin respuesta útil para una línea", "No useful response for one line",
)
_WIN_PATH = re.compile(r"[A-Za-z]:\\(?:[^\s\\/:*?\"<>|]+\\)*[^\s\\/:*?\"<>|]*")
_UNIX_PATH = re.compile(r"(?:/home|/Users|/mnt|/media)/[^\s\"']+")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TOKEN = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")


def sanitize(text: str, known_paths: Iterable[str] = ()) -> str:
    """Quita rutas, correos, posibles claves y el nombre de usuario del equipo."""
    paths = sorted({p for p in known_paths if p and len(p) > 3}, key=len, reverse=True)
    for p in paths:
        text = re.sub(re.escape(p), "<ruta>", text, flags=re.IGNORECASE)
    text = _WIN_PATH.sub("<ruta>", text)
    text = _UNIX_PATH.sub("<ruta>", text)
    text = _EMAIL.sub("<correo>", text)
    text = _TOKEN.sub("<oculto>", text)
    user = Path.home().name
    if len(user) > 2:
        text = re.sub(re.escape(user), "<usuario>", text, flags=re.IGNORECASE)
    return text


def clean_log(lines: Iterable[str], known_paths: Iterable[str] = (), last: int = 40) -> List[str]:
    out = []
    for line in list(lines)[-last:]:
        if any(m in line for m in _DROP_MARKERS):
            out.append(OMITTED)
        else:
            out.append(sanitize(line.rstrip(), known_paths))
    return out


def build_diagnostics(
    log_lines: Iterable[str], engine: str, language: str, ui_language: str, known_paths: Iterable[str] = ()
) -> str:
    log = "\n".join(clean_log(log_lines, known_paths))
    return (
        f"TraductorRenPy {about.VERSION}\n"
        f"Windows/OS: {platform.platform()}\n"
        f"Python: {platform.python_version()}\n"
        f"Engine: {engine}\n"
        f"Target language: {language} | UI: {ui_language}\n"
        "\n--- Last log lines (paths, e-mails and keys removed) ---\n"
        f"{log}\n"
    )


def issue_url(repo_url: str, title: str, body: str, max_len: int = 6500) -> str:
    """Dirección de «nuevo issue» con título y texto ya escritos (se recorta si es larga)."""
    base = repo_url.rstrip("/") + "/issues/new"
    suffix = "\n\n…(recortado: pega aquí el resto desde el botón Copiar)"
    url = f"{base}?title={quote(title)}&body={quote(body)}"
    while len(url) > max_len and len(body) > 200:
        body = body[: int(len(body) * 0.8)]
        url = f"{base}?title={quote(title)}&body={quote(body + suffix)}"
    return url
