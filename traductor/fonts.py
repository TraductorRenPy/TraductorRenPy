"""Revisión de fuentes: ¿dibujan bien las letras del idioma de la traducción?

Muchos juegos usan fuentes decorativas pensadas solo para inglés. Al traducir salen huecos donde iría la
ñ, la ¿, un acento... Hay dos casos: la letra no existe en la fuente, o existe pero está VACÍA (ocurre de
verdad: Audrey-Bold.otf trae la ñ y la ¿ sin dibujo). Aquí se detectan y se escribe un archivo
`zz_fuentes_<idioma>.rpy` que, solo con ese idioma activo, usa otra fuente en su lugar.

La lectura de fuentes es propia (TrueType/OpenType con cmap y glyf o CFF), sin dependencias externas.
No se detectan acentos mal colocados en una fuente cuyas letras sí existen.
"""

import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from . import languages
from .common import LogFn, noop_log

# Caracteres propios de cada idioma (los que el inglés no usa).
NEEDED = {
    "spanish": "áéíóúüñÁÉÍÓÚÜÑ¿¡",
    "portuguese": "áàâãçéêíóôõúüÁÀÂÃÇÉÊÍÓÔÕÚ",
    "french": "àâçéèêëîïôûùüÿœÀÂÇÉÈÊËÎÏÔÛÙÜŸŒ«»",
    "german": "äöüßÄÖÜ",
    "italian": "àèéìíîòóùúÀÈÉÌÒÙ",
    "russian": "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
    "polish": "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
    "turkish": "çğıöşüÇĞİÖŞÜ",
}
RENPY_FALLBACK = "DejaVuSans.ttf"  # viene con Ren'Py: cualquier juego puede usarla por su nombre
RENPY_FALLBACK_BOLD = "DejaVuSans-Bold.ttf"
EMPTY_CHARSTRING = 4  # bytes: una glifo CFF sin trazos es solo «ancho + endchar»


def needed_chars(language: str) -> str:
    return NEEDED.get(languages.get(language).code, "")


# --- lectura mínima de TrueType / OpenType --------------------------------------------------------

def _tables(data: bytes) -> Dict[str, tuple]:
    base = 0
    if data[:4] == b"ttcf":  # colección: se usa la primera fuente
        base = struct.unpack_from(">I", data, 12)[0]
    num = struct.unpack_from(">H", data, base + 4)[0]
    out = {}
    for i in range(num):
        tag, _chk, off, length = struct.unpack_from(">4sIII", data, base + 12 + 16 * i)
        out[tag.decode("latin-1")] = (off, length)
    return out


def _cmap_lookup(data: bytes, table: tuple):
    """Función codepoint -> glyph id (0 = sin glifo), con la mejor tabla Unicode de la fuente."""
    off, _ = table
    n = struct.unpack_from(">H", data, off + 2)[0]
    best = None
    for i in range(n):
        plat, enc, sub = struct.unpack_from(">HHI", data, off + 4 + 8 * i)
        rank = {(3, 10): 0, (0, 4): 0, (0, 6): 0, (3, 1): 1}.get((plat, enc), 2 if plat == 0 else None)
        if rank is not None and (best is None or rank < best[0]):
            best = (rank, off + sub)
    if best is None:
        return lambda cp: 0
    pos = best[1]
    fmt = struct.unpack_from(">H", data, pos)[0]
    if fmt == 4:
        segx2 = struct.unpack_from(">H", data, pos + 6)[0]
        seg = segx2 // 2
        ends = pos + 14
        starts = ends + segx2 + 2
        deltas = starts + segx2
        ranges = deltas + segx2

        def lookup4(cp):
            if cp > 0xFFFF:
                return 0
            for s in range(seg):
                end = struct.unpack_from(">H", data, ends + 2 * s)[0]
                if cp > end:
                    continue
                start = struct.unpack_from(">H", data, starts + 2 * s)[0]
                if cp < start:
                    return 0
                delta = struct.unpack_from(">h", data, deltas + 2 * s)[0]
                ro = struct.unpack_from(">H", data, ranges + 2 * s)[0]
                if ro == 0:
                    return (cp + delta) & 0xFFFF
                gpos = ranges + 2 * s + ro + 2 * (cp - start)
                gid = struct.unpack_from(">H", data, gpos)[0]
                return (gid + delta) & 0xFFFF if gid else 0
            return 0

        return lookup4
    if fmt == 12:
        groups = struct.unpack_from(">I", data, pos + 12)[0]

        def lookup12(cp):
            for g in range(groups):
                start, end, gid = struct.unpack_from(">III", data, pos + 16 + 12 * g)
                if start <= cp <= end:
                    return gid + (cp - start)
            return 0

        return lookup12
    if fmt == 6:
        first, count = struct.unpack_from(">HH", data, pos + 6)

        def lookup6(cp):
            if first <= cp < first + count:
                return struct.unpack_from(">H", data, pos + 10 + 2 * (cp - first))[0]
            return 0

        return lookup6
    return lambda cp: 0


