"""Utilidades sobre el texto de un diálogo de Ren'Py (en su forma escapada)."""

import re
from typing import List, Tuple

# Tokens que una traducción debe conservar tal cual: tags {i}, interpolaciones
# [name] (con un nivel de anidado), formatos %s/%(x)d y escapes \n \t \" \\.
TOKEN_RE = re.compile(
    r"\{[^{}]*\}"
    r"|\[(?:[^\[\]]|\[[^\[\]]*\])*\]"
    r"|%\(\w+\)[#0\- +]*\d*[sdifrx]"
    r"|%[sdifrx]"
    r"|\\n|\\t|\\\"|\\\\"
)


def tokens(text: str) -> List[str]:
    return TOKEN_RE.findall(text)


def split_protected(text: str) -> List[Tuple[bool, str]]:
    """Parte el texto en segmentos (es_token, texto)."""
    parts, pos = [], 0
    for m in TOKEN_RE.finditer(text):
        if m.start() > pos:
            parts.append((False, text[pos : m.start()]))
        parts.append((True, m.group(0)))
        pos = m.end()
    if pos < len(text):
        parts.append((False, text[pos:]))
    return parts


def fix_newlines(text: str) -> str:
    """Un salto de línea real dentro de un diálogo rompe el script: se vuelve
    el escape `\\n` (el modelo a veces decodifica el `\\n` del original)."""
    return text.replace("\r\n", "\n").replace("\n", "\\n")


def fix_quotes(text: str) -> str:
    """Escapa las comillas dobles sin escapar (`"` -> `\\"`)."""
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            out.append(text[i : i + 2])
            i += 2
            continue
        out.append('\\"' if ch == '"' else ch)
        i += 1
    return "".join(out)
