"""Paso 8: validar una traducción antes de escribirla en el tl.

Una línea es válida si conserva los tokens del original ({..} [..] %s \\n ...),
no rompe la sintaxis del script (comillas sin escapar, saltos de línea reales,
barra final) y no está vacía. Un fallo típico y reparable es que el modelo
escriba `{i}` donde iba `{/i}`: se corrige copiando el tag del original.
"""

from collections import Counter
from typing import List, Optional, Tuple

from .textutil import TOKEN_RE, tokens


def has_unescaped_quote(text: str) -> bool:
    i = 0
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return True
        i += 1
    return False


def check(original: str, translated: str) -> List[str]:
    """Motivos por los que `translated` no es válida (lista vacía = válida)."""
    reasons: List[str] = []
    if not translated.strip():
        return ["traducción vacía"]
    if "\n" in translated or "\r" in translated:
        reasons.append("contiene un salto de línea real")
    if has_unescaped_quote(translated):
        reasons.append('tiene comillas sin escapar (\\")')
    trailing = len(translated) - len(translated.rstrip("\\"))
    if trailing % 2:
        reasons.append("termina en una barra invertida suelta")

    # Las comillas escapadas \" son puntuación, no un token a conservar: el
    # español puede usar comillas donde el inglés usaba ' ' (ya se exige que
    # estén escapadas). El resto de tokens debe coincidir exactamente.
    def significant(text):
        return Counter(t for t in tokens(text) if t != '\\"')

    want, got = significant(original), significant(translated)
    if want != got:
        missing = sorted((want - got).elements())
        extra = sorted((got - want).elements())
        reasons.append(f"tokens distintos (faltan {missing or '-'}, sobran {extra or '-'})")
    for ch in "[]{}%":
        if original.count(ch) != translated.count(ch):
            reasons.append(f"cambió el número de «{ch}»")
            break
    return reasons


def repair_tags(original: str, translated: str) -> Optional[str]:
    """Si solo difieren tags `{..}` en la misma posición, los copia del original."""
    o = [m.group(0) for m in TOKEN_RE.finditer(original)]
    t = list(TOKEN_RE.finditer(translated))
    if len(o) != len(t):
        return None
    out, pos = [], 0
    for want, m in zip(o, t):
        have = m.group(0)
        out.append(translated[pos : m.start()])
        if have != want:
            if not (have.startswith("{") and want.startswith("{")):
                return None  # difiere algo que no es un tag: no se arriesga
            have = want
        out.append(have)
        pos = m.end()
    out.append(translated[pos:])
    return "".join(out)


def strip_artifacts(original: str, translated: str) -> str:
    """Quita el `q=` que algunos traductores automáticos dejan al inicio
    (viene del parámetro `q=` de la API de Google Translate)."""
    if translated.startswith("q=") and not original.startswith("q="):
        return translated[2:]
    return translated


def validate(original: str, translated: str) -> Tuple[Optional[str], List[str], bool]:
    """(texto final o None, motivos del fallo, ¿se reparó?)."""
    cleaned = strip_artifacts(original, translated)
    artifact = cleaned != translated
    reasons = check(original, cleaned)
    if not reasons:
        return cleaned, [], artifact
    fixed = repair_tags(original, cleaned)
    if fixed is not None and not check(original, fixed):
        return fixed, [], True
    return None, reasons, False
