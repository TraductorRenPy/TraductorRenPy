"""Mejora de una traducción EXISTENTE (por ejemplo la de la comunidad, hecha casi siempre sin contexto).

El motor de IA recibe cada línea con su original en inglés, la traducción actual y la escena que la rodea, y
devuelve la misma traducción si está bien o una corregida si tiene un problema real (sentido literal, frases
antinaturales, concordancia...). Los resultados se guardan en una caché propia (`revision.json`) y NO se escriben en
el juego hasta que el usuario lo decide («aplicar»), con respaldo y validación de etiquetas y variables.

Se salta lo que escribió esta misma app (archivos `zz_*`, que ya se tradujeron con contexto) y lo que no tiene
texto traducible.
"""

import hashlib
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .common import LogFn, ProgressFn, check_cancel, noop_log
from .engines import BadResponse, Batch, Engine, EngineError, Item
from .glossary import Glossary
from .pending import (
    RE_NEW, RE_OLD, RE_STRING, RE_TRANSLATE, TRANSLATED, TlEntry, TlReport, _split_statement, block_end,
    has_translatable_text, is_say,
)
from .textutil import fix_newlines, fix_quotes
from .translate import make_batches
from .validate import validate

Pair = Tuple[str, str]  # (original inglés, traducción actual)


def pair_key(src: str, cur: str) -> str:
    return hashlib.sha1((src + "\x00" + cur).encode("utf-8")).hexdigest()[:16]


