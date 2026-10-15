"""Motores de traducción conectables. Un motor por trabajo."""

from typing import Dict, Type

from .. import languages
from .base import BadResponse, Batch, Engine, EngineError, Item
from .llm import GeminiEngine, GrokEngine
from .microsoft import MicrosoftEngine

ENGINES: Dict[str, Type[Engine]] = {
    GrokEngine.name: GrokEngine,
    GeminiEngine.name: GeminiEngine,
    MicrosoftEngine.name: MicrosoftEngine,
}


def create_engine(
    name: str, engines_cfg: Dict[str, Dict[str, str]], language: str = languages.DEFAULT
) -> Engine:
    if name not in ENGINES:
        raise EngineError(f"Motor desconocido: {name}", fatal=True)
    engine = ENGINES[name](engines_cfg.get(name, {}))
    engine.target = languages.get(language)
    return engine


__all__ = ["ENGINES", "BadResponse", "Batch", "Engine", "EngineError", "Item", "create_engine"]
