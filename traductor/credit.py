"""Crédito de la traducción, añadido al final de la pantalla «Acerca de» del juego.

Siempre se añade el nombre de la app, en el idioma de la traducción («Traducción con TraductorRenPy»), y la
dirección de su página. Solo se omite si el juego no tiene una pantalla «Acerca de» o esta aún no está traducida.

Ren'Py guarda ese texto en `gui.about` (o `config.about`), normalmente dentro de una llamada `_p(...)` con comillas
triples. Se busca en los scripts del juego y se añade el crédito a su traducción en `tl/<idioma>`. Es idempotente:
el bloque de crédito va siempre al final y, si cambia, se reemplaza en vez de repetirse. No toca la caché.
"""

import re
from pathlib import Path
from typing import Dict, Iterable, Optional

from . import about, languages
from .about import APP_NAME
from .translate import Cache

# «Traducción con <app>» en cada idioma de la lista; cualquier otro usa inglés.
APP_LINE = {
    "spanish": "Traducción con {app}",
    "portuguese": "Tradução com {app}",
    "french": "Traduit avec {app}",
    "german": "Übersetzt mit {app}",
    "italian": "Tradotto con {app}",
    "russian": "Перевод выполнен с помощью {app}",
    "polish": "Przetłumaczono za pomocą {app}",
    "turkish": "{app} ile çevrildi",
}
DEFAULT_APP_LINE = "Translated with {app}"

_ABOUT = re.compile(
    r"""^[ \t]*(?:define[ \t]+)?(?:gui|config)\.about[ \t]*=[ \t]*_p?\(\s*(\"\"\"|'''|"|')(.*?)\1\s*\)""",
    re.DOTALL | re.MULTILINE,
)
_OLD = re.compile(r'^(\s*)old "(.*)"\s*$')
_NEW = re.compile(r'^(\s*)new "(.*)"\s*$')


def app_line(language: str) -> str:
    """La línea fija con el nombre de la app, en el idioma de la traducción."""
    code = languages.get(language).code
    if languages.is_spanish(language):
        code = "spanish"
    return APP_LINE.get(code, DEFAULT_APP_LINE).format(app=APP_NAME)


def project_page() -> str:
    """Dirección de la página del proyecto, sin «https://» (vacía si no está definida)."""
    return re.sub(r"^https?://", "", (about.REPO_URL or "").strip()).rstrip("/")


def build_credit(language: str, personal: str = "") -> str:
    """Texto del crédito: la línea de la app, su página y, debajo, un crédito personal si se da
    (la ventana no lo ofrece por ahora; queda previsto para una versión de pago o con donación)."""
    lines = [app_line(language)]
    if project_page():
        lines.append(project_page())
    lines += [" ".join(l.split()) for l in (personal or "").splitlines() if l.strip()]
    return "\n".join(lines)


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


def _without_old_credit(base: str, marker: str) -> str:
    """Quita un bloque de crédito anterior (siempre al final): desde la línea que lleva `marker`."""
    pos = base.find(marker)
    if pos < 0:
        return base
    cut = base.rfind("\n", 0, pos)
    return base[:cut].rstrip() if cut >= 0 else ""


def add_credit(changes: Dict[Path, str], tl_dir: Path, about_text: str, credit: str, cache: Cache) -> int:
    """Añade `credit` (varias líneas con \\n) a la traducción de «Acerca de». Actualiza `changes`
    (ruta -> texto nuevo) y devuelve cuántas entradas modificó (0 si no la encuentra o ya estaba igual)."""
    credit = "\n".join(" ".join(l.split()) for l in credit.splitlines() if l.strip())
    first = credit.split("\n", 1)[0]
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
            current = _unescape(n.group(2)).strip() or (cache.get(_unescape(m.group(2))) or "").strip()
            if not current:
                continue  # sin traducir todavía: se añadirá cuando esté traducida
            base = _without_old_credit(current, first)
            new_value = (base + "\n\n" + credit) if base else credit
            if new_value == current:
                continue  # ya está tal cual
            lines[j] = f'{n.group(1)}new "{_escape(new_value)}"'
            touched = True
            done += 1
        if touched:
            changes[path] = "\n".join(lines)
    return done
