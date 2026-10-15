"""Orquesta los pasos 2-5 de la fase 1 sobre un área de trabajo por juego.

El juego original solo se toca en el paso 4 cuando todos sus scripts ya son
.rpy (el SDK escribe ahí tl/<idioma>, y antes se respalda la carpeta previa).
Si hay scripts en .rpa o .rpyc, el SDK corre sobre un proyecto de trabajo
reconstruido con los scripts extraídos y decompilados.
"""

import hashlib
import re
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import credit as credit_mod
from . import decompile, extras, importer, install, rpa, sdk
from .common import LogFn, ProgressFn, check_cancel, noop_log
from .detect import GameInfo, source_key
from .engines import create_engine
from .glossary import Glossary, Term, find_characters, find_game_titles, suggest_terms
from .pending import TlReport, scan_tl
from .translate import Cache, build_units, run_job


@dataclass
class Workspace:
    base: Path

    @property
    def scripts(self) -> Path:
        return self.base / "_scripts_extraidos"

    @property
    def project(self) -> Path:
        return self.base / "proyecto_trabajo"

    @property
    def backups(self) -> Path:
        return self.base / "respaldos"

    @property
    def pending_json(self) -> Path:
        return self.base / "pendientes.json"

    @property
    def cache_file(self) -> Path:
        return self.base / "traducciones.json"

    @property
    def glossary_file(self) -> Path:
        return self.base / "glosario.json"


def make_workspace(workspace_dir, info: GameInfo) -> Workspace:
    safe = re.sub(r"[^\w.-]+", "_", info.name)
    tag = hashlib.md5(str(info.root).lower().encode("utf-8")).hexdigest()[:6]
    return Workspace(Path(workspace_dir) / f"{safe}-{tag}")


def tl_dir_of(project_root: Path, language: str) -> Path:
    return project_root / "game" / "tl" / language


def uses_work_project(info: GameInfo) -> bool:
    return info.need_collect


def sdk_project_root(info: GameInfo, ws: Workspace) -> Path:
    return ws.project if uses_work_project(info) else info.root


# --- Paso 2: reunir/extraer scripts ---------------------------------------

def collect_scripts(
    info: GameInfo,
    ws: Workspace,
    log: LogFn = noop_log,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[threading.Event] = None,
) -> int:
    """Copia los .rpyc sueltos sin .rpy y extrae de los .rpa los scripts que
    faltan, todo a ws.scripts. No modifica el juego."""
    if not info.missing_sources:
        log("No hay scripts que extraer: todo está como .rpy.")
        return 0
    ws.scripts.mkdir(parents=True, exist_ok=True)
    total = 0

    loose = [
        rel for rel in info.loose_compiled
        if info.missing_sources.get(source_key(rel)) == "rpyc"
    ]
    for rel in loose:
        check_cancel(cancel)
        target = ws.scripts / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(info.game_dir / rel, target)
    if loose:
        log(f"Copiados {len(loose)} .rpyc sueltos.")
        total += len(loose)

    wanted_keys = {k for k, o in info.missing_sources.items() if o == "rpa"}
    written: set = set()
    for r in info.rpas:
        if r.error or not r.script_files:
            continue
        check_cancel(cancel)
        log(f"Extrayendo scripts de {r.path.name} ...")
        result = rpa.extract_scripts(
            r.path,
            ws.scripts,
            wanted=lambda e: source_key(e.name) in wanted_keys,
            already_written=written,
            log=log,
            progress=progress,
            cancel=cancel,
        )
        for err in result.errors:
            log(f"  ERROR {err}")
        log(f"  {len(result.extracted)} scripts extraídos.")
        total += len(result.extracted)
    log(f"Scripts en {ws.scripts}")
    return total


# --- Paso 3: decompilar -----------------------------------------------------

