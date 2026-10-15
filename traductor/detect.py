"""Paso 1: localizar la carpeta del juego y clasificar sus scripts."""

import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .rpa import RpaError, read_index

SRC_EXTS = (".rpy", ".rpym")
COMPILED_EXTS = (".rpyc", ".rpymc")
# Carpetas que nunca contienen scripts originales del juego.
PRUNE_DIRS = {"tl", "cache", "saves", "__pycache__"}
# Carpetas que no se recorren al buscar `game` hacia abajo.
SKIP_WHEN_SEARCHING = {"renpy", "lib", "tl", "saves", "cache", "images", "audio", "gui", "__pycache__"}


def source_key(rel: str) -> Optional[str]:
    """Clave común de un script: 'a/b.rpyc' y 'a/b.rpy' -> 'a/b.rpy'."""
    low = rel.replace("\\", "/").lower()
    if low.endswith(SRC_EXTS):
        return low
    if low.endswith(COMPILED_EXTS):
        return low[:-1]
    return None


def _has_game_files(game_dir: Path) -> bool:
    try:
        with os.scandir(game_dir) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.lower().endswith(
                    SRC_EXTS + COMPILED_EXTS + (".rpa",)
                ):
                    return True
    except OSError:
        pass
    return False


def find_game_root(path, max_depth: int = 4) -> Optional[Path]:
    """Devuelve la carpeta que contiene `game/` (raíz del proyecto Ren'Py).

    Acepta la raíz, la carpeta `game` o una carpeta superior (p. ej. un zip
    descomprimido con carpetas anidadas).
    """
    start = Path(path)
    if not start.is_dir():
        return None
    if start.name.lower() == "game" and _has_game_files(start):
        return start.parent
    queue = deque([(start, 0)])
    while queue:
        current, depth = queue.popleft()
        candidate = current / "game"
        if candidate.is_dir() and _has_game_files(candidate):
            return current
        if depth >= max_depth:
            continue
        try:
            children = sorted(
                (e for e in os.scandir(current) if e.is_dir()), key=lambda e: e.name
            )
        except OSError:
            continue
        for child in children:
            if child.name.lower() not in SKIP_WHEN_SEARCHING:
                queue.append((Path(child.path), depth + 1))
    return None


@dataclass
class RpaInfo:
    path: Path
    size: int
    version: str = ""
    total_files: int = 0
    script_files: List[str] = field(default_factory=list)  # nombres internos
    tl_script_files: int = 0
    error: Optional[str] = None


@dataclass
class GameInfo:
    root: Path
    game_dir: Path
    loose_rpy: List[str] = field(default_factory=list)
    loose_compiled: List[str] = field(default_factory=list)
    rpas: List[RpaInfo] = field(default_factory=list)
    tl_languages: List[str] = field(default_factory=list)
    # clave -> origen ('rpyc' suelto | 'rpa') de scripts sin .rpy suelto
    missing_sources: Dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def need_collect(self) -> bool:
        """Hay scripts que obtener (copiar .rpyc sueltos o extraer de .rpa)."""
        return bool(self.missing_sources)

    @property
    def rpyc_only(self) -> List[str]:
        return [k for k, o in self.missing_sources.items() if o == "rpyc"]

    @property
    def in_rpa_only(self) -> List[str]:
        return [k for k, o in self.missing_sources.items() if o == "rpa"]

    def summary(self) -> str:
        lines = [
            f"Proyecto: {self.root}",
            f".rpy sueltos: {len(self.loose_rpy)}",
            f".rpyc sin .rpy: {len(self.rpyc_only)}",
        ]
        for r in self.rpas:
            if r.error:
                lines.append(f".rpa {r.path.name}: ilegible ({r.error})")
            else:
                lines.append(
                    f".rpa {r.path.name} ({r.version}, {r.size / 1e6:,.0f} MB): "
                    f"{len(r.script_files)} scripts de {r.total_files} archivos"
                )
        lines.append(f"Scripts solo dentro de .rpa: {len(self.in_rpa_only)}")
        lines.append(
            "Idiomas en tl/: " + (", ".join(self.tl_languages) if self.tl_languages else "ninguno")
        )
        if not self.missing_sources:
            lines.append("Resultado: todos los scripts están como .rpy; se puede generar tl directo.")
        else:
            todo = []
            if self.in_rpa_only:
                todo.append("extraer de .rpa")
            todo.append("decompilar con unrpyc")
            lines.append("Resultado: hace falta " + " y ".join(todo) + ".")
        return "\n".join(lines)


def analyze(path) -> GameInfo:
    root = find_game_root(path)
    if root is None:
        raise FileNotFoundError(
            "No se encontró una carpeta `game` con scripts o .rpa dentro de esa ruta."
        )
    game_dir = root / "game"
    info = GameInfo(root=root, game_dir=game_dir)

    rpy_keys: Set[str] = set()
    compiled: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(game_dir):
        dirnames[:] = [d for d in dirnames if d.lower() not in PRUNE_DIRS]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), game_dir).replace("\\", "/")
            key = source_key(rel)
            if key is None:
                if fn.lower().endswith(".rpa"):
                    full = Path(dirpath) / fn
                    info.rpas.append(RpaInfo(path=full, size=full.stat().st_size))
                continue
            if rel.lower().endswith(SRC_EXTS):
                info.loose_rpy.append(rel)
                rpy_keys.add(key)
            else:
                info.loose_compiled.append(rel)
                compiled[key] = rel

    tl_dir = game_dir / "tl"
    if tl_dir.is_dir():
        info.tl_languages = sorted(
            d.name for d in tl_dir.iterdir() if d.is_dir() and d.name.lower() != "none"
        )

    rpa_keys: Set[str] = set()
    for rpa in info.rpas:
        try:
            index = read_index(rpa.path)
        except (RpaError, OSError) as exc:
            rpa.error = str(exc)
            continue
        rpa.version = index.version
        rpa.total_files = len(index.entries)
        for entry in index.scripts():
            if entry.name.lower().startswith("tl/"):
                rpa.tl_script_files += 1
                continue
            rpa.script_files.append(entry.name)
            key = source_key(entry.name)
            if key:
                rpa_keys.add(key)

    for key, rel in compiled.items():
        if key not in rpy_keys and not key.startswith("tl/"):
            info.missing_sources[key] = "rpyc"
    for key in rpa_keys:
        if key not in rpy_keys and key not in info.missing_sources:
            info.missing_sources[key] = "rpa"
    return info
