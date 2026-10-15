"""Guía del flujo: qué pasos hay, en qué paso va cada juego y cuál sigue.

El estado se guarda en `estado.json` dentro de la carpeta de trabajo del juego.
Marcar un paso invalida los posteriores (si regeneras el tl, hay que volver a
traducir), salvo el análisis y el glosario, que no cambian lo ya hecho.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .detect import GameInfo


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    what: str  # explicación en lenguaje simple
    optional: bool = False
    only_if_scripts_missing: bool = False  # solo si hay .rpa/.rpyc por abrir
    invalidates_later: bool = True


STEPS: List[Step] = [
    Step("analizar", "Revisar el juego",
         "Detecta la carpeta del juego y cómo están guardados sus textos.", invalidates_later=False),
    Step("extraer", "Extraer los scripts",
         "Saca los textos de los archivos .rpa/.rpyc a una carpeta aparte, sin tocar el juego.",
         only_if_scripts_missing=True),
    Step("decompilar", "Decompilar",
         "Convierte esos scripts a texto legible (con unrpyc).", only_if_scripts_missing=True),
    Step("generar", "Crear la lista de textos",
         "Ren'Py prepara el archivo de traducción con todas las líneas del juego."),
    Step("extras", "Buscar textos sin marcar",
         "Encuentra botones, avisos y mensajes que el juego no marcó para traducir."),
    Step("importar", "Usar una traducción anterior",
         "Aprovecha la traducción de otra versión del juego para traducir solo lo nuevo.", optional=True),
    Step("glosario", "Glosario de nombres",
         "Nombres de personajes que no se traducen. Se crea solo.", optional=True, invalidates_later=False),
    Step("traducir", "Traducir lo que falta",
         "Usa tu motor (Gemini, Grok…). Es el único paso que gasta tu cuota de API."),
    Step("validar", "Revisar las traducciones",
         "Comprueba etiquetas, variables y comillas. No escribe nada todavía."),
    Step("instalar", "Instalar en el juego",
         "Escribe la traducción en el juego, con respaldo, y lo deja en el idioma elegido."),
]
STEP_BY_ID: Dict[str, Step] = {s.id: s for s in STEPS}
ORDER = [s.id for s in STEPS]


def state_path(base: Path) -> Path:
    return Path(base) / "estado.json"


def load_state(base: Path) -> Dict[str, dict]:
    try:
        data = json.loads(state_path(base).read_text(encoding="utf-8"))
        return data.get("steps", {})
    except (OSError, ValueError, AttributeError):
        return {}


def _save(base: Path, steps: Dict[str, dict]) -> None:
    Path(base).mkdir(parents=True, exist_ok=True)
    state_path(base).write_text(
        json.dumps({"steps": steps}, indent=1, ensure_ascii=False), encoding="utf-8"
    )


def mark(base: Path, step_id: str, skipped: bool = False) -> Dict[str, dict]:
    """Marca un paso como hecho (o como omitido) e invalida los posteriores."""
    steps = load_state(base)
    if STEP_BY_ID[step_id].invalidates_later:
        later = ORDER[ORDER.index(step_id) + 1:]
        for sid in later:
            if sid != "glosario":  # el glosario no se pierde al rehacer pasos
                steps.pop(sid, None)
    steps[step_id] = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "skipped": skipped}
    _save(base, steps)
    return steps


def applicable(info: Optional[GameInfo], step_id: str) -> bool:
    step = STEP_BY_ID[step_id]
    if step.only_if_scripts_missing:
        return info is not None and info.need_collect
    return True


def next_step(info: Optional[GameInfo], steps: Dict[str, dict]) -> Optional[str]:
    """Primer paso aplicable que aún no está hecho (el glosario es automático)."""
    for step in STEPS:
        if step.id == "glosario":
            continue
        if applicable(info, step.id) and step.id not in steps:
            return step.id
    return None


def status_of(info: Optional[GameInfo], steps: Dict[str, dict], step_id: str, current: Optional[str]) -> str:
    """'hecho' | 'omitido' | 'siguiente' | 'pendiente' | 'no_aplica'."""
    if not applicable(info, step_id):
        return "no_aplica"
    if step_id in steps:
        return "omitido" if steps[step_id].get("skipped") else "hecho"
    return "siguiente" if step_id == current else "pendiente"


def checklist(info: Optional[GameInfo], steps: Dict[str, dict]) -> List[dict]:
    """Filas para mostrar la guía: número, título, explicación y estado."""
    current = next_step(info, steps)
    rows, number = [], 0
    for step in STEPS:
        status = status_of(info, steps, step.id, current)
        if status == "no_aplica":
            continue
        number += 1
        rows.append({
            "id": step.id, "n": number, "title": step.title, "what": step.what,
            "optional": step.optional, "status": status,
        })
    return rows
