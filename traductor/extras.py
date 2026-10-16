"""Paso 10: textos que el juego muestra sin marcarlos para traducir.

Ren'Py solo extrae al tl los diálogos y lo marcado con _(). Quedan fuera:
prompts de `renpy.input`, `text`/`textbutton`/`label` de pantallas, notificaciones,
textos dentro de listas o diccionarios de Python... Aquí se buscan en los
scripts y se agregan a `tl/<idioma>/zz_extra_strings.rpy` como
`translate <idioma> strings:` (old/new). Ren'Py traduce en ejecución todo texto
mostrado cuyo contenido coincida con un `old`, así que no hace falta tocar el juego.

Un `old` repetido en otro archivo del tl es un error de Ren'Py, por eso se
excluye todo texto que ya tenga entrada en cualquier archivo del idioma.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from .install import write_text_file
from .pending import RE_OLD, RE_STRING, RE_TRANSLATE, has_translatable_text, looks_spanish
from .textutil import fix_quotes

EXTRA_FILE = "zz_extra_strings.rpy"
KNOWN, PROBABLE = "known", "probable"

_Q = r"""(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')"""
# Contextos donde el literal es seguro texto de interfaz.
_RE_SCREEN = re.compile(r"^\s*(?:text|textbutton|label|tooltip)\s+" + _Q)
_RE_CALL = re.compile(
    r"\b(?:renpy\.input|renpy\.notify|Notify|Confirm|Text|renpy\.say|narrator|extend)\s*\(\s*"
    r"(?:(?:prompt|message|what)\s*=\s*)?" + _Q
)
# Líneas que Ren'Py ya cubre: diálogo (translate <id>) y opciones de menú.
_RE_SAY = re.compile(
    r"^\s*(?:[A-Za-z_]\w*(?:\s+[\w@]+)*\s+)?" + _Q + r"(?:\s+(?:with\s+\S+|nointeract|id\s+\S+|\(.*\)))*\s*$"
)
_RE_MENU = re.compile(r"^\s*" + _Q + r"(?:\s+if\s+.*)?\s*:\s*$")
_SKIP_START = re.compile(
    r"^\s*(?:#|(?:\$\s*)?(?:print|raise|assert)\b|(?:\$\s*)?renpy\.(?:log|write_log)\b|image\b|scene\b|show\b|hide\b|play\b|queue\b|stop\b|jump\b|call\b|label\b\s+\w|"
    r"import\b|from\b|style\b|transform\b|define\s+(?:config|gui|persistent)\.|"
    r"define\s+\w+\s*=\s*Character|default\s+(?:persistent)\.)"
)
_PATHLIKE = re.compile(r"[\w ./\\-]*\.(?:png|jpg|jpeg|webp|gif|ogg|mp3|wav|opus|webm|mp4|ttf|otf|rpy|rpyc|py|txt|json)$", re.I)
_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}$")


@dataclass
class Found:
    text: str  # en forma escapada, listo para `old "<text>"`
    file: str  # relativo al directorio escaneado
    line: int
    kind: str  # KNOWN | PROBABLE


def _normalize(double: Optional[str], single: Optional[str]) -> str:
    """Literal -> contenido para un string de comillas dobles de Ren'Py."""
    if double is not None:
        return double
    return fix_quotes(single.replace("\\'", "'"))


def _plausible(text: str, known: bool) -> bool:
    visible = re.sub(r"\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}|\\U[0-9a-fA-F]{8}", "", text)
    if not has_translatable_text(visible) or looks_spanish(text):
        return False
    if len(re.findall(r"[^\W\d_]", visible)) < 2:  # teclas y símbolos sueltos: "H", "x"
        return False
    if _COLOR.fullmatch(text.strip()) or _PATHLIKE.match(text.strip()):
        return False
    if "/" in text and " " not in text.strip():
        return False
    if " " not in text.strip():  # una sola palabra
        if "_" in text or "." in text.strip(".!?¿¡") or not known:
            return False
    return True


