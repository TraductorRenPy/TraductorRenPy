"""Ajuste opcional de la caja de diálogo, en un archivo aparte del juego.

Se escribe `game/zz_ui_tweaks.rpy`; los scripts del juego no se tocan y
borrar ese archivo devuelve el diseño original. Variantes:
  - "soft":    solo suaviza el contorno del texto (conserva todo lo demás).
  - "text":    sin barra de fondo; letras blancas con contorno negro.
  - "compact": barra oscura semitransparente y más baja.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from .install import write_text_file

FILE_NAME = "zz_ui_tweaks.rpy"
MODES = {
    "original": "Original del juego",
    "soft": "Contorno discreto (conserva el diseño del juego)",
    "compact": "Compacta (barra oscura más baja)",
    "text": "Solo texto (sin barra)",
}

_HEADER = (
    "# Ajuste de la caja de diálogo creado por TraductorRenPy (modo: @MODE@).\n"
    "# Para volver al diseño original, borra este archivo.\n"
)

# Texto legible sobre la imagen: blanco con contorno negro.
_COMMON = """\
init 100 python:
    style.say_dialogue.color = "#ffffff"
    style.say_label.outlines = @LABEL@
    style.say_dialogue.outlines = @TEXT@
"""

_TEXT = _COMMON + """\
    style.say_window.background = None
    # {alpha=.5} (pensamientos) con fondo transparente quedaría ilegible
    _tb_prev_filter = config.say_menu_text_filter
    def _tb_no_alpha(s):
        if _tb_prev_filter:
            s = _tb_prev_filter(s)
        return s.replace("{alpha=.5}", "").replace("{/alpha}", "")
    config.say_menu_text_filter = _tb_no_alpha
"""

_COMPACT = _COMMON + """\
    style.say_window.background = Solid("#000000b8")
    style.say_window.ysize = 235
    style.say_dialogue.ypos = 58
    _tb_prev_filter = config.say_menu_text_filter
    def _tb_no_alpha(s):
        if _tb_prev_filter:
            s = _tb_prev_filter(s)
        return s.replace("{alpha=.5}", "").replace("{/alpha}", "")
    config.say_menu_text_filter = _tb_no_alpha
"""


# Solo suaviza el contorno del texto; no cambia colores, ni fondo, ni posiciones.
# El grosor se escala con la resolución del juego (1 px en 1080p, 2 px en 4K).
_SOFT = """\
init 100 python:
    _tb_px = max(1, int(round(config.screen_height / 1080.0)))
    style.say_label.outlines = [(_tb_px, "#00000090", 0, 0)]
    style.say_dialogue.outlines = [(_tb_px, "#00000090", 0, 0)]
"""

# Contorno fino de 1 px + sombra suave desplazada 2 px.
_TEXT_OUTLINE = '[(1, "#000000", 0, 0), (0, "#000000a0", 2, 2)]'


def _fill(template: str, label_outline: str, text_outline: str) -> str:
    return template.replace("@LABEL@", label_outline).replace("@TEXT@", text_outline)


# --- pantallas `say` propias con contornos escritos dentro -------------------
# Algunos juegos redefinen `screen say` y ponen `outlines [...]` en cada texto.
# Eso manda sobre los estilos, así que se genera una copia con el contorno suave.

_SAY_HEADER = re.compile(r"^(?:init\s+(-?\d+)\s+|init\s+)?screen\s+say\s*(\(.*\))\s*:\s*$")
_INIT_OFFSET = re.compile(r"^init\s+offset\s*=\s*(-?\d+)\s*$")
_OUTLINES_LINE = re.compile(r"^(\s*)outlines\s*\[.*\]\s*$")
_SOFT_OUTLINE = '[(_tb_px, "#00000090", 0, 0)]'


def find_say_screen(game_dir: Path) -> Optional[Tuple[str, List[str]]]:
    """(args, líneas del cuerpo) de la `screen say` que manda en el juego: la de
    mayor prioridad `init` (a igualdad, la del último archivo). None si no hay."""
    best, best_key = None, None
    for order, path in enumerate(sorted(Path(game_dir).rglob("*.rpy"))):
        if "tl" in path.relative_to(game_dir).parts[:-1] or path.name == FILE_NAME:
            continue
        try:
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError:
            continue
        offset = 0  # `init offset = N` desplaza la prioridad de todo lo que sigue en el archivo
        for i, line in enumerate(lines):
            mo = _INIT_OFFSET.match(line)
            if mo:
                offset = int(mo.group(1))
                continue
            m = _SAY_HEADER.match(line)
            if not m:
                continue
            body = []
            for nxt in lines[i + 1:]:
                if nxt.strip() and not nxt[0].isspace():
                    break
                body.append(nxt)
            key = (offset + int(m.group(1) or 0), order, i)
            if best_key is None or key > best_key:
                best, best_key = (m.group(2), body), key
    return best


def soften_screen(args: str, body: List[str]) -> Optional[str]:
    """Copia de la pantalla con todos sus `outlines` suavizados; None si no tiene."""
    changed, out = False, []
    for line in body:
        m = _OUTLINES_LINE.match(line)
        if m:
            line, changed = f"{m.group(1)}outlines {_SOFT_OUTLINE}", True
        out.append(line)
    if not changed:
        return None
    while out and not out[-1].strip():
        out.pop()
    return f"\n# Copia de la pantalla de diálogo del juego con el contorno suavizado.\n" \
           f"init 999 screen say{args}:\n" + "\n".join(out) + "\n"


def render(mode: str, game_dir: Optional[Path] = None) -> str:
    if mode == "soft":
        text = _HEADER.replace("@MODE@", mode) + _SOFT
        found = find_say_screen(game_dir) if game_dir is not None else None
        screen = soften_screen(*found) if found else None
        return text + screen if screen else text
    if mode == "text":
        body = _fill(_TEXT, _TEXT_OUTLINE, _TEXT_OUTLINE)
    elif mode == "compact":
        body = _fill(_COMPACT, "[]", "[]")
    else:
        raise ValueError(f"Modo desconocido: {mode}")
    return _HEADER.replace("@MODE@", mode) + body


def current_mode(game_dir: Path) -> str:
    path = Path(game_dir) / FILE_NAME
    if not path.is_file():
        return "original"
    first = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[0]
    for mode in ("text", "compact", "soft"):
        if f"modo: {mode}" in first:
            return mode
    return "original"


def apply(game_dir: Path, mode: str) -> Optional[Path]:
    """Aplica la variante; "original" borra el archivo. Devuelve su ruta."""
    game_dir = Path(game_dir)
    path = game_dir / FILE_NAME
    stale = path.with_suffix(".rpyc")
    if mode == "original":
        for p in (path, stale):
            if p.exists():
                p.unlink()
        return None
    write_text_file(path, render(mode, game_dir))
    if stale.exists():
        stale.unlink()
    return path
