"""Interfaz común de los motores de traducción y cliente HTTP con reintentos."""

import json
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .. import languages
from ..glossary import Term

_sleep = time.sleep  # sustituible en las pruebas

# Pausa compartida: si el servicio pide esperar (límite por minuto), las demás peticiones simultáneas
# también esperan, en vez de insistir cada una por su cuenta.
_cooldown_lock = threading.Lock()
_cooldown_until = 0.0
_cooldown_owner = None


def _set_cooldown(seconds: float) -> None:
    global _cooldown_until, _cooldown_owner
    with _cooldown_lock:
        until = time.monotonic() + seconds
        if until > _cooldown_until:
            _cooldown_until, _cooldown_owner = until, threading.get_ident()


def _wait_cooldown() -> None:
    """Espera si OTRA petición provocó una pausa (quien la provocó ya espera por su cuenta)."""
    with _cooldown_lock:
        remaining = _cooldown_until - time.monotonic()
        mine = _cooldown_owner == threading.get_ident()
    if remaining > 0 and not mine:
        _sleep(remaining)


class EngineError(Exception):
    """Fallo del motor. `fatal` = no tiene sentido seguir (clave inválida...)."""

    def __init__(self, message: str, fatal: bool = False):
        super().__init__(message)
        self.fatal = fatal


class BadResponse(EngineError):
    """Respuesta recibida pero inservible (no es JSON, formato inesperado).
    Reintentar con un lote más pequeño suele resolverlo."""


@dataclass
class Item:
    id: str  # identificador dentro del lote
    text: str
    who: Optional[str] = None  # nombre del personaje que habla


@dataclass
class Batch:
    items: List[Item]
    before: List[Tuple[Optional[str], str]] = field(default_factory=list)  # contexto previo
    after: List[Tuple[Optional[str], str]] = field(default_factory=list)  # contexto posterior
    glossary: List[Term] = field(default_factory=list)  # términos presentes en el lote


class Engine:
    name = ""
    label = ""
    # Campos de configuración que usa el motor (para la ventana).
    fields = ("api_key", "model", "base_url")
    defaults: Dict[str, str] = {}
    key_url = ""  # página donde el usuario crea su clave
    key_help = ""  # pasos para conseguirla

    def __init__(self, cfg: Dict[str, str]):
        self.cfg = {**self.defaults, **{k: v for k, v in cfg.items() if v}}
        if not self.cfg.get("api_key"):
            raise EngineError(f"Falta la clave de API de {self.label}.", fatal=True)

    min_interval = 0.0  # segundos mínimos entre llamadas (límites del nivel gratuito)
    _last_call: Optional[float] = None
    target = languages.get(languages.DEFAULT)  # idioma destino (lo fija create_engine)

    def _throttle(self) -> None:
        interval = float(self.cfg.get("min_interval", self.min_interval))
        if self._last_call is not None:
            remaining = interval - (time.monotonic() - self._last_call)
            if remaining > 0:
                _sleep(remaining)
        self._last_call = time.monotonic()

    def translate(self, batch: Batch) -> Dict[str, str]:
        """Devuelve {id: traducción}. Puede omitir ids que no pudo traducir."""
        raise NotImplementedError


def post_json(
    url: str,
    headers: Dict[str, str],
    payload,
    timeout: float = 120,
    retries: int = 4,
):
    """POST JSON con reintentos ante 429/5xx y errores de red. Nunca incluye
    las cabeceras (claves) en los mensajes de error."""
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json; charset=utf-8", **headers}
    last = "sin respuesta"
    limit = retries
    attempt = -1
    while attempt < limit:
        attempt += 1
        req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
        wait = 2 ** (attempt + 1)
        _wait_cooldown()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            full = exc.read().decode("utf-8", errors="replace")[:8000]
            exc.close()
            detail = full  # para buscar cuota/retryDelay; el mensaje va recortado
            last = f"HTTP {exc.code}: {full[:400]}"
            if exc.code in (401, 403):
                raise EngineError(f"Clave rechazada o sin permiso ({last})", fatal=True)
            if exc.code == 404:
                raise EngineError(
                    "El modelo no existe o ya no está disponible para tu cuenta. "
                    f"Cambia el campo Modelo. Detalle: {full[:300]}",
                    fatal=True,
                )
            if exc.code not in (408, 429, 500, 502, 503, 504):
                raise EngineError(last)
            if exc.code == 429:
                if "PerDay" in detail or "per day" in detail.lower():
                    raise EngineError(
                        "Se agotó la cuota diaria del servicio. Vuelve a pulsar Traducir "
                        "mañana: lo ya traducido está en la caché.",
                        fatal=True,
                    )
                limit = max(limit, 6)  # los límites por minuto necesitan más paciencia
                wait = max(wait, 15)
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            m = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', detail)
            if retry_after and retry_after.isdigit():
                wait = min(int(retry_after), 90)
            elif m:
                wait = min(float(m.group(1)) + 1, 90)
            if exc.code == 429:
                _set_cooldown(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = f"error de red: {getattr(exc, 'reason', exc)}"
        except ValueError:
            raise EngineError("La respuesta no es JSON válido.")
        if attempt < limit:
            _sleep(wait)
    raise EngineError(f"Sin éxito tras {attempt + 1} intentos ({last})")
