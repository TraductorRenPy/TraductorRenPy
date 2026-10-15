"""Lectura y extracción de archivos .rpa de Ren'Py (RPA-2.0 y RPA-3.x).

Solo se leen el encabezado y el índice (al final del archivo), de modo que
analizar un .rpa de varios GB es instantáneo. Solo se extraen scripts.

El índice es un pickle; se carga con un Unpickler restringido para que un .rpa
malicioso no pueda ejecutar código.
"""

import codecs
import io
import pickle
import threading
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, List, Optional

from .common import LogFn, ProgressFn, check_cancel, noop_log

SCRIPT_EXTS = (".rpy", ".rpyc", ".rpym", ".rpymc")


class RpaError(Exception):
    pass


@dataclass
class RpaEntry:
    name: str  # ruta relativa a game/, con "/" y ya saneada
    offset: int
    length: int
    prefix: bytes


class _IndexUnpickler(pickle.Unpickler):
    # El índice solo contiene dict/list/tuple/int/str/bytes. Los pickles
    # protocolo 2 de Python 3 serializan bytes con _codecs.encode (y los
    # bytes vacíos como bytes()).
    def find_class(self, module, name):
        if (module, name) == ("_codecs", "encode"):
            return codecs.encode
        if module in ("builtins", "__builtin__") and name == "bytes":
            return bytes
        raise RpaError(f"El índice contiene un objeto no permitido: {module}.{name}")


def _to_bytes(value) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("latin-1", errors="replace")
    raise RpaError(f"Tipo inesperado en el índice: {type(value).__name__}")


def _clean_name(raw) -> Optional[str]:
    """Normaliza el nombre interno; None si es inseguro (ruta absoluta, '..')."""
    name = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    name = name.replace("\\", "/")
    parts = PurePosixPath(name).parts
    if not parts or name.startswith("/") or ".." in parts or ":" in parts[0]:
        return None
    return "/".join(parts)


@dataclass
class RpaIndex:
    path: Path
    version: str
    entries: List[RpaEntry] = field(default_factory=list)
    unsafe_names: int = 0

    def scripts(self, exts: Iterable[str] = SCRIPT_EXTS) -> List[RpaEntry]:
        exts = tuple(exts)
        return [e for e in self.entries if e.name.lower().endswith(exts)]


def read_index(path) -> RpaIndex:
    path = Path(path)
    with open(path, "rb") as f:
        header = f.readline(256)
        parts = header.split()
        if not parts or not parts[0].startswith(b"RPA-"):
            raise RpaError("No es un archivo RPA (encabezado desconocido).")
        version = parts[0].decode("ascii", errors="replace")
        try:
            offset = int(parts[1], 16)
            if version.startswith("RPA-3.2"):
                key = 0
                for sub in parts[3:]:
                    key ^= int(sub, 16)
            elif version.startswith("RPA-3"):
                key = int(parts[2], 16)
            elif version.startswith("RPA-2"):
                key = 0
            else:
                raise RpaError(f"Versión de RPA no soportada: {version}")
        except (IndexError, ValueError):
            raise RpaError("Encabezado RPA mal formado.")

        f.seek(offset)
        try:
            raw_index = zlib.decompress(f.read())
            index = _IndexUnpickler(io.BytesIO(raw_index), encoding="bytes").load()
        except (zlib.error, pickle.UnpicklingError, EOFError) as exc:
            raise RpaError(f"No se pudo leer el índice: {exc}")

    if not isinstance(index, dict):
        raise RpaError("El índice del RPA no es un diccionario.")

    result = RpaIndex(path=path, version=version)
    for raw_name, segments in index.items():
        name = _clean_name(raw_name)
        if name is None:
            result.unsafe_names += 1
            continue
        try:
            seg = segments[0]
            off, length = int(seg[0]) ^ key, int(seg[1]) ^ key
            prefix = _to_bytes(seg[2]) if len(seg) > 2 else b""
        except (IndexError, TypeError, ValueError):
            continue
        result.entries.append(RpaEntry(name, off, length, prefix))
    return result


@dataclass
class ExtractResult:
    extracted: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)  # ya extraídos desde otro .rpa
    errors: List[str] = field(default_factory=list)


def extract_scripts(
    rpa_path,
    out_dir,
    wanted: Optional[Callable[[RpaEntry], bool]] = None,
    already_written: Optional[set] = None,
    log: LogFn = noop_log,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[threading.Event] = None,
) -> ExtractResult:
    """Extrae los scripts de un .rpa a out_dir (estructura relativa a game/).

    `wanted` filtra entradas; `already_written` (nombres en minúsculas) evita
    que un segundo .rpa pise un archivo ya extraído en la misma corrida.
    """
    index = read_index(rpa_path)
    out_dir = Path(out_dir)
    if already_written is None:
        already_written = set()
    entries = [e for e in index.scripts() if wanted is None or wanted(e)]
    result = ExtractResult()
    if index.unsafe_names:
        log(f"  Aviso: {index.unsafe_names} nombres inseguros ignorados en {index.path.name}")

    with open(index.path, "rb") as f:
        for i, entry in enumerate(entries, 1):
            check_cancel(cancel)
            if progress:
                progress(i, len(entries))
            low = entry.name.lower()
            if low in already_written:
                result.skipped.append(entry.name)
                log(f"  Duplicado en otro .rpa, se omite: {entry.name}")
                continue
            try:
                f.seek(entry.offset)
                data = entry.prefix + f.read(entry.length - len(entry.prefix))
                target = out_dir / entry.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            except OSError as exc:
                result.errors.append(f"{entry.name}: {exc}")
                continue
            already_written.add(low)
            result.extracted.append(entry.name)
    return result