def decompile_scripts(
    info: GameInfo,
    ws: Workspace,
    unrpyc_path: str,
    log: LogFn = noop_log,
    cancel: Optional[threading.Event] = None,
) -> List[str]:
    """Decompila los .rpyc de ws.scripts. Devuelve los que fallaron."""
    unrpyc = decompile.find_unrpyc(unrpyc_path)
    if unrpyc is None:
        raise FileNotFoundError(
            "No se encontró unrpyc. Configura la ruta de unrpyc.py "
            "(descárgalo de https://github.com/CensoredUsername/unrpyc, licencia MIT)."
        )
    if not ws.scripts.is_dir():
        raise FileNotFoundError("Primero extrae los scripts (paso 2).")
    ok, failed = decompile.decompile_dir(unrpyc, ws.scripts, log, cancel)
    log(f"Decompilados: {ok}. Fallidos: {len(failed)}.")
    for name in failed:
        log(f"  FALLÓ {name}")
    return failed


# --- Paso 4: generar tl -----------------------------------------------------

def _backup_tl(tl_dir: Path, ws: Workspace, language: str, log: LogFn) -> Optional[Path]:
    if not tl_dir.is_dir():
        return None
    dest = ws.backups / f"tl_{language}_{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(tl_dir, dest)
    log(f"Respaldo de {tl_dir} en {dest}")
    return dest


def build_work_project(info: GameInfo, ws: Workspace, language: str, log: LogFn = noop_log) -> Path:
    """Reconstruye ws.project/game con los .rpy sueltos y los scripts
    extraídos/decompilados. Conserva su tl/ (el SDK solo agrega)."""
    game = ws.project / "game"
    game.mkdir(parents=True, exist_ok=True)
    for child in game.iterdir():
        if child.name == "tl":
            continue
        shutil.rmtree(child) if child.is_dir() else child.unlink()

    copied = 0
    for rel in info.loose_rpy:
        target = game / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(info.game_dir / rel, target)
        copied += 1
    # Se recorre el disco (no las claves en minúsculas) para conservar el
    # nombre original de cada script: tl/ nombra sus archivos igual.
    found = set()
    for src in sorted(ws.scripts.rglob("*")):
        if src.suffix.lower() not in (".rpy", ".rpym"):
            continue
        rel = src.relative_to(ws.scripts).as_posix()
        key = source_key(rel)
        if key not in info.missing_sources:
            continue
        found.add(key)
        target = game / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied += 1
    missing = sorted(set(info.missing_sources) - found)
    if missing:
        log(f"Aviso: {len(missing)} scripts sin .rpy (sin decompilar), no entran al proyecto:")
        for key in missing[:20]:
            log(f"  {key}")

    work_tl = tl_dir_of(ws.project, language)
    real_tl = tl_dir_of(info.root, language)
    if not work_tl.exists() and real_tl.is_dir():
        shutil.copytree(real_tl, work_tl)
        log(f"Se partió del tl/{language} existente del juego.")
    log(f"Proyecto de trabajo: {ws.project} ({copied} scripts)")
    return ws.project


def generate_tl(
    info: GameInfo,
    ws: Workspace,
    sdk_path: str,
    language: str,
    log: LogFn = noop_log,
    cancel: Optional[threading.Event] = None,
) -> TlReport:
    exe = sdk.find_renpy_exe(sdk_path)
    if exe is None:
        raise FileNotFoundError("No se encontró renpy.exe en la ruta del SDK configurada.")

    if uses_work_project(info):
        project = build_work_project(info, ws, language, log)
    else:
        project = info.root
    tl_dir = tl_dir_of(project, language)
    before = len(scan_tl(tl_dir).entries)
    _backup_tl(tl_dir, ws, language, log)

    result = sdk.run_translate(exe, project, language, log, cancel)
    if result.traceback_text:
        log("El SDK reportó errores:\n" + result.traceback_text.strip()[-3000:])
        raise RuntimeError("El SDK terminó con errores (ver registro).")
    if result.returncode != 0:
        raise RuntimeError(f"renpy terminó con código {result.returncode}.")

    report = scan_tl(tl_dir)
    if not tl_dir.is_dir() or not report.entries:
        raise RuntimeError(
            f"El SDK no generó entradas en {tl_dir}. Revisa que los scripts sean válidos."
        )
    log(f"tl/{language}: {before} -> {len(report.entries)} entradas ({len(report.entries) - before:+d}).")
    return report


