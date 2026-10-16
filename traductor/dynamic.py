"""Textos que el juego arma por código y muestra con «[variable]».

Ren'Py traduce el TEXTO de una pantalla («[bio]»), pero no el contenido de la variable que se pone dentro: la
descripción o el historial de una ficha, por ejemplo, salen en inglés aunque estén en `zz_extra_strings.rpy`.
Dos piezas lo resuelven:

1. Un gancho `config.replace_text` (archivo `zz_dynamic_text.rpy` en game/) que, justo antes de dibujar cada
   fragmento de texto, lo busca en las traducciones del idioma activo. Si no hay coincidencia, no cambia nada.
2. Ren'Py reparte el texto en fragmentos y los saltos de línea (`\\n`) quedan fuera de ellos, así que un texto que
   empieza o termina con saltos nunca coincidiría. Se añade la misma entrada SIN esos saltos del borde
   (`zz_dynamic_strings.rpy` en tl/<idioma>), con la traducción ya hecha, sin gastar más API.
"""

import re
import shutil
import time
from pathlib import Path
from typing import List, Set, Tuple

from .common import LogFn, noop_log
from .extras import EXTRA_FILE, existing_olds
from .install import write_text_file
from .pending import RE_NEW, RE_OLD, RE_STRING, has_translatable_text

HOOK_FILE = "zz_dynamic_text.rpy"
VARIANTS_FILE = "zz_dynamic_strings.rpy"
HOOK_MARKER = "_tr_dynamic_text"

HOOK_CONTENT = """\
# Traduce en pantalla los textos que el juego arma por código (p. ej. "[variable]") (creado por TraductorRenPy).
# Antes de dibujar cada fragmento de texto lo busca en las traducciones del idioma activo; si no hay, no cambia nada.
# Para quitarlo, borra este archivo.
init 999 python:
    _tr_previous_replace_text = config.replace_text

    def _tr_dynamic_text(s):
        if _tr_previous_replace_text is not None:
            s = _tr_previous_replace_text(s)
        try:
            return renpy.translate_string(s)
        except Exception:
            return s

    config.replace_text = _tr_dynamic_text
"""

_EDGE_LEFT = re.compile(r"^(?:\\n)+")  # el texto «\n» (barra y n), tal como está escrito en los .rpy
_EDGE_RIGHT = re.compile(r"(?:\\n)+$")


def strip_edges(text: str) -> str:
    return _EDGE_RIGHT.sub("", _EDGE_LEFT.sub("", text))


def write_hook(game_dir: Path, backups: Path, log: LogFn = noop_log) -> Path:
    """Crea game/zz_dynamic_text.rpy (respaldo si ya existía otro distinto)."""
    path = Path(game_dir) / HOOK_FILE
    if path.is_file():
        current = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
        if current == HOOK_CONTENT:
            return path
        backups.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backups / f"{path.name}_{time.strftime('%Y%m%d_%H%M%S')}")
    write_text_file(path, HOOK_CONTENT)
    stale = path.with_suffix(".rpyc")
    if stale.exists():
        stale.unlink()
    log(f"Creado {path}")
    return path


def _pairs(path: Path) -> List[Tuple[str, str]]:
    """(old, new) de un archivo `translate <idioma> strings:` con el texto tal como está escrito."""
    pairs, old = [], None
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if line.strip().startswith("#"):
            continue
        if RE_OLD.match(line):
            m = RE_STRING.search(line)
            old = m.group(1) if m else None
        elif RE_NEW.match(line) and old is not None:
            m = RE_STRING.search(line)
            if m:
                pairs.append((old, m.group(1)))
            old = None
    return pairs


def write_edge_variants(tl_dir: Path, language: str) -> int:
    """Escribe tl/<idioma>/zz_dynamic_strings.rpy con la versión sin saltos de borde de cada texto extra ya
    traducido que empiece o termine con ellos. Devuelve cuántas entradas quedaron (0 = no hace falta el archivo)."""
    tl_dir = Path(tl_dir)
    extra = tl_dir / EXTRA_FILE
    target = tl_dir / VARIANTS_FILE
    entries: List[Tuple[str, str]] = []
    if extra.is_file():
        existing: Set[str] = existing_olds(tl_dir, skip=VARIANTS_FILE)
        seen: Set[str] = set()
        for old, new in _pairs(extra):
            variant_old = strip_edges(old)
            if variant_old == old or not variant_old or not has_translatable_text(variant_old):
                continue
            if not new or new == old:
                continue  # aún sin traducir
            variant_new = strip_edges(new)
            if not variant_new or variant_old in existing or variant_old in seen:
                continue
            seen.add(variant_old)
            entries.append((variant_old, variant_new))
    if not entries:
        target.unlink(missing_ok=True)
        return 0
    lines = [
        "# Versiones sin saltos de línea en los bordes de los textos extra, para los que el juego muestra con",
        "# [variable] (creado por TraductorRenPy).",
        "",
        f"translate {language} strings:",
        "",
    ]
    for old, new in entries:
        lines += [f'    old "{old}"', f'    new "{new}"', ""]
    write_text_file(target, "\n".join(lines))
    return len(entries)
