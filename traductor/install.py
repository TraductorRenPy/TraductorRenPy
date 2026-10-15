"""Paso 11: escribir las traducciones validadas en tl/<idioma>.

Solo se reemplaza el texto entre comillas de la línea traducida (o del `new`):
ids, comentarios y el resto del archivo quedan byte a byte iguales. Los
archivos se escriben en UTF-8 con BOM y saltos LF, con respaldo previo.
"""

import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .common import LogFn, noop_log
from .pending import (
    block_end,
    PENDING,
    RE_NEW,
    RE_OLD,
    RE_STRING,
    RE_TRANSLATE,
    _identical_status,
    _split_statement,
    is_say,
    scan_tl,
)
from .translate import Cache
from .validate import validate


@dataclass
class Failure:
    file: str
    line: int
    original: str
    translation: str
    reasons: List[str]


@dataclass
class ApplyResult:
    applied: int = 0
    repaired: int = 0
    failed: List[Failure] = field(default_factory=list)
    untranslated: int = 0  # pendientes sin traducción en la caché
    glossary_fixed: int = 0  # textos iguales a un término del glosario que se corrigieron
    changes: Dict[Path, str] = field(default_factory=dict)  # archivo -> texto nuevo


def _replace_literal(line: str, text: str) -> str:
    m = RE_STRING.search(line)
    return line[: m.start(1)] + text + line[m.end(1) :]


def _try_apply(lines, idx, original, cache, rel, result, fixed=None) -> None:
    translation = fixed[original] if fixed and original in fixed else cache.get(original)
    if translation is None:
        result.untranslated += 1
        return
    final, reasons, repaired = validate(original, translation)
    if final is None:
        result.failed.append(Failure(rel, idx + 1, original, translation, reasons))
        return
    lines[idx] = _replace_literal(lines[idx], final)
    result.applied += 1
    result.repaired += repaired


def process_text(
    text: str, cache: Cache, rel: str, result: ApplyResult, fixed=None, target: str = "spanish"
) -> str:
    """Devuelve el texto del tl con los pendientes reemplazados por la caché.

    `fixed` ({texto inglés exacto: traducción obligatoria}) viene del glosario:
    un texto que es exactamente un término (p. ej. el título del juego) se deja
    como el glosario dice, incluso si ya traía otra traducción."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        m = RE_TRANSLATE.match(lines[i])
        if not m:
            i += 1
            continue
        j = block_end(lines, i)
        body = range(i + 1, j)
        if m.group(2) == "strings":
            old_idx, old_text = None, None
            for k in body:
                s = lines[k].strip()
                if s.startswith("#"):
                    continue
                if RE_OLD.match(lines[k]):
                    mo = RE_STRING.search(lines[k])
                    old_idx, old_text = k, (mo.group(1) if mo else None)
                elif RE_NEW.match(lines[k]) and old_text is not None:
                    mn = RE_STRING.search(lines[k])
                    if mn and mn.group(1) == old_text and _identical_status(old_text, target) == PENDING:
                        _try_apply(lines, k, old_text, cache, rel, result, fixed)
                    elif mn and fixed and old_text in fixed and mn.group(1) != fixed[old_text]:
                        lines[k] = _replace_literal(lines[k], fixed[old_text])
                        result.glossary_fixed += 1
                    old_idx, old_text = None, None
        elif m.group(2) != "python":
            comments = [
                k for k in body
                if lines[k].strip().startswith("#") and is_say(lines[k].strip()[1:].strip())
            ]
            stmts = [
                k for k in body
                if lines[k].strip() and not lines[k].strip().startswith("#") and is_say(lines[k])
            ]
            if len(comments) == len(stmts):
                pairs = list(zip(comments, stmts))
            else:
                pairs = []
            for c, s in pairs:
                orig_stmt = lines[c].strip()[1:].strip()
                if orig_stmt != lines[s].strip():  # ya traducida
                    if fixed:
                        _, en = _split_statement(orig_stmt)
                        _, current = _split_statement(lines[s])
                        if en in fixed and current != fixed[en]:
                            lines[s] = _replace_literal(lines[s], fixed[en])
                            result.glossary_fixed += 1
                    continue
                _, text_en = _split_statement(orig_stmt)
                if text_en is None or _identical_status(text_en, target) != PENDING:
                    continue
                _try_apply(lines, s, text_en, cache, rel, result, fixed)
        i = j
    new_text = "\n".join(lines)
    return new_text if new_text.endswith("\n") else new_text + "\n"


def apply_cache_to_tl(tl_dir: Path, cache: Cache, glossary=None) -> ApplyResult:
    """Calcula (sin escribir) los cambios de todos los .rpy de tl_dir."""
    result = ApplyResult()
    fixed = {t.src: t.target for t in glossary.terms} if glossary else None
    for path in sorted(tl_dir.rglob("*.rpy")):
        original = path.read_text(encoding="utf-8-sig", errors="replace")
        rel = path.relative_to(tl_dir).as_posix()
        before = (result.applied, result.glossary_fixed)
        new_text = process_text(original, cache, rel, result, fixed, tl_dir.name)
        if (result.applied, result.glossary_fixed) != before:
            result.changes[path] = new_text
    return result


def write_text_file(path: Path, text: str) -> None:
    """UTF-8 con BOM y saltos LF, escritura atómica."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def backup_dir(src: Path, dest_root: Path, label: str, log: LogFn = noop_log) -> Optional[Path]:
    if not src.is_dir():
        return None
    dest = dest_root / f"{label}_{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(src, dest)
    log(f"Respaldo: {dest}")
    return dest


