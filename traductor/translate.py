"""Paso 6: traducir los pendientes por lotes, con contexto de escena.

Las traducciones van a una caché por juego (texto inglés -> español), de modo
que no se retraduce nada al repetir el trabajo ni al actualizar el juego.
Escribirlas en tl/ es la fase 3 (tras validarlas).
"""

import hashlib
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .common import LogFn, ProgressFn, check_cancel, noop_log
from .engines import BadResponse, Batch, Engine, EngineError, Item
from .glossary import Glossary
from .pending import PENDING, TlEntry, TlReport
from .textutil import fix_newlines, fix_quotes


def text_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


class Cache:
    """Caché JSON {clave: {src, dst, engine}}; se guarda tras cada lote."""

    def __init__(self, path):
        self.path = Path(path)
        self.items: Dict[str, dict] = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = data.get("items", {})
        except (OSError, ValueError):
            pass

    def get(self, text: str) -> Optional[str]:
        row = self.items.get(text_key(text))
        return row["dst"] if row else None

    def put(self, text: str, dst: str, engine: str) -> None:
        self.items[text_key(text)] = {"src": text, "dst": dst, "engine": engine}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"version": 1, "items": self.items}, indent=1, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.path)


@dataclass
class Unit:
    """Un texto inglés único por traducir, con su contexto en la escena."""

    text: str
    who: Optional[str]
    before: List[Tuple[Optional[str], str]] = field(default_factory=list)
    after: List[Tuple[Optional[str], str]] = field(default_factory=list)


def build_units(
    report: TlReport,
    characters: Optional[Dict[str, str]] = None,
    context_before: int = 3,
    context_after: int = 1,
) -> List[Unit]:
    """Pendientes únicos en orden de archivo. `characters` mapea la variable
    del personaje (c, j) a su nombre, que es lo que ve el modelo."""
    characters = characters or {}

    def name(who: Optional[str]) -> Optional[str]:
        return characters.get(who, who) if who else None

    entries = report.entries
    units, seen = [], set()
    for idx, e in enumerate(entries):
        if e.status != PENDING or e.original in seen:
            continue
        seen.add(e.original)
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
        units.append(Unit(e.original, name(e.who), before, after))
    return units


def make_batches(units: List[Unit], size: int, max_chars: int = 6000) -> List[List[Unit]]:
    batches, current, chars = [], [], 0
    for u in units:
        if current and (len(current) >= size or chars + len(u.text) > max_chars):
            batches.append(current)
            current, chars = [], 0
        current.append(u)
        chars += len(u.text)
    if current:
        batches.append(current)
    return batches


def _to_engine_batch(units: List[Unit], glossary: Glossary) -> Tuple[Batch, Dict[str, Unit]]:
    items = [Item(str(i + 1), u.text, u.who) for i, u in enumerate(units)]
    texts = [u.text for u in units]
    batch = Batch(
        items=items,
        before=units[0].before,
        after=units[-1].after,
        glossary=glossary.relevant(texts),
    )
    return batch, {it.id: u for it, u in zip(items, units)}


@dataclass
class JobResult:
    translated: int = 0
    from_cache: int = 0
    failed: List[str] = field(default_factory=list)  # textos que el motor no tradujo


def run_job(
    units: List[Unit],
    engine: Engine,
    glossary: Glossary,
    cache: Cache,
    batch_size: int = 20,
    log: LogFn = noop_log,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[threading.Event] = None,
    max_consecutive_failures: int = 3,
) -> JobResult:
    result = JobResult()
    todo = []
    for u in units:
        if cache.get(u.text) is not None:
            result.from_cache += 1
        else:
            todo.append(u)
    log(f"{len(units)} textos únicos: {result.from_cache} ya en caché, {len(todo)} por traducir.")

    batches = make_batches(todo, batch_size)
    failures_in_row = 0
    for n, units_b in enumerate(batches, 1):
        check_cancel(cancel)
        if progress:
            progress(n - 1, len(batches))
        try:
            got = _translate_units(units_b, engine, glossary, cache, result, log)
        except EngineError as exc:
            if exc.fatal:
                cache.save()
                raise
            log(f"  Lote {n}/{len(batches)} falló: {exc}")
            result.failed.extend(u.text for u in units_b)
            failures_in_row += 1
            if failures_in_row >= max_consecutive_failures:
                cache.save()
                raise EngineError(f"{failures_in_row} lotes seguidos fallaron; se detiene el trabajo.")
            continue
        failures_in_row = 0
        cache.save()
        log(f"  Lote {n}/{len(batches)}: {got}/{len(units_b)} traducidos.")
    if progress:
        progress(len(batches), len(batches))
    return result


def _translate_units(
    units: List[Unit],
    engine: Engine,
    glossary: Glossary,
    cache: Cache,
    result: JobResult,
    log: LogFn,
) -> int:
    """Traduce un lote. Si la respuesta es inservible el lote se divide en dos
    y se reintenta; los ids que falten se reintentan de uno en uno."""
    batch, by_id = _to_engine_batch(units, glossary)
    try:
        out = engine.translate(batch)
    except BadResponse as exc:
        if len(units) == 1:
            log(f"  Sin respuesta útil para una línea ({exc}): {units[0].text[:60]}")
            result.failed.append(units[0].text)
            return 0
        half = len(units) // 2
        log(f"  Respuesta inválida ({exc}); se divide el lote de {len(units)} en dos.")
        return _translate_units(units[:half], engine, glossary, cache, result, log) + _translate_units(
            units[half:], engine, glossary, cache, result, log
        )
    got = 0
    missing = []
    for item_id, unit in by_id.items():
        dst = (out.get(item_id) or "").strip()
        if dst:
            cache.put(unit.text, fix_quotes(fix_newlines(dst)), engine.name)
            result.translated += 1
            got += 1
        else:
            missing.append(unit)
    if missing and len(units) > 1:
        for unit in missing:
            got += _translate_units([unit], engine, glossary, cache, result, log)
    elif missing:
        result.failed.extend(u.text for u in missing)
    return got


def apply_cache(report: TlReport, cache: Cache) -> List[Tuple[TlEntry, str]]:
    """Pendientes del informe que ya tienen traducción en la caché."""
    return [(e, d) for e in report.pending if (d := cache.get(e.original)) is not None]
