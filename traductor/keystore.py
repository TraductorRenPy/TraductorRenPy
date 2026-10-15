"""Cifrado de las claves de API en el equipo del usuario (Windows DPAPI).

DPAPI usa las credenciales de la sesión de Windows: el texto cifrado solo se
puede descifrar con el mismo usuario en el mismo equipo. Si el archivo de
ajustes se copia a otro equipo o usuario, las claves no se leen (hay que
volver a pegarlas) en vez de quedar expuestas. Fuera de Windows se guardan en
texto plano, igual que antes.
"""

import base64
import sys

PREFIX = "dpapi:"
_ENTROPY = b"TraductorRenPy.api-key"


def available() -> bool:
    return sys.platform == "win32"


def _blob(data: bytes):
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf, DATA_BLOB


def _call(fn_name: str, data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    inp, keep_in, blob_cls = _blob(data)
    ent, keep_ent, _ = _blob(_ENTROPY)
    out = blob_cls()
    fn = getattr(crypt32, fn_name)
    fn.restype = wintypes.BOOL
    ok = fn(
        ctypes.byref(inp), None, ctypes.byref(ent), None, None, 0, ctypes.byref(out)
    ) if fn_name == "CryptUnprotectData" else fn(
        ctypes.byref(inp), "TraductorRenPy", ctypes.byref(ent), None, None, 0, ctypes.byref(out)
    )
    if not ok:
        raise OSError("DPAPI no pudo procesar el dato")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def protect(text: str) -> str:
    """Texto -> 'dpapi:<base64>' (sin cambios si no hay DPAPI o ya está cifrado)."""
    if not text or not available() or text.startswith(PREFIX):
        return text
    try:
        return PREFIX + base64.b64encode(_call("CryptProtectData", text.encode("utf-8"))).decode("ascii")
    except OSError:
        return text


def unprotect(text: str) -> str:
    """'dpapi:<base64>' -> texto. Un valor sin prefijo (versión anterior) se
    devuelve tal cual; uno que no se puede descifrar devuelve ''."""
    if not text or not text.startswith(PREFIX):
        return text
    if not available():
        return ""
    try:
        return _call("CryptUnprotectData", base64.b64decode(text[len(PREFIX):])).decode("utf-8")
    except (OSError, ValueError):
        return ""
