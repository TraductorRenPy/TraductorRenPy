"""Crédito opcional de la traducción, añadido al final de la pantalla «Acerca de» del juego.

Ren'Py guarda ese texto en `gui.about` (o `config.about`), normalmente dentro de una llamada `_p(...)` con comillas triples.
Se busca en los scripts del juego y se añade una línea a su traducción en `tl/<idioma>`. Es idempotente
(no se duplica al instalar otra vez) y no toca la caché de traducciones.
"""

import re
from pathlib import Path
from typing import Dict, Iterable, Optional

from .translate import Cache

_ABOUT = re.compile(
    r"""^[ \t]*(?:define[ \t]+)?(?:gui|config)\.about[ \t]*=[ \t]*_p?\(\s*(\"\"\"|'''|"|')(.*?)\1\s*\)""",
    re.DOTALL | re.MULTILINE,
)
_OLD = re.compile(r'^(\s*)old "(.*)"\s*$')
_NEW = re.compile(r'^(\s*)new "(.*)"\s*$')


def _unescape(s: str) -> str:
    return (s.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\'", "'")
            .replace("\\\\", "\\"))


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _norm(s: str) -> str:
    return " ".join(_unescape(s).split())


def find_about_text(script_dirs: Iterable[Path]) -> Optional[str]:
    """Texto original de «Acerca de» del juego, o None si no lo define."""
    for folder in script_dirs:
        for path in sorted(Path(folder).rglob("*.rpy")):
            try:
                match = _ABOUT.search(path.read_text(encoding="utf-8-sig", errors="replace"))
            except OSError:
                continue
            if match and match.group(2).strip():
                return match.group(2)
    return None


def add_credit(changes: Dict[Path, str], tl_dir: Path, about_text: str, credit: str, cache: Cache) -> int:
    """Añade `credit` a la traducción de «Acerca de». Actualiza `changes` (ruta -> texto nuevo) y
    devuelve cuántas entradas modificó (0 si no la encuentra o ya estaba)."""
    credit = " ".join(credit.split())
    target = _norm(about_text)
    done = 0
    for path in sorted(Path(tl_dir).rglob("*.rpy")):
        text = changes.get(path)
        if text is None:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        lines = text.split("\n")
        touched = False
        for i, line in enumerate(lines):
            m = _OLD.match(line)
            if not m or _norm(m.group(2)) != target:
                continue
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            n = _NEW.match(lines[j]) if j < len(lines) else None
            if not n:
                continue
            base = _unescape(n.group(2)).strip() or (cache.get(_unescape(m.group(2))) or "").strip()
            if not base or credit in base:
                continue  # sin traducir todavía (se añadirá al instalarla) o ya tiene el crédito
            lines[j] = f'{n.group(1)}new "{_escape(base + chr(10) * 2 + credit)}"'
            touched = True
            done += 1
        if touched:
            changes[path] = "\n".join(lines)
    return done
