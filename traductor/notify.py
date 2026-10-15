"""Aviso al terminar un trabajo largo: sonido y parpadeo del botón en la barra de tareas (Windows)."""

import sys


def alert(window, success: bool) -> None:
    """Suena y hace parpadear la ventana. Nunca lanza errores: un aviso no debe romper nada."""
    try:
        if sys.platform == "win32":
            import ctypes
            import winsound

            winsound.MessageBeep(winsound.MB_OK if success else winsound.MB_ICONHAND)
            _flash(window)
        else:
            window.bell()
    except Exception:  # sin sonido o sin pantalla (pruebas)
        pass


def _flash(window) -> None:
    import ctypes
    from ctypes import wintypes

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                    ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]

    hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
    FLASHW_ALL, FLASHW_TIMERNOFG = 3, 12  # parpadea hasta que la ventana vuelva a primer plano
    info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, 0, 0)
    ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