def _dict_operand_end(data: bytes, i: int) -> int:
    b0 = data[i]
    if b0 == 28:
        return i + 3
    if b0 == 29:
        return i + 5
    if b0 == 30:  # número real: nibbles hasta 0xF
        i += 1
        while i < len(data):
            b = data[i]
            i += 1
            if (b & 0x0F) == 0x0F or (b >> 4) == 0x0F:
                break
        return i
    if 247 <= b0 <= 254:
        return i + 2
    return i + 1


def _cff_charstring_sizes(data: bytes, table: tuple) -> List[int]:
    off, length = table
    cff = data[off:off + length]
    hdr_size = cff[2]

    def read_index(pos):
        count = struct.unpack_from(">H", cff, pos)[0]
        if count == 0:
            return [], pos + 2
        osz = cff[pos + 2]
        offs = [int.from_bytes(cff[pos + 3 + osz * k: pos + 3 + osz * (k + 1)], "big") for k in range(count + 1)]
        base = pos + 3 + osz * (count + 1) - 1
        return [(base + offs[k], base + offs[k + 1]) for k in range(count)], base + offs[-1]

    _names, pos = read_index(hdr_size)
    tops, _pos = read_index(pos)
    top = cff[tops[0][0]:tops[0][1]]
    i, stack = 0, []
    cs_off = None
    while i < len(top):
        b0 = top[i]
        if b0 <= 21:  # operador
            if b0 == 12:
                i += 2
                stack = []
                continue
            if b0 == 17 and stack:  # CharStrings
                cs_off = stack[-1]
            stack = []
            i += 1
            continue
        end = _dict_operand_end(top, i)
        if b0 == 28:
            stack.append(struct.unpack_from(">h", top, i + 1)[0])
        elif b0 == 29:
            stack.append(struct.unpack_from(">i", top, i + 1)[0])
        elif 32 <= b0 <= 246:
            stack.append(b0 - 139)
        elif 247 <= b0 <= 250:
            stack.append((b0 - 247) * 256 + top[i + 1] + 108)
        elif 251 <= b0 <= 254:
            stack.append(-(b0 - 251) * 256 - top[i + 1] - 108)
        else:
            stack.append(0)
        i = end
    if cs_off is None:
        return []
    spans, _ = read_index(cs_off)
    return [e - s for s, e in spans]


def _truetype_glyph_sizes(data: bytes, tables: Dict[str, tuple]) -> List[int]:
    head_off, _ = tables["head"]
    long_loca = struct.unpack_from(">h", data, head_off + 50)[0] == 1
    maxp_off, _ = tables["maxp"]
    n = struct.unpack_from(">H", data, maxp_off + 4)[0]
    loca_off, _ = tables["loca"]
    if long_loca:
        offs = struct.unpack_from(f">{n + 1}I", data, loca_off)
    else:
        offs = [v * 2 for v in struct.unpack_from(f">{n + 1}H", data, loca_off)]
    return [offs[i + 1] - offs[i] for i in range(n)]


def check_font(path, chars: str) -> Optional[List[str]]:
    """Caracteres de `chars` que la fuente no dibuja (no existen o están vacíos).
    None si no se pudo leer (formato no admitido: se deja como está)."""
    try:
        data = Path(path).read_bytes()
        tables = _tables(data)
        if "cmap" not in tables:
            return None
        lookup = _cmap_lookup(data, tables["cmap"])
        if "glyf" in tables and "loca" in tables:
            sizes, empty_at = _truetype_glyph_sizes(data, tables), 0
        elif "CFF " in tables:
            sizes, empty_at = _cff_charstring_sizes(data, tables["CFF "]), EMPTY_CHARSTRING
        else:
            return None
        bad = []
        for ch in dict.fromkeys(chars):
            gid = lookup(ord(ch))
            if gid == 0 or gid >= len(sizes) or sizes[gid] <= empty_at:
                bad.append(ch)
        return bad
    except (OSError, struct.error, IndexError, KeyError, ValueError):
        return None


# --- fuentes del juego -------------------------------------------------------------------------------

_FONT_REF = re.compile(r"""["'=]\s*([^"'{}=\n]*?\.(?:ttf|otf))""", re.IGNORECASE)


