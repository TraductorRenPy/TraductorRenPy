"""Importar la traducción de una versión anterior (o de otro juego) como
punto de partida: solo lo nuevo o cambiado se traduce con el motor.

Se lee el tl/<idioma> del juego de referencia (suelto, o dentro de un .rpa y
entonces se extrae y decompila). Las traducciones se casan con los pendientes
del juego nuevo de dos formas:
  - por id (`translate spanish <label>_<hash>`): el hash sale del texto inglés,
    así que el mismo id garantiza el mismo original aunque el tl no traiga el
    comentario inglés (caso de los tl decompilados);
  - por texto inglés exacto, cuando el id cambió (label renombrado).
Una traducción solo se acepta si conserva los mismos tokens que el original.
"""

import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import decompile, rpa
from .common import LogFn, check_cancel, noop_log
from .detect import analyze, find_game_root
from .pending import TRANSLATED, TlReport, scan_tl
from .textutil import fix_quotes
from .translate import Cache
from .validate import validate

IMPORT_ENGINE = "importada"


@dataclass
class ReferenceData:
    by_id: Dict[str, str] = field(default_factory=dict)
    by_text: Dict[str, str] = field(default_factory=dict)
    strings: Dict[str, str] = field(default_factory=dict)
    entries: int = 0


@dataclass
class ImportResult:
    by_id: int = 0
    by_text: int = 0
    rejected_tokens: int = 0
    remaining: int = 0
    reference_entries: int = 0

    @property
    def imported(self) -> int:
        return self.by_id + self.by_text


def load_reference(tl_dir: Path) -> ReferenceData:
    """Lee un tl/<idioma> y arma los diccionarios de traducciones útiles."""
    ref = ReferenceData()
    report = scan_tl(tl_dir)
    ref.entries = len(report.entries)
    for e in report.entries:
        if not e.translated:
            continue
        if e.original and e.translated == e.original:
            continue  # sin traducir también en la referencia
        if e.kind == "dialogue":
            ref.by_id[e.key] = e.translated
            if e.original and e.status == TRANSLATED:
                ref.by_text.setdefault(e.original, e.translated)
        else:
            ref.strings.setdefault(e.original, e.translated)
    return ref


def apply_reference(report: TlReport, ref: ReferenceData, cache: Cache) -> ImportResult:
    """Pone en la caché las traducciones de la referencia para los pendientes."""
    result = ImportResult(reference_entries=ref.entries)
    for e in report.pending:
        dst, via = None, ""
        if e.kind == "dialogue" and e.key in ref.by_id:
            dst, via = ref.by_id[e.key], "id"
        if dst is None:
            dst = ref.strings.get(e.original) if e.kind == "string" else None
            if dst is None:
                dst = ref.by_text.get(e.original)
            via = "text"
        if dst is None or dst == e.original:
            result.remaining += 1
            continue
        final, _, _ = validate(e.original, dst)  # tokens, comillas, tags y artefactos q=
        if final is None:
            result.rejected_tokens += 1
            result.remaining += 1
            continue
        cache.put(e.original, fix_quotes(final), IMPORT_ENGINE)
        if via == "id":
            result.by_id += 1
        else:
            result.by_text += 1
    return result


def _pick_language(available: List[str], wanted: str, log: LogFn) -> str:
    if wanted in available:
        return wanted
    lowered = [a for a in available if a.lower() == wanted.lower()]
    if len(lowered) == 1:
        return lowered[0]
    # nombres como "SpanishTE" o "spanish_latam" cuentan como "spanish"
    similar = [a for a in available if wanted.lower() in a.lower()]
    if len(similar) == 1:
        log(f"La referencia no tiene tl/{wanted}; se usa tl/{similar[0]}.")
        return similar[0]
    if len(available) == 1:
        log(f"La referencia no tiene tl/{wanted}; se usa tl/{available[0]}.")
        return available[0]
    raise FileNotFoundError(
        f"La referencia no tiene tl/{wanted}. Idiomas encontrados: "
        + (", ".join(available) if available else "ninguno")
    )


def find_reference_tl(
    ref_path,
    language: str,
    work_dir: Path,
    unrpyc_path: str = "",
    log: LogFn = noop_log,
    cancel: Optional[threading.Event] = None,
) -> Path:
    """Devuelve una carpeta con el tl de la referencia como .rpy legibles.

    Si el tl está suelto en .rpy se usa tal cual. Si hay .rpyc sin .rpy
    (sueltos o dentro de un .rpa) se copian/extraen a `work_dir` y se
    decompilan allí, sin tocar el juego de referencia.
    """
    root = find_game_root(ref_path)
    if root is None:
        raise FileNotFoundError("No se encontró una carpeta `game` en la referencia.")
    info = analyze(ref_path)
    rpa_scripts = {
        r.path: [e.name for e in rpa.read_index(r.path).scripts()]
        for r in info.rpas if not r.error
    }
    langs = set(info.tl_languages)
    for names in rpa_scripts.values():
        for name in names:
            parts = name.split("/")
            if len(parts) > 2 and parts[0].lower() == "tl" and parts[1].lower() != "none":
                langs.add(parts[1])
    language = _pick_language(sorted(langs), language, log)

    loose = root / "game" / "tl" / language
    compiled_only = [
        p for p in loose.rglob("*")
        if p.suffix.lower() in (".rpyc", ".rpymc") and not p.with_suffix(p.suffix[:-1]).exists()
    ] if loose.is_dir() else []
    prefix = f"tl/{language.lower()}/"
    in_rpa = [p for p, names in rpa_scripts.items() if any(n.lower().startswith(prefix) for n in names)]
    if loose.is_dir() and not compiled_only and not in_rpa:
        if not any(loose.rglob("*.rpy")):
            raise FileNotFoundError(f"{loose} no contiene scripts de traducción.")
        return loose

    # Hay que decompilar: se trabaja sobre una copia en work_dir.
    out_tl = work_dir / "game" / "tl" / language
    if work_dir.exists():
        shutil.rmtree(work_dir)
    out_tl.mkdir(parents=True)
    if loose.is_dir():
        for p in loose.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".rpy", ".rpyc", ".rpymc", ".rpym"):
                target = out_tl / p.relative_to(loose)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
    written: set = set()
    for rpa_path in in_rpa:
        check_cancel(cancel)
        log(f"Extrayendo tl/{language} de {rpa_path.name} ...")
        res = rpa.extract_scripts(
            rpa_path,
            work_dir / "game",
            wanted=lambda e: e.name.lower().startswith(prefix),
            already_written=written,
            log=log,
            cancel=cancel,
        )
        log(f"  {len(res.extracted)} archivos extraídos.")
    unrpyc = decompile.find_unrpyc(unrpyc_path)
    if unrpyc is None:
        raise FileNotFoundError(
            "La referencia tiene el tl compilado (.rpyc) y hace falta unrpyc para leerlo."
        )
    ok, failed = decompile.decompile_dir(unrpyc, out_tl, log, cancel)
    log(f"Decompilados: {ok}. Fallidos: {len(failed)}.")
    return out_tl
