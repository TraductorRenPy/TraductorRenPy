"""Interfaz en varios idiomas (español e inglés).

Los textos originales del programa están en español y sirven de clave: `tr("Texto")`
devuelve su versión en inglés si la interfaz está en inglés (o el mismo texto si no
hay traducción). Los mensajes dinámicos del registro se traducen con patrones
(`tr_log`). El idioma de la interfaz es independiente del idioma de la traducción.
"""

import re
import sys
from typing import List, Tuple

from .i18n_en import EN, LOG_PATTERNS

_current = "es"
UI_LANGUAGES = ("auto", "es", "en")


def detect_system() -> str:
    """'es' si el idioma de Windows (o del sistema) es español; si no, 'en'."""
    try:
        if sys.platform == "win32":
            import ctypes

            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            return "es" if primary == 0x0A else "en"
        import locale

        code = (locale.getlocale()[0] or "")
        return "es" if code.lower().startswith("es") else "en"
    except (OSError, AttributeError, ValueError):
        return "en"


def resolve(setting: str) -> str:
    return detect_system() if setting not in ("es", "en") else setting


def set_language(code: str) -> None:
    global _current
    _current = "en" if code == "en" else "es"


def current() -> str:
    return _current


def tr(text: str, **kw) -> str:
    """Texto en el idioma de la interfaz; `kw` rellena los {marcadores}."""
    out = EN.get(text, text) if _current == "en" else text
    return out.format(**kw) if kw else out


_COMPILED: List[Tuple["re.Pattern", str]] = []


def _compiled():
    if not _COMPILED:
        for spanish, english in LOG_PATTERNS:
            pattern = re.escape(spanish)
            pattern = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>.+?)", pattern)
            _COMPILED.append((re.compile("^" + pattern + "$", re.S), english))
    return _COMPILED


def tr_log_block(text: str) -> str:
    """Traduce un texto de varias líneas, línea por línea."""
    return "\n".join(tr_log(line) for line in text.splitlines())


def tr_log(message: str) -> str:
    """Traduce un mensaje del registro (exacto o por patrón); si no hay, lo deja igual."""
    if _current != "en":
        return message
    if message.startswith("ERROR: "):
        return "ERROR: " + tr_log(message[7:])
    if message in EN:
        return EN[message]
    # los mensajes pueden llevar sangría o prefijos de «  »
    stripped = message.lstrip()
    indent = message[: len(message) - len(stripped)]
    for rx, english in _compiled():
        m = rx.match(stripped)
        if m:
            try:
                # los datos capturados también se traducen si pueden (p. ej. «Escritas»)
                groups = {k: tr_log(v) for k, v in m.groupdict().items()}
                return indent + english.format(**groups)
            except (KeyError, IndexError):
                return message
    return message