def game_fonts(game_dir: Path) -> Dict[str, Path]:
    """nombre (como lo escribe el juego: ruta relativa a game/) -> archivo, de las fuentes sueltas."""
    out: Dict[str, Path] = {}
    game_dir = Path(game_dir)
    for path in sorted(game_dir.rglob("*")):
        if path.suffix.lower() in (".ttf", ".otf") and "tl" not in path.relative_to(game_dir).parts[:-1]:
            out[path.relative_to(game_dir).as_posix()] = path
    return out


def fonts_used(script_dirs: Iterable[Path], available: Iterable[str]) -> Set[str]:
    """Fuentes (de `available`) que los scripts mencionan por nombre."""
    by_lower = {name.lower(): name for name in available}
    used: Set[str] = set()
    for base in script_dirs:
        base = Path(base)
        if not base.is_dir():
            continue
        for path in base.rglob("*.rpy"):
            if "tl" in path.relative_to(base).parts[:-1]:
                continue
            try:
                text = path.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            for m in _FONT_REF.finditer(text):
                name = m.group(1).strip().replace("\\", "/")
                hit = by_lower.get(name.lower())
                if hit:
                    used.add(hit)
    return used


def has_replacement(game_dir: Path, font_name: str) -> bool:
    """¿Ya hay en el juego un reemplazo de esta fuente (hecho por esta app o a mano)?"""
    game_dir = Path(game_dir)
    for path in game_dir.rglob("*.rpy"):
        if "tl" in path.relative_to(game_dir).parts[:-1]:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if "font_replacement_map" in text and font_name in text:
            return True
    return False


@dataclass
class FontProblem:
    name: str  # como lo pide el juego
    chars: List[str]  # lo que no dibuja
    replacement: str = ""  # propuesta


@dataclass
class FontReport:
    problems: List[FontProblem] = field(default_factory=list)
    unreadable: List[str] = field(default_factory=list)


def _is_bold(name: str) -> bool:
    return bool(re.search(r"bold|black|heavy", name, re.IGNORECASE))


def analyze(game_dir: Path, script_dirs: Iterable[Path], language: str) -> FontReport:
    """Fuentes que el juego usa y no dibujan bien el idioma, cada una con una sustituta propuesta."""
    chars = needed_chars(language)
    report = FontReport()
    if not chars:
        return report
    fonts = game_fonts(game_dir)
    used = fonts_used(script_dirs, fonts)
    status: Dict[str, Optional[List[str]]] = {}
    for name in sorted(used):
        status[name] = check_font(fonts[name], chars)
        if status[name] is None:
            report.unreadable.append(name)
    good_used = [n for n, bad in status.items() if bad == []]
    for name, bad in status.items():
        if not bad:
            continue
        same_weight = [n for n in good_used if _is_bold(n) == _is_bold(name)]
        pick = (same_weight or good_used or [""])[0]
        if not pick:
            # ninguna fuente buena entre las usadas: se prueba con el resto de fuentes del juego
            rest = [n for n in sorted(fonts) if n not in status and check_font(fonts[n], chars) == []]
            pick = next((n for n in rest if _is_bold(n) == _is_bold(name)), rest[0] if rest else "")
        report.problems.append(
            FontProblem(name, bad, pick or (RENPY_FALLBACK_BOLD if _is_bold(name) else RENPY_FALLBACK))
        )
    return report


def render_fix(language: str, problems: List[FontProblem]) -> str:
    """Contenido de `zz_fuentes_<idioma>.rpy`."""
    lines = [
        f"# Arreglo de fuentes para {language} (creado por TraductorRenPy).",
        "#",
        "# Algunas fuentes del juego no dibujan bien las letras de este idioma (huecos donde va la ñ, la ¿, ...).",
        f"# Mientras el idioma activo sea {language}, se usa otra fuente en su lugar.",
        "# No modifica los scripts ni las traducciones. Para quitarlo, borra este archivo.",
        "",
        f"translate {language} python:",
    ]
    for p in problems:
        lines.append(f"    # {p.name}: no dibuja {' '.join(p.chars)}")
        lines.append("    for _b in (False, True):")
        lines.append("        for _i in (False, True):")
        lines.append(
            f'            config.font_replacement_map[("{p.name}", _b, _i)] = ("{p.replacement}", _b, _i)'
        )
    return "\n".join(lines) + "\n"


def fix_filename(language: str) -> str:
    return f"zz_fuentes_{language}.rpy"


def write_fix(game_dir: Path, language: str, problems: List[FontProblem], log: LogFn = noop_log) -> Path:
    from .install import write_text_file

    path = Path(game_dir) / fix_filename(language)
    write_text_file(path, render_fix(language, problems))
    log(f"Creado {path}")
    return path