# --- Pasos 6-7: traducción y glosario --------------------------------------

def script_dirs(info: GameInfo, ws: Workspace) -> List[Path]:
    return [info.game_dir, ws.scripts]


def suggest_glossary(info: GameInfo, ws: Workspace, language: str = "spanish") -> Glossary:
    """Glosario del juego con los nombres de personaje añadidos como sugerencia."""
    glossary = Glossary.load(ws.glossary_file)
    dirs = script_dirs(info, ws)
    glossary.add_missing(suggest_terms(find_characters(dirs), language))
    glossary.add_missing(Term(t) for t in find_game_titles(dirs))  # el título no se traduce
    return glossary


def add_extra_strings(info: GameInfo, ws: Workspace, language: str, log: LogFn = noop_log):
    """Paso 10: agrega al tl los textos sin marcar que hay en los scripts."""
    tl_dir = tl_dir_of(sdk_project_root(info, ws), language)
    if not tl_dir.is_dir():
        raise FileNotFoundError(f"No existe {tl_dir}. Primero genera la traducción (paso 4).")
    dirs = script_dirs(info, ws)
    found = extras.scan_dirs(dirs, find_characters(dirs).keys())
    known = sum(1 for f in found if f.kind == extras.KNOWN)
    log(f"Textos sin marcar en los scripts: {len(found)} ({known} seguros, {len(found) - known} probables).")
    target = tl_dir / extras.EXTRA_FILE
    if target.is_file():
        ws.backups.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, ws.backups / f"{target.name}_{time.strftime('%Y%m%d_%H%M%S')}")
    added = extras.write_extra_strings(tl_dir, language, found)
    log(
        f"Agregados {added} a {target.name}; {len(found) - added} ya tenían entrada en el tl. "
        "Ahora pulsa Pendientes y Traducir."
    )
    return found, added


def import_previous(
    info: GameInfo,
    ws: Workspace,
    language: str,
    ref_path: str,
    unrpyc_path: str = "",
    log: LogFn = noop_log,
    cancel: Optional[threading.Event] = None,
):
    """Usa la traducción de otra versión del juego como punto de partida:
    deja en la caché lo que coincide, para que el paso 6 traduzca solo el resto."""
    report = detect_pending(info, ws, language, log)
    tl_dir = importer.find_reference_tl(
        ref_path, language, ws.base / "_referencia", unrpyc_path, log, cancel
    )
    ref = importer.load_reference(tl_dir)
    log(
        f"Referencia ({tl_dir}): {ref.entries} entradas; "
        f"{len(ref.by_id)} diálogos por id, {len(ref.strings)} strings."
    )
    cache = Cache(ws.cache_file)
    result = importer.apply_reference(report, ref, cache)
    cache.save()
    log(
        f"Importadas {result.imported} traducciones ({result.by_id} por id, "
        f"{result.by_text} por texto); {result.rejected_tokens} descartadas por tokens distintos. "
        f"Quedan {result.remaining} pendientes para traducir con el motor."
    )
    return report, cache, result


def count_to_translate(info: GameInfo, ws: Workspace, language: str) -> int:
    """Textos únicos pendientes que aún no están en la caché (lo que gastaría API)."""
    tl_dir = tl_dir_of(sdk_project_root(info, ws), language)
    report = scan_tl(tl_dir)
    units = build_units(report, find_characters(script_dirs(info, ws)))
    cache = Cache(ws.cache_file)
    return sum(1 for u in units if cache.get(u.text) is None)


def failed_validation_originals(info: GameInfo, ws: Workspace, language: str) -> List[str]:
    """Textos originales cuya traducción en la caché no pasa la validación (sin escribir nada)."""
    tl_dir = tl_dir_of(sdk_project_root(info, ws), language)
    if not tl_dir.is_dir() or not ws.cache_file.is_file():
        return []
    glossary = suggest_glossary(info, ws, language)
    result = install.apply_cache_to_tl(tl_dir, Cache(ws.cache_file), glossary, titles=find_game_titles(script_dirs(info, ws)))
    return sorted({f.original for f in result.failed})


