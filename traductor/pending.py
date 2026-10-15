"""Paso 5: detectar líneas pendientes en tl/<idioma>.

Un bloque `translate <idioma> <id>:` está pendiente si la línea traducida es
idéntica al comentario `# who "English"`. En `translate <idioma> strings:` lo
está si `new == old`.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import languages

RE_TRANSLATE = re.compile(r"^translate\s+(\w+)\s+(\w+)\s*:\s*$")
RE_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
RE_OLD = re.compile(r'^\s*old\s+(.*\S)\s*$')
RE_NEW = re.compile(r'^\s*new\s+(.*\S)\s*$')
RE_LOCATION = re.compile(r"^#\s*(\S+\.rpym?):(\d+)\s*$")

_TAGS = re.compile(r"\{[^}]*\}|\[[^\]]*\]|%\(\w+\)\w|%[sdif]|\\n|\\t")
_LETTER = re.compile(r"[^\W\d_]")

PENDING, TRANSLATED, TRIVIAL = "pending", "translated", "trivial"
ALREADY_SPANISH = "spanish"  # el "original" ya está en español: no hay que traducirlo

# Palabras muy frecuentes que no existen en el otro idioma (sin ambiguas como a/no/me/he).
_ES_WORDS = frozenset(
    "el la los las de del que y en un una por con para se su al lo como más pero sus ya este "
    "esta esto eso sí porque muy sin sobre también hasta hay donde desde todo nos todos uno les "
    "ni cuando entre yo mi mis tú te tu tus es son está están fue ser era soy eres tengo tiene "
    "qué cómo quién nada algo bien aquí allí ahora siempre nunca pero cuando mientras".split()
)
_EN_WORDS = frozenset(
    "the and to of is that it you i he she was for on are with as his they be at have this from "
    "or had by but not what all were we when your can said there an each which do how their if "
    "will up other about out them these so some her would make like him into time has look more "
    "go see could my than been who its now get i'm it's don't i'll you're what's just really".split()
)
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")


def looks_spanish(text: str) -> bool:
    """Heurística: el texto (sin tags ni variables) parece estar en español."""
    clean = _TAGS.sub(" ", text).lower()
    words = _WORD.findall(clean)
    es = sum(w in _ES_WORDS for w in words)
    en = sum(w in _EN_WORDS for w in words)
    marks = len(re.findall(r"[¿¡ñáéíóúü]", clean))
    return es + 2 * min(marks, 2) > en and es + marks >= 2


def has_translatable_text(text: str) -> bool:
    """True si, quitando tags, variables y escapes, queda al menos una letra."""
    return bool(_LETTER.search(_TAGS.sub("", text)))


def _identical_status(text: str, target: str = "spanish") -> str:
    """Estado de una entrada cuya traducción es idéntica al original.

    «Ya en español» solo se detecta si el idioma destino es el español."""
    if not has_translatable_text(text):
        return TRIVIAL
    return ALREADY_SPANISH if languages.is_spanish(target) and looks_spanish(text) else PENDING


@dataclass
class TlEntry:
    file: str  # relativo a tl/<idioma>
    line: int  # línea del `translate ...:` o del `old`
    kind: str  # "dialogue" | "string"
    key: str  # id del bloque, o texto `old`
    who: Optional[str]
    original: str  # texto inglés (sin las comillas externas)
    translated: str
    status: str
    source_ref: str = ""  # p. ej. "game/script.rpy:34"
    lines: int = 1  # sentencias con texto en el bloque (las strings siempre 1)


@dataclass
class TlReport:
    tl_dir: Path
    entries: List[TlEntry] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for e in self.entries if e.status == status)

    @property
    def pending(self) -> List[TlEntry]:
        return [e for e in self.entries if e.status == PENDING]

    def by_file(self) -> Dict[str, Dict[str, int]]:
        stats: Dict[str, Dict[str, int]] = {}
        for e in self.entries:
            s = stats.setdefault(e.file, {"total": 0, PENDING: 0, TRIVIAL: 0})
            s["total"] += 1
            if e.status == PENDING:
                s[PENDING] += 1
            elif e.status in (TRIVIAL, ALREADY_SPANISH):
                s[TRIVIAL] += 1  # columna "Sin texto / ya en español"
        return stats

    def summary(self) -> str:
        return (
            f"{len(self.entries)} entradas: {self.count(TRANSLATED)} traducidas, "
            f"{self.count(PENDING)} pendientes, "
            f"{self.count(ALREADY_SPANISH)} ya en español, "
            f"{self.count(TRIVIAL)} sin texto traducible (nombres, '...', variables)"
        )

    def to_json(self, path) -> None:
        data = {
            "tl_dir": str(self.tl_dir),
            "pending": [e.__dict__ for e in self.pending],
        }
        Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def _split_statement(stmt: str):
    """(who, texto) de una sentencia say; texto None si no tiene literal."""
    m = RE_STRING.search(stmt)
    if not m:
        return None, None
    head = stmt[: m.start()].strip().split()
    return (head[0] if head else None), m.group(1)


def _parse_dialogue(block: List[str]):
    """De las líneas de un bloque saca (comentarios originales, sentencias)."""
    originals, statements = [], []
    for raw in block:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            originals.append(s[1:].strip())
        else:
            statements.append(s)
    return originals, statements


# Sentencias que pueden aparecer en un bloque de traducción y NO son diálogo
# (p. ej. `voice my_audio["19"]`, `$ x = 1`, `with dissolve`, `nvl clear`).
_NOT_SAY = re.compile(
    r"^(?:voice|\$|with|show|hide|scene|play|queue|stop|window|nvl|pause|call|jump|python|init|"
    r"renpy\.|define|default)\b|^\$"
)


def is_say(stmt: str) -> bool:
    """True si la sentencia es un diálogo (tiene texto y no es voice/$/with...)."""
    s = stmt.strip()
    return not _NOT_SAY.match(s) and _split_statement(s)[1] is not None


def _dialogue_entries(rel, header_line, block_id, block, source_ref, target="spanish") -> List[TlEntry]:
    """Una entrada por cada diálogo del bloque. El primero usa el id del bloque;
    los siguientes `<id>#2`, `<id>#3`..."""
    originals, statements = _parse_dialogue(block)
    if not statements:  # bloque vacío: todo pendiente
        who, text = _split_statement(originals[0]) if originals else (None, None)
        return [TlEntry(rel, header_line, "dialogue", block_id, who, text or "", "", PENDING, source_ref)]
    originals = [o for o in originals if is_say(o)]
    statements = [s for s in statements if is_say(s)]
    if not originals:  # p. ej. tl decompilado, sin los comentarios en inglés
        pairs = [(None, s) for s in statements]
    elif len(originals) == len(statements):
        pairs = list(zip(originals, statements))
    else:  # estructura inesperada: casar cada sentencia con un original igual
        pairs = [(s, s) for s in statements if s in originals]
    entries = []
    for i, (orig, stmt) in enumerate(pairs):
        key = block_id if i == 0 else f"{block_id}#{i + 1}"
        s_who, s_text = _split_statement(stmt)
        if orig is None:
            who, original, status = s_who, "", TRANSLATED
        else:
            who, original = _split_statement(orig)
            original = original or ""
            status = _identical_status(original, target) if orig.strip() == stmt.strip() else TRANSLATED
        entries.append(
            TlEntry(rel, header_line, "dialogue", key, who, original, s_text or "", status,
                    source_ref, len(pairs))
        )
    return entries


def _strings_entries(rel, lines: List[str], start: int, target="spanish") -> List[TlEntry]:
    entries, old, old_line, ref = [], None, 0, ""
    for offset, raw in enumerate(lines):
        s = raw.strip()
        if s.startswith("#"):
            m = RE_LOCATION.match(s)
            if m:
                ref = f"{m.group(1)}:{m.group(2)}"
            continue
        m = RE_OLD.match(raw)
        if m:
            old, old_line = m.group(1), start + offset
            continue
        m = RE_NEW.match(raw)
        if m and old is not None:
            o = RE_STRING.search(old)
            n = RE_STRING.search(m.group(1))
            o_text = o.group(1) if o else old
            n_text = n.group(1) if n else m.group(1)
            if o_text == n_text:
                status = _identical_status(o_text, target)
            elif not n_text and o_text:
                status = PENDING
            else:
                status = TRANSLATED
            entries.append(TlEntry(rel, old_line, "string", o_text, None, o_text, n_text, status, ref))
            old = None
    return entries


def block_end(lines: List[str], i: int) -> int:
    """Índice de la primera línea después del bloque `translate` que empieza en i.

    El cuerpo son líneas en blanco o indentadas. Algunos parches ponen el
    comentario con el inglés en la columna 0 (`#   c "Hello"`) justo antes de la
    línea traducida: sigue siendo del bloque si lo que viene después es una línea
    indentada; si lo siguiente es un `translate`, es el comentario de ubicación
    del bloque siguiente.
    """
    j = i + 1
    while j < len(lines):
        line = lines[j]
        if not line.strip() or line[0] in " \t":
            j += 1
            continue
        if line.startswith("#"):
            k = j + 1
            while k < len(lines) and (not lines[k].strip() or lines[k].startswith("#")):
                k += 1
            if k < len(lines) and lines[k][0] in " \t":
                j += 1
                continue
        break
    return j


def parse_tl_text(text: str, rel: str = "", target: str = "spanish") -> List[TlEntry]:
    lines = text.splitlines()
    entries: List[TlEntry] = []
    i, last_ref = 0, ""
    while i < len(lines):
        line = lines[i]
        m_loc = RE_LOCATION.match(line)
        if m_loc:
            last_ref = f"{m_loc.group(1)}:{m_loc.group(2)}"
        m = RE_TRANSLATE.match(line)
        if not m:
            i += 1
            continue
        block_id = m.group(2)
        j = block_end(lines, i)
        body = lines[i + 1 : j]
        if block_id == "strings":
            entries.extend(_strings_entries(rel, body, i + 2, target))
        elif block_id not in ("python",):
            entries.extend(_dialogue_entries(rel, i + 1, block_id, body, last_ref, target))
        last_ref = ""
        i = j
    return entries


def scan_tl(tl_dir) -> TlReport:
    """Analiza todos los .rpy de `tl_dir` (la carpeta del idioma)."""
    tl_dir = Path(tl_dir)
    report = TlReport(tl_dir=tl_dir)
    if not tl_dir.is_dir():
        return report
    for path in sorted(tl_dir.rglob("*.rpy")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        rel = path.relative_to(tl_dir).as_posix()
        report.entries.extend(parse_tl_text(text, rel, tl_dir.name))  # tl/<idioma>: el nombre es el idioma
    return report
