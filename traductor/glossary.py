"""Paso 7: glosario por juego.

Cada término es `Origen` (no se traduce) o `Origen = Traducción` (se traduce
siempre así). Se edita como texto, una línea por término.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from . import languages

RE_CHARACTER = re.compile(
    r"""^\s*(?:define|default)\s+(\w+)\s*=\s*(?:\w+\.)*Character\(\s*_?\(?\s*(["'])(.*?)\2"""
)


@dataclass(frozen=True)
class Term:
    src: str
    dst: str = ""  # vacío = no traducir (se deja igual)

    @property
    def target(self) -> str:
        return self.dst or self.src


class Glossary:
    def __init__(self, terms: Iterable[Term] = ()):
        self.terms: List[Term] = list(terms)

    # --- persistencia ---------------------------------------------------

    @classmethod
    def load(cls, path) -> "Glossary":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls(Term(t["src"], t.get("dst", "")) for t in data.get("terms", []))
        except (OSError, ValueError, KeyError, TypeError):
            return cls()

    def save(self, path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {"terms": [{"src": t.src, "dst": t.dst} for t in self.terms]}
        Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    # --- edición como texto -----------------------------------------------

    @classmethod
    def from_text(cls, text: str) -> "Glossary":
        seen, terms = set(), []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            src, _, dst = line.partition("=")
            src, dst = src.strip(), dst.strip()
            if src and src not in seen:
                seen.add(src)
                terms.append(Term(src, dst))
        return cls(terms)

    def to_text(self) -> str:
        return "\n".join(f"{t.src} = {t.dst}" if t.dst else t.src for t in self.terms)

    def add_missing(self, terms: Iterable[Term]) -> int:
        have = {t.src for t in self.terms}
        added = 0
        for t in terms:
            if t.src not in have:
                self.terms.append(t)
                have.add(t.src)
                added += 1
        return added

    # --- uso en la traducción -------------------------------------------------

    def relevant(self, texts: Iterable[str]) -> List[Term]:
        """Términos que aparecen (como palabra completa) en alguno de los textos."""
        joined = "\n".join(texts)
        return [
            t for t in self.terms
            if re.search(r"(?<!\w)" + re.escape(t.src) + r"(?!\w)", joined)
        ]


def find_characters(dirs: Iterable[Path]) -> Dict[str, str]:
    """{variable: nombre} de las definiciones `define c = Character("Nombre")`
    en los .rpy de `dirs` (se ignoran las carpetas tl)."""
    found: Dict[str, str] = {}
    for base in dirs:
        base = Path(base)
        if not base.is_dir():
            continue
        for path in base.rglob("*.rpy"):
            if "tl" in path.relative_to(base).parts[:-1]:
                continue
            try:
                text = path.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                m = RE_CHARACTER.match(line)
                if m and m.group(3).strip():
                    found.setdefault(m.group(1), m.group(3).strip())
    return found


# Palabras corrientes del inglés que indican un "nombre" que en realidad es una
# descripción (Pizza Guy, Unknown Man, First Child) o un pronombre (Him).
COMMON_WORDS = frozenset(
    "man men woman women guy guys girl girls boy boys child children kid kids narrator therapist "
    "him her he she they them it stranger unknown someone everyone everybody voice boss mom mommy "
    "mother dad daddy father doctor nurse teacher waiter waitress officer cop driver clerk cashier "
    "customer customers neighbor neighbors friend friends first second third fourth all both crowd "
    "guard guards student students the a an and of or with unnamed anonymous caller male female "
    "old young little big new delivery taxi cab bartender barista".split()
)

# Traducciones fijas y sin ambigüedad de género/contexto.
ROLE_TRANSLATIONS = {
    "narrator": "Narrador",
    "unknown man": "Hombre desconocido",
    "therapist": "Terapeuta",
    "pizza guy": "Repartidor de pizza",
    "stranger": "Desconocido",
    "mom": "Mamá",
    "dad": "Papá",
}


def is_common_name(name: str) -> bool:
    """True si el nombre parece una descripción (alguna palabra corriente)."""
    words = re.findall(r"[A-Za-z]+(?:'[a-z]+)?", name)
    return any(w.lower().removesuffix("'s") in COMMON_WORDS for w in words)


RE_TITLE = re.compile(
    r"""^\s*(?:define|default)\s+config\.(?:name|window_title)\s*=\s*_?\(?\s*(["'])(.*?)\1"""
)


def find_game_titles(dirs: Iterable[Path]) -> List[str]:
    """Títulos del juego (`define config.name = _("...")`): no se traducen."""
    titles: List[str] = []
    for base in dirs:
        base = Path(base)
        if not base.is_dir():
            continue
        for path in base.rglob("*.rpy"):
            if "tl" in path.relative_to(base).parts[:-1]:
                continue
            try:
                lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                m = RE_TITLE.match(line)
                if m and m.group(2).strip() and m.group(2) not in titles:
                    titles.append(m.group(2))
    return titles


def suggest_terms(characters: Dict[str, str], language: str = "spanish") -> List[Term]:
    """Términos de glosario a partir de los nombres de personaje.

    Los nombres propios no se traducen. Las descripciones (Pizza Guy, Him,
    First Child) se dejan fuera para que el motor las traduzca con contexto,
    salvo, en español, las que tienen una traducción fija clara
    (Narrator -> Narrador).
    """
    seen, terms = set(), []
    for name in characters.values():
        if name in seen or not re.search(r"[^\W\d_]", name) or "[" in name:
            continue
        seen.add(name)
        if is_common_name(name):
            fixed = ROLE_TRANSLATIONS.get(name.lower()) if languages.is_spanish(language) else None
            if fixed:
                terms.append(Term(name, fixed))
            continue
        terms.append(Term(name))
    return terms