def retry_failed_validation(
    info: GameInfo,
    ws: Workspace,
    language: str,
    engine_name: str,
    engines_cfg: dict,
    batch_size: int = 20,
    log: LogFn = noop_log,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[threading.Event] = None,
    workers: int = 1,
) -> int:
    """Vuelve a traducir, con el motor elegido, las líneas que no pasaron la validación.

    Esas traducciones están en la caché, así que «Traducir lo que falta» las daría por hechas: se quitan
    de la caché (con copia de seguridad) y se traducen de nuevo. Devuelve cuántas se reintentaron."""
    engine = create_engine(engine_name, engines_cfg, language)  # falla pronto si falta la clave
    originals = failed_validation_originals(info, ws, language)
    if not originals:
        log("No hay líneas que hayan fallado la validación.")
        return 0
    ws.backups.mkdir(parents=True, exist_ok=True)
    backup = ws.backups / f"traducciones_antes_de_reintentar_{time.strftime('%Y%m%d_%H%M%S')}.json"
    shutil.copy2(ws.cache_file, backup)
    cache = Cache(ws.cache_file)
    removed = sum(1 for text in originals if cache.remove(text))
    cache.save()
    log(f"Copia de la caché: {backup}")
    log(f"Se volverán a traducir {removed} líneas con {engine.label}.")
    translate_pending(info, ws, language, engine_name, engines_cfg, batch_size, log, progress, cancel, workers=workers)
    return removed


def translate_pending(
    info: GameInfo,
    ws: Workspace,
    language: str,
    engine_name: str,
    engines_cfg: dict,
    batch_size: int = 20,
    log: LogFn = noop_log,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[threading.Event] = None,
    workers: int = 1,
):
    """Traduce los pendientes de tl/<idioma> con un motor y guarda la caché.
    `workers` > 1 = modo avanzado: varias peticiones a la vez (útil con cuentas de pago)."""
    engine = create_engine(engine_name, engines_cfg, language)  # falla pronto si falta la clave
    report = detect_pending(info, ws, language, log)
    units = build_units(report, find_characters(script_dirs(info, ws)))
    if ws.glossary_file.is_file():
        glossary = Glossary.load(ws.glossary_file)
    else:  # primera vez: se arma solo con los nombres de personaje
        glossary = suggest_glossary(info, ws, language)
        glossary.save(ws.glossary_file)
        log(
            f"Glosario creado automáticamente: {len(glossary.terms)} términos "
            f"({', '.join(t.src for t in glossary.terms[:12])}{'…' if len(glossary.terms) > 12 else ''}). "
            "Puedes editarlo en «7. Glosario…»."
        )
    cache = Cache(ws.cache_file)
    log(f"Motor: {engine.label}. Glosario: {len(glossary.terms)} términos.")
    result = run_job(units, engine, glossary, cache, batch_size, log, progress, cancel, workers=workers)
    cache.save()
    log(
        f"Traducidos {result.translated}, de caché {result.from_cache}, "
        f"sin traducir {len(result.failed)}. Caché: {ws.cache_file}"
    )
    for text in result.failed[:10]:
        log(f"  SIN TRADUCIR: {text[:80]}")
    return report, cache, result


# --- Pasos 8 y 11: validar e instalar ----------------------------------------

def validate_translations(info: GameInfo, ws: Workspace, language: str, log: LogFn = noop_log):
    """Simulacro: valida la caché contra los pendientes sin escribir nada."""
    tl_dir = tl_dir_of(sdk_project_root(info, ws), language)
    if not tl_dir.is_dir():
        raise FileNotFoundError(f"No existe {tl_dir}. Primero genera la traducción (paso 4).")
    if not ws.cache_file.is_file():
        raise FileNotFoundError("No hay traducciones todavía (paso 6 o Importar previa).")
    glossary = suggest_glossary(info, ws, language)
    result = install.apply_cache_to_tl(tl_dir, Cache(ws.cache_file), glossary, titles=find_game_titles(script_dirs(info, ws)))
    remaining = len(scan_tl(tl_dir).pending) - result.applied
    _write_report(ws, result, remaining, log, dry_run=True)
    return result