def _is_sentence(text: str) -> bool:
    words = len(re.findall(r"[^\W\d_]+", re.sub(r"\{[^}]*\}|\[[^\]]*\]", "", text)))
    return words >= 3 and len(text) >= 20


def scan_source(source: str, rel: str, characters: Iterable[str] = ()) -> List[Found]:
    found: List[Found] = []
    char_call = None
    chars = [re.escape(c) for c in characters if c]
    if chars:
        char_call = re.compile(r"(?<![\w.])(?:" + "|".join(chars) + r")\s*\(\s*" + _Q)
    for n, line in enumerate(source.splitlines(), 1):
        if '"""' in line or "'''" in line:
            continue
        hits = []
        m = _RE_SCREEN.match(line)
        if m:
            hits.append((m.group(1), m.group(2), KNOWN))
        for rx in (_RE_CALL, char_call):
            if rx is not None:
                for m in rx.finditer(line):
                    hits.append((m.group(1), m.group(2), KNOWN))
        if not hits and not _SKIP_START.match(line) and not _RE_SAY.match(line) and not _RE_MENU.match(line):
            for m in re.finditer(_Q, line):
                before = line[: m.start()].rstrip()
                if before.endswith(("_(", "_p(")):
                    continue
                hits.append((m.group(1), m.group(2), PROBABLE))
        for double, single, kind in hits:
            text = _normalize(double, single)
            if not _plausible(text, kind == KNOWN):
                continue
            if kind == PROBABLE and not _is_sentence(text):
                continue
            found.append(Found(text, rel, n, kind))
    return found


def scan_dirs(dirs: Iterable[Path], characters: Iterable[str] = ()) -> List[Found]:
    """Escanea los .rpy de `dirs` (sin las carpetas tl) y quita repetidos."""
    seen: Dict[str, Found] = {}
    characters = list(characters)
    for base in dirs:
        base = Path(base)
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.rpy")):
            rel_parts = path.relative_to(base).parts
            if "tl" in rel_parts[:-1] or path.name.startswith("zz_"):
                continue
            try:
                source = path.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            for f in scan_source(source, f"game/{'/'.join(rel_parts)}", characters):
                prev = seen.get(f.text)
                if prev is None or (prev.kind == PROBABLE and f.kind == KNOWN):
                    seen[f.text] = f
    return list(seen.values())


def existing_olds(tl_dir: Path, skip: Optional[str] = None) -> Set[str]:
    """Todos los `old "..."` ya presentes en los .rpy del tl (menos el archivo `skip`, si se da)."""
    olds: Set[str] = set()
    for path in tl_dir.rglob("*.rpy"):
        if skip and path.name == skip:
            continue
        in_strings = False
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = RE_TRANSLATE.match(line)
            if m:
                in_strings = m.group(2) == "strings"
            elif in_strings and not line.strip().startswith("#"):
                mo = RE_OLD.match(line)
                ms = RE_STRING.search(line) if mo else None
                if ms:
                    olds.add(ms.group(1))
    return olds


def write_extra_strings(tl_dir: Path, language: str, found: List[Found]) -> int:
    """Agrega los textos a tl/<idioma>/zz_extra_strings.rpy (sin repetir `old`).
    Devuelve cuántos se agregaron."""
    existing = existing_olds(tl_dir)
    new = [f for f in found if f.text not in existing]
    if not new:
        return 0
    path = tl_dir / EXTRA_FILE
    prior = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n") if path.is_file() else ""
    if not prior:
        prior = "# Textos que el juego muestra sin marcarlos para traducir (creado por TraductorRenPy).\n"
    lines = [prior.rstrip("\n"), "", f"translate {language} strings:", ""]
    for f in new:
        lines += [f"    # {f.file}:{f.line}", f'    old "{f.text}"', f'    new "{f.text}"', ""]
    tl_dir.mkdir(parents=True, exist_ok=True)
    write_text_file(path, "\n".join(lines))
    return len(new)
