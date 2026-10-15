"""Paso 4: generar tl/<idioma> con el Ren'Py SDK por línea de comandos."""

import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .common import Cancelled, LogFn, noop_log


@dataclass
class SdkResult:
    returncode: int
    output: str
    traceback_text: str = ""  # contenido de traceback.txt / errors.txt si existe


def find_renpy_exe(sdk_path) -> Optional[Path]:
    """Acepta la carpeta del SDK o el ejecutable (renpy.exe / renpy.sh)."""
    if not sdk_path:
        return None
    p = Path(sdk_path)
    if p.is_file():
        return p
    names = ("renpy.exe",) if sys.platform == "win32" else ("renpy.sh", "renpy.exe")
    for name in names:
        if (p / name).is_file():
            return p / name
    return None


SDK_DOWNLOAD_URL = "https://www.renpy.org/latest.html"


def _known_folder(guid: str) -> Optional[Path]:
    """Ruta real de una carpeta conocida de Windows (respeta las redirigidas)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

        u = uuid.UUID(guid)
        g = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) != 0:
            return None
        path = Path(out.value)
        ctypes.windll.ole32.CoTaskMemFree(out)
        return path
    except (OSError, AttributeError, ValueError):
        return None


def _default_search_roots() -> List[Path]:
    home = Path.home()
    roots = [
        _known_folder("{374DE290-123F-4565-9164-39C4925E467B}"),  # Descargas
        _known_folder("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"),  # Escritorio
        _known_folder("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"),  # Documentos
        home / "Downloads", home / "Desktop", home / "Documents", home, home / "renpy",
    ]
    if sys.platform == "win32":
        roots += [Path(f"{c}:\\") for c in "CDEFG" if os.path.exists(f"{c}:\\")]
        for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            if os.environ.get(var):
                roots.append(Path(os.environ[var]))
    return [r for r in roots if r is not None and r.is_dir()]


def _version_key(path: Path):
    nums = re.findall(r"\d+", path.name)
    return tuple(int(n) for n in nums) or (0,)


def autodetect(roots: Optional[Iterable[Path]] = None, extra_env: bool = True) -> List[Path]:
    """Carpetas del Ren'Py SDK encontradas, la versión más nueva primero.

    Busca carpetas cuyo nombre empiece por «renpy» (hasta dos niveles bajo las
    ubicaciones habituales) que contengan `renpy.exe` / `renpy.sh`.
    """
    found: List[Path] = []

    def consider(p: Path) -> None:
        if p.is_dir() and find_renpy_exe(p) is not None and p not in found:
            found.append(p)

    if extra_env:
        for var in ("RENPY_SDK", "RENPY_PATH"):
            if os.environ.get(var):
                consider(Path(os.environ[var]))
    for root in (roots if roots is not None else _default_search_roots()):
        try:
            level1 = [e for e in os.scandir(root) if e.is_dir() and e.name.lower().startswith("renpy")]
        except OSError:
            continue
        for entry in level1:
            consider(Path(entry.path))
            try:
                for sub in os.scandir(entry.path):
                    if sub.is_dir() and sub.name.lower().startswith("renpy"):
                        consider(Path(sub.path))
            except OSError:
                continue
    return sorted(found, key=_version_key, reverse=True)


def run_translate(
    renpy_exe: Path,
    project_root: Path,
    language: str,
    log: LogFn = noop_log,
    cancel: Optional[threading.Event] = None,
    timeout: float = 900,
) -> SdkResult:
    cmd = [str(renpy_exe), str(project_root), "translate", language]
    log("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    lines = []

    def reader():
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                lines.append(line)
                log("  " + line)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    start = time.monotonic()
    started_wall = time.time()
    try:
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            if time.monotonic() - start > timeout:
                raise TimeoutError(f"El SDK no terminó en {timeout:.0f} s.")
            time.sleep(0.2)
    except BaseException:
        proc.kill()
        raise
    finally:
        t.join(timeout=2)

    tb = ""
    for name in ("traceback.txt", "errors.txt"):
        f = project_root / name
        if f.is_file() and f.stat().st_mtime >= started_wall - 1:
            tb += f.read_text(encoding="utf-8", errors="replace")
    return SdkResult(proc.returncode, "\n".join(lines), tb)
