import sys


def _run_unrpyc():
    """Modo interno del .exe: ejecuta unrpyc.py como si fuera `python unrpyc.py ...`."""
    import runpy
    from pathlib import Path

    # En un .exe sin consola no hay stdout/stderr: se reabren sobre los descriptores
    # heredados (la tubería con la que la app lee el avance de unrpyc).
    for name, fd in (("stdout", 1), ("stderr", 2)):
        if getattr(sys, name, None) is None:
            try:
                setattr(sys, name, open(fd, "w", encoding="utf-8", errors="replace", closefd=False))
            except OSError:
                pass
    if getattr(sys, "frozen", False):
        # unrpyc usa un grupo de procesos (multiprocessing). En el .exe los procesos hijo no
        # encuentran las funciones definidas por runpy y el grupo se queda reintentando sin fin.
        # unrpyc ya trae un modo de un solo proceso para cuando multiprocessing falla: se activa.
        import traceback

        sys.modules["_multiprocessing"] = None  # `import _multiprocessing` fallará a propósito
        original_print_exc = traceback.print_exc

        def quiet_print_exc(*args, **kwargs):
            if not isinstance(sys.exc_info()[1], ImportError):
                original_print_exc(*args, **kwargs)

        traceback.print_exc = quiet_print_exc
    script = sys.argv[2]
    sys.argv = [script] + sys.argv[3:]
    sys.path.insert(0, str(Path(script).resolve().parent))
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    # Necesario en el .exe: unrpyc usa multiprocessing y sin esto cada proceso hijo
    # volvería a abrir el programa entero.
    import multiprocessing

    multiprocessing.freeze_support()
    if len(sys.argv) > 2 and sys.argv[1] == "--unrpyc-run":
        _run_unrpyc()
    else:
        from traductor.gui import main

        main()