def write_changes(result: ApplyResult, tl_dir: Path, backups: Path, label: str, log: LogFn = noop_log):
    """Escribe los cambios y verifica que no cambió ningún id ni comentario;
    si algo no cuadra, restaura el respaldo y lanza error."""
    before = scan_tl(tl_dir)
    backup = backup_dir(tl_dir, backups, label, log)
    for path, text in result.changes.items():
        write_text_file(path, text)
    after = scan_tl(tl_dir)
    same_ids = [(e.kind, e.key, e.file) for e in before.entries] == [
        (e.kind, e.key, e.file) for e in after.entries
    ]
    same_comments = [(e.original) for e in before.entries] == [(e.original) for e in after.entries]
    no_new_pending = len(after.pending) <= len(before.pending)
    if not (same_ids and same_comments and no_new_pending):
        if backup is not None:
            shutil.rmtree(tl_dir)
            shutil.copytree(backup, tl_dir)
        raise RuntimeError("La verificación posterior falló; se restauró el respaldo.")
    log(f"Escritos {len(result.changes)} archivos; ids y comentarios intactos.")
    return before, after


ZZ_TEMPLATE = (
    "# Activa el idioma {lang} al iniciar el juego (creado por TraductorRenPy).\n"
    "# Para volver al inglés, borra este archivo.\n"
    'define config.language = "{lang}"\n'
)


def write_language_file(game_dir: Path, language: str, backups: Path, log: LogFn = noop_log) -> Path:
    """Crea game/zz_<idioma>.rpy con config.language (respaldo si ya existía)."""
    path = game_dir / f"zz_{language}.rpy"
    content = ZZ_TEMPLATE.format(lang=language)
    if path.is_file():
        current = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
        if current == content:
            return path
        if re.search(r"config\.(?:default_)?language|change_language|_preferences\.language", current):
            log(f"{path.name} ya activa el idioma; se deja como está.")
            return path
        backups.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backups / f"{path.name}_{time.strftime('%Y%m%d_%H%M%S')}")
    write_text_file(path, content)
    stale = path.with_suffix(".rpyc")
    if stale.exists():
        stale.unlink()
    log(f"Creado {path}")
    return path


def format_report(result: ApplyResult, remaining_after: int) -> str:
    lines = [
        "REPORTE DE TRADUCCIÓN",
        f"Traducidas y escritas: {result.applied} (reparadas automáticamente: {result.repaired})",
        f"Corregidas según el glosario (p. ej. el título del juego): {result.glossary_fixed}",
        f"Fallaron la validación: {len(result.failed)}",
        f"Pendientes sin traducción en la caché: {result.untranslated}",
        f"Pendientes que quedan en el tl: {remaining_after}",
        "",
    ]
    for f in result.failed:
        lines += [
            f"[{f.file}:{f.line}] {'; '.join(f.reasons)}",
            f"  EN: {f.original}",
            f"  ES: {f.translation}",
            "",
        ]
    return "\n".join(lines)
