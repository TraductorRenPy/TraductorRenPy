"""Idiomas destino disponibles.

`code` es el nombre que usa Ren'Py para la carpeta `tl/<code>` y para
`config.language` (en minúsculas, en inglés). `prompt` describe al modelo cómo
debe sonar la traducción; `ms` es el código de Microsoft Translator.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Language:
    code: str
    label: str  # nombre para mostrar (en el propio idioma + inglés)
    prompt: str
    ms: str


LANGUAGES: Dict[str, Language] = {l.code: l for l in [
    Language(
        "spanish", "Español neutro / Spanish",
        'neutral Spanish (understood across Latin America and Spain: use "tú", avoid regional slang and voseo)',
        "es",
    ),
    Language(
        "portuguese", "Português (Brasil) / Portuguese",
        "Brazilian Portuguese (natural and clear; use \"você\", avoid European-only expressions)",
        "pt",
    ),
    Language(
        "french", "Français / French",
        'standard French (France; use "tu" between friends and family and "vous" when the context is formal)',
        "fr",
    ),
    Language(
        "german", "Deutsch / German",
        'standard German (use "du" between friends and family and "Sie" when the context is formal)',
        "de",
    ),
    Language(
        "italian", "Italiano / Italian",
        'standard Italian (use "tu" between friends and family and "Lei" when the context is formal)',
        "it",
    ),
    Language("russian", "Русский / Russian", "natural, modern Russian", "ru"),
    Language("polish", "Polski / Polish", "natural, modern Polish", "pl"),
    Language("turkish", "Türkçe / Turkish", "natural, modern Turkish", "tr"),
]}

DEFAULT = "spanish"


def get(code: str) -> Language:
    """Idioma por código; uno desconocido se acepta con valores genéricos."""
    key = (code or DEFAULT).strip().lower()
    if key in LANGUAGES:
        return LANGUAGES[key]
    return Language(key, key.title(), f"natural, modern {key.title()}", key[:2])


def is_spanish(code: str) -> bool:
    """Spanish, SpanishTE, spanish_latam... (los ayudantes específicos de español)."""
    return (code or "").strip().lower().startswith("spanish")


def labels() -> List[str]:
    return [l.label for l in LANGUAGES.values()]


def code_from_label(text: str) -> str:
    """Etiqueta del selector -> código; si no coincide, se usa lo escrito como código."""
    for lang in LANGUAGES.values():
        if lang.label == text:
            return lang.code
    return (text or DEFAULT).strip().lower() or DEFAULT


def label_for(code: str) -> str:
    lang = LANGUAGES.get((code or DEFAULT).lower())
    return lang.label if lang else (code or DEFAULT)
