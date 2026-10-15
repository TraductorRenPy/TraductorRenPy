"""Construye la versión para Windows: dist/TraductorRenPy/ y un .zip listo para publicar.

Uso:  python build_exe.py        (requiere: pip install -r requirements-dev.txt)
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from traductor import __version__  # noqa: E402

DIST = ROOT / "dist"
BUILD = ROOT / "build"
NAME = "TraductorRenPy"

# unrpyc se ejecuta como script aparte (runpy), así que PyInstaller no ve sus importaciones.
HIDDEN = [
    "argparse", "base64", "collections", "contextlib", "copy", "glob", "hashlib", "importlib.machinery",
    "inspect", "io", "multiprocessing", "_multiprocessing", "operator", "pathlib", "pickle", "pickletools",
    "re", "struct", "traceback", "types", "zlib",
]


def main() -> None:
    for folder in (DIST, BUILD):
        shutil.rmtree(folder, ignore_errors=True)
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", NAME,
        "--distpath", str(DIST), "--workpath", str(BUILD), "--specpath", str(BUILD),
        "--add-data", f"{ROOT / 'vendor' / 'unrpyc'}{os.pathsep}vendor/unrpyc",
    ]
    icon = ROOT / "assets" / "icon.ico"
    if icon.is_file():
        cmd += ["--icon", str(icon)]
        # También dentro del .exe: la ventana usa este icono en la barra de título y la barra de tareas.
        cmd += ["--add-data", f"{icon}{os.pathsep}assets"]
    for mod in HIDDEN:
        cmd += ["--hidden-import", mod]
    cmd.append(str(ROOT / "main.py"))
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

    out = DIST / NAME
    for extra in ("README.md", "README.es.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md"):
        shutil.copy2(ROOT / extra, out / extra)
    # Instrucciones en texto plano (se abren con doble clic en el Bloc de notas): UTF-8 con BOM y CRLF.
    for name in ("LEEME.txt", "READ_ME_FIRST.txt", "TUTORIAL.txt", "TUTORIAL_EN.txt"):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
        (out / name).write_text(text, encoding="utf-8-sig", newline="")
    shutil.copytree(ROOT / "examples" / "demo_game", out / "examples" / "demo_game")

    archive = DIST / f"{NAME}-v{__version__}-windows.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in out.rglob("*"):
            if path.is_file():
                z.write(path, Path(NAME) / path.relative_to(out))
    print(f"\nListo: {archive} ({archive.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