class ReviewCache:
    """{clave: {src, cur, new, engine, rejected?}}; se guarda tras cada lote."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.items: Dict[str, dict] = {}
        try:
            self.items = json.loads(self.path.read_text(encoding="utf-8")).get("items", {})
        except (OSError, ValueError):
            pass

    def get(self, src: str, cur: str) -> Optional[dict]:
        return self.items.get(pair_key(src, cur))

    def put(self, src: str, cur: str, new: str, engine: str, rejected: str = "") -> None:
        row = {"src": src, "cur": cur, "new": new, "engine": engine}
        if rejected:
            row["rejected"] = rejected
        with self._lock:
            self.items[pair_key(src, cur)] = row

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"version": 1, "items": self.items}, indent=1, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    def changed(self) -> Dict[Pair, str]:
        """{(original, actual): corregida} de lo que el motor cambió y no fue rechazado."""
        return {
            (r["src"], r["cur"]): r["new"]
            for r in self.items.values()
            if r["new"] != r["cur"] and not r.get("rejected")
        }


@dataclass
class ReviewUnit:
    text: str  # original inglés (el nombre `text` permite reutilizar make_batches)
    cur: str  # traducción actual
    who: Optional[str]
    file: str = ""
    line: int = 0
    before: List[Tuple[Optional[str], str]] = field(default_factory=list)
    after: List[Tuple[Optional[str], str]] = field(default_factory=list)


def is_reviewable(e: TlEntry, only: str = "") -> bool:
    if e.status != TRANSLATED or Path(e.file).name.startswith("zz_"):
        return False  # los zz_* los escribió esta app, ya con contexto
    if only and only.lower() not in e.file.lower():
        return False
    return e.translated != e.original and has_translatable_text(e.original)


def build_units(
    report: TlReport, characters: Optional[Dict[str, str]] = None, only: str = "",
    context_before: int = 3, context_after: int = 2,
) -> List[ReviewUnit]:
    """Líneas traducidas por revisar (una por pareja original/traducción), con la escena como contexto."""
    characters = characters or {}

    def name(who):
        return characters.get(who, who) if who else None

    entries = report.entries
    units, seen = [], set()
    for idx, e in enumerate(entries):
        if not is_reviewable(e, only) or (e.original, e.translated) in seen:
            continue
        seen.add((e.original, e.translated))
        before, after = [], []
        if e.kind == "dialogue":
            lo = idx - 1
            while lo >= 0 and len(before) < context_before:
                n = entries[lo]
                if n.file != e.file or n.kind != "dialogue":
                    break
                before.insert(0, (name(n.who), n.original))
                lo -= 1
            hi = idx + 1
            while hi < len(entries) and len(after) < context_after:
                n = entries[hi]
                if n.file != e.file or n.kind != "dialogue":
                    break
                after.append((name(n.who), n.original))
                hi += 1
        units.append(ReviewUnit(e.original, e.translated, name(e.who), e.file, e.line, before, after))
    return units


@dataclass
class ReviewResult:
    reviewed: int = 0
    changed: int = 0
    rejected: int = 0
    skipped: int = 0  # el motor no devolvió esa línea: queda sin revisar


def _to_batch(units: List[ReviewUnit], glossary: Glossary) -> Tuple[Batch, Dict[str, ReviewUnit]]:
    items = [Item(str(i + 1), u.text, u.who, u.cur) for i, u in enumerate(units)]
    batch = Batch(
        items=items, before=units[0].before, after=units[-1].after, glossary=glossary.relevant([u.text for u in units])
    )
    return batch, {it.id: u for it, u in zip(items, units)}


def _decide(unit: ReviewUnit, answer: str) -> Tuple[str, str]:
    """(texto final, motivo de rechazo). Si hay rechazo el texto final es la traducción actual."""
    new = fix_quotes(fix_newlines((answer or "").strip()))
    if not new:
        return unit.cur, "respuesta vacía"
    if new == unit.cur:
        return unit.cur, ""
    final, reasons, _ = validate(unit.text, new)
    if final is None:
        return unit.cur, "; ".join(reasons)
    if final == unit.text and unit.cur != unit.text:
        return unit.cur, "devolvió el inglés sin traducir"
    return final, ""


def _review_batch(units, engine, glossary, cache, result, log) -> int:
    """Revisa un lote; si la respuesta es inservible lo parte en dos y reintenta."""
    batch, by_id = _to_batch(units, glossary)
    try:
        out = engine.review(batch)
    except BadResponse as exc:
        if len(units) == 1:
            log(f"  Sin respuesta útil para una línea ({exc}): {units[0].text[:60]}")
            result.skipped += 1
            return 0
        half = len(units) // 2
        log(f"  Respuesta inválida ({exc}); se divide el lote de {len(units)} en dos.")
        return _review_batch(units[:half], engine, glossary, cache, result, log) + _review_batch(
            units[half:], engine, glossary, cache, result, log
        )
    got = 0
    for item_id, unit in by_id.items():
        if item_id not in out:
            result.skipped += 1
            continue
        final, rejected = _decide(unit, out[item_id])
        cache.put(unit.text, unit.cur, final, engine.name, rejected)
        result.reviewed += 1
        got += 1
        if rejected:
            result.rejected += 1
        elif final != unit.cur:
            result.changed += 1
    return got


def run_review(
    units: List[ReviewUnit],
    engine: Engine,
    glossary: Glossary,
    cache: ReviewCache,
    batch_size: int = 20,
    log: LogFn = noop_log,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[threading.Event] = None,
    max_consecutive_failures: int = 3,
) -> ReviewResult:
    result = ReviewResult()
    todo = [u for u in units if cache.get(u.text, u.cur) is None]
    log(f"{len(units)} líneas por revisar: {len(units) - len(todo)} ya revisadas, {len(todo)} pendientes.")
    batches = make_batches(todo, batch_size)
    failures = 0
    for n, batch in enumerate(batches, 1):
        check_cancel(cancel)
        if progress:
            progress(n - 1, len(batches))
        try:
            got = _review_batch(batch, engine, glossary, cache, result, log)
        except EngineError as exc:
            if exc.fatal:
                cache.save()
                raise
            log(f"  Lote {n}/{len(batches)} falló: {exc}")
            failures += 1
            if failures >= max_consecutive_failures:
                cache.save()
                raise EngineError(f"{failures} lotes seguidos fallaron; se detiene el trabajo.")
            continue
        failures = 0
        cache.save()
        log(f"  Lote {n}/{len(batches)}: {got}/{len(batch)} revisadas.")
    if progress:
        progress(len(batches), len(batches))
    return result


def stats(units: List[ReviewUnit], cache: ReviewCache) -> Dict[str, int]:
    total = len(units)
    rows = [cache.get(u.text, u.cur) for u in units]
    done = [r for r in rows if r is not None]
    return {
        "total": total,
        "reviewed": len(done),
        "pending": total - len(done),
        "changed": sum(1 for r in done if r["new"] != r["cur"] and not r.get("rejected")),
        "rejected": sum(1 for r in done if r.get("rejected")),
    }


def report_text(units: List[ReviewUnit], cache: ReviewCache) -> str:
    """Informe legible de los cambios sugeridos: dónde está cada línea, antes y ahora."""
    where: Dict[Pair, ReviewUnit] = {(u.text, u.cur): u for u in units}
    rows = []
    for (src, cur), new in cache.changed().items():
        u = where.get((src, cur))
        rows.append((u.file if u else "", u.line if u else 0, src, cur, new))
    rows.sort()
    out = [f"REVISIÓN DE LA TRADUCCIÓN: {len(rows)} cambios sugeridos", ""]
    for file, line, src, cur, new in rows:
        out += [f"[{file}:{line}]", f"  EN:    {src}", f"  ANTES: {cur}", f"  AHORA: {new}", ""]
    rejected = [r for r in cache.items.values() if r.get("rejected")]
    if rejected:
        out += [f"Respuestas descartadas por no pasar la validación: {len(rejected)}", ""]
        for r in rejected[:30]:
            out += [f"  EN: {r['src'][:90]}", f"  motivo: {r['rejected']}"]
    return "\n".join(out) + "\n"


# --- aplicar al tl -----------------------------------------------------------------------------------

def _replace_literal(line: str, text: str) -> str:
    m = RE_STRING.search(line)
    return line[: m.start(1)] + text + line[m.end(1):]


def apply_to_text(text: str, changes: Dict[Pair, str]) -> Tuple[str, int]:
    """Reemplaza en el texto de un .rpy del tl las traducciones de `changes`; devuelve (texto, cuántas)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    done, i = 0, 0
    while i < len(lines):
        m = RE_TRANSLATE.match(lines[i])
        if not m:
            i += 1
            continue
        j = block_end(lines, i)
        body = range(i + 1, j)
        if m.group(2) == "strings":
            old_text = None
            for k in body:
                if lines[k].strip().startswith("#"):
                    continue
                if RE_OLD.match(lines[k]):
                    mo = RE_STRING.search(lines[k])
                    old_text = mo.group(1) if mo else None
                elif RE_NEW.match(lines[k]) and old_text is not None:
                    mn = RE_STRING.search(lines[k])
                    key = (old_text, mn.group(1)) if mn else None
                    if key in changes and key[1] != old_text:
                        lines[k] = _replace_literal(lines[k], changes[key])
                        done += 1
                    old_text = None
        elif m.group(2) != "python":
            comments = [
                k for k in body if lines[k].strip().startswith("#") and is_say(lines[k].strip()[1:].strip())
            ]
            stmts = [k for k in body if lines[k].strip() and not lines[k].strip().startswith("#") and is_say(lines[k])]
            if len(comments) == len(stmts):
                for c, s in zip(comments, stmts):
                    orig_stmt = lines[c].strip()[1:].strip()
                    if orig_stmt == lines[s].strip():
                        continue  # sin traducir
                    _, en = _split_statement(orig_stmt)
                    _, current = _split_statement(lines[s])
                    key = (en, current)
                    if en is not None and key in changes:
                        lines[s] = _replace_literal(lines[s], changes[key])
                        done += 1
        i = j
    out = "\n".join(lines)
    return (out if out.endswith("\n") else out + "\n"), done


def apply_to_tl(tl_dir: Path, changes: Dict[Pair, str]) -> Tuple[Dict[Path, str], int]:
    """Calcula (sin escribir) los archivos del tl que cambiarían y cuántas líneas."""
    files: Dict[Path, str] = {}
    total = 0
    for path in sorted(Path(tl_dir).rglob("*.rpy")):
        if path.name.startswith("zz_"):
            continue
        original = path.read_text(encoding="utf-8-sig", errors="replace")
        new_text, n = apply_to_text(original, changes)
        if n:
            files[path] = new_text
            total += n
    return files, total