def _write_report(ws: Workspace, result, remaining: int, log: LogFn, dry_run: bool) -> None:
    ws.base.mkdir(parents=True, exist_ok=True)
    report_path = ws.base / "reporte.txt"
    install.write_text_file(report_path, install.format_report(result, remaining))
    verb = "Se escribirían" if dry_run else "Escritas"
    log(
        f"{verb} {result.applied} traducciones ({result.repaired} reparadas); "
        f"fallaron validación: {len(result.failed)}; sin traducir: {result.untranslated}."
    )
    if result.glossary_fixed:
        log(f"{verb} {result.glossary_fixed} correcciones por glosario (p. ej. el título del juego).")
    for f in result.failed[:8]:
        log(f"  FALLÓ [{f.file}:{f.line}] {'; '.join(f.reasons)}")
    if len(result.failed) > 8:
        log(f"  ... y {len(result.failed) - 8} más en el reporte.")
    log(f"Reporte: {report_path}")


def install_translations(info: GameInfo, ws: Workspace, language: str, log: LogFn = noop_log, credit: str = ""):
    """Valida, escribe el tl (con respaldo) y deja el juego en `language`."""
    project = sdk_project_root(info, ws)
    tl_dir = tl_dir_of(project, language)
    if not tl_dir.is_dir():
        raise FileNotFoundError(f"No existe {tl_dir}. Primero genera la traducción (paso 4).")
    if not ws.cache_file.is_file():
        raise FileNotFoundError("No hay traducciones todavía (paso 6 o Importar previa).")

    glossary = suggest_glossary(info, ws, language)
    cache = Cache(ws.cache_file)
    result = install.apply_cache_to_tl(tl_dir, cache, glossary, titles=find_game_titles(script_dirs(info, ws)))
    # El crédito de la app va siempre (más el personal, si hay). Solo se omite si el juego no tiene «Acerca de».
    about = credit_mod.find_about_text(script_dirs(info, ws))
    if about is None:
        log("Crédito: este juego no define una pantalla «Acerca de»; no se añadió el crédito.")
    elif credit_mod.add_credit(result.changes, tl_dir, about, credit_mod.build_credit(language, credit), cache):
        log("Crédito añadido al final de «Acerca de».")
    else:
        log("Crédito: «Acerca de» aún no está traducido o ya lo tenía; no se cambió.")
    if result.changes:
        install.write_changes(result, tl_dir, ws.backups, f"tl_{language}_antes_de_instalar", log)
    remaining = len(scan_tl(tl_dir).pending)

    real_tl = tl_dir_of(info.root, language)
    if project != info.root:  # el tl se generó en el proyecto de trabajo: pasarlo al juego
        install.backup_dir(real_tl, ws.backups, f"juego_tl_{language}", log)
        # solo los .rpy: el juego puede traer otra versión de Ren'Py que recompila los suyos
        shutil.copytree(tl_dir, real_tl, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.rpyc"))
        log(f"tl/{language} copiado al juego: {real_tl}")
    # El .rpyc viejo de un .rpy cambiado se descarta: Ren'Py lo recompila al abrir.
    for path in result.changes:
        stale = real_tl / path.relative_to(tl_dir).with_suffix(".rpyc")
        if stale.exists():
            stale.unlink()
    install.write_language_file(info.game_dir, language, ws.backups, log)
    _write_report(ws, result, remaining, log, dry_run=False)
    return result, remaining


# --- Paso 5: pendientes ---------------------------------------------------

def detect_pending(
    info: GameInfo, ws: Workspace, language: str, log: LogFn = noop_log
) -> TlReport:
    tl_dir = tl_dir_of(sdk_project_root(info, ws), language)
    if not tl_dir.is_dir():
        raise FileNotFoundError(f"No existe {tl_dir}. Primero genera la traducción (paso 4).")
    report = scan_tl(tl_dir)
    ws.base.mkdir(parents=True, exist_ok=True)
    report.to_json(ws.pending_json)
    log(report.summary())
    log(f"Lista de pendientes en {ws.pending_json}")
    return report
