"""Aviso de versión nueva: pregunta a GitHub cuál es el último Release y compara con la versión instalada.

Solo AVISA: no descarga ni instala nada. La consulta es una petición pública a la API de GitHub (revela la IP, como
cualquier visita web; no se envía nada del usuario ni de sus juegos). Cualquier fallo se ignora en silencio.
"""

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional, Tuple

from . import __version__, about

TIMEOUT = 6  # segundos


@dataclass(frozen=True)
class UpdateInfo:
    version: str  # p. ej. "1.0.8"
    url: str  # página del Release, para descargar


def parse_version(text: str) -> Tuple[int, ...]:
    """«v1.0.8», «1.0.8-beta» -> (1, 0, 8). Sin números -> ()."""
    return tuple(int(n) for n in re.findall(r"\d+", (text or "").split("-")[0]))


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return bool(a) and bool(b) and a > b


def api_url(repo_url: str) -> str:
    """https://github.com/usuario/repo -> API del último Release. Vacío si la dirección no es de GitHub."""
    m = re.match(r"^https?://github\.com/([^/]+)/([^/#?]+)", (repo_url or "").strip())
    return f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}/releases/latest" if m else ""


def fetch_latest(url: Optional[str] = None, timeout: float = TIMEOUT) -> Optional[UpdateInfo]:
    """Último Release publicado, o None si no se pudo consultar."""
    url = url or api_url(about.REPO_URL)
    if not url:
        return None
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": f"{about.APP_NAME}/{__version__}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = str(data.get("tag_name") or "")
        page = str(data.get("html_url") or "")
    except urllib.error.HTTPError as exc:
        exc.close()
        return None
    except Exception:  # sin internet, límite de GitHub, respuesta rara...: no se molesta al usuario
        return None
    if not parse_version(tag) or not page.startswith("https://"):
        return None
    return UpdateInfo(".".join(str(n) for n in parse_version(tag)), page)


def check(current: str = __version__, url: Optional[str] = None) -> Tuple[bool, Optional[UpdateInfo]]:
    """(¿se pudo consultar?, versión nueva si la hay)."""
    latest = fetch_latest(url)
    if latest is None:
        return False, None
    return True, (latest if is_newer(latest.version, current) else None)
