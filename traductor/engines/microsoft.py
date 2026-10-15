"""Microsoft Translator (Azure AI Translator, API v3).

Es traducción automática pura: no usa el contexto de escena. Los tokens de
Ren'Py y los términos del glosario se protegen con marcado HTML
(`notranslate` y `mstrans:dictionary`) y luego se limpia.
"""

import html
import re
from typing import Dict, List

from ..glossary import Term
from ..textutil import split_protected
from .base import Batch, Engine, post_json

_TAG_RE = re.compile(r"</?(?:span|mstrans:dictionary)\b[^>]*>")


def protect(text: str, glossary: List[Term]) -> str:
    """Texto -> HTML con tokens y términos del glosario protegidos."""
    pieces = []
    terms = sorted(glossary, key=lambda t: -len(t.src))
    pattern = (
        re.compile(
            r"(?<!\w)(" + "|".join(re.escape(t.src) for t in terms) + r")(?!\w)"
        )
        if terms
        else None
    )
    by_src = {t.src: t for t in terms}
    for is_token, seg in split_protected(text):
        if is_token:
            pieces.append(f'<span class="notranslate">{html.escape(seg, quote=False)}</span>')
            continue
        if pattern is None:
            pieces.append(html.escape(seg, quote=False))
            continue
        pos = 0
        for m in pattern.finditer(seg):
            pieces.append(html.escape(seg[pos : m.start()], quote=False))
            term = by_src[m.group(1)]
            if term.dst:
                pieces.append(
                    f'<mstrans:dictionary translation="{html.escape(term.dst, quote=True)}">'
                    f"{html.escape(term.src, quote=False)}</mstrans:dictionary>"
                )
            else:
                pieces.append(
                    f'<span class="notranslate">{html.escape(term.src, quote=False)}</span>'
                )
            pos = m.end()
        pieces.append(html.escape(seg[pos:], quote=False))
    return "".join(pieces)


def restore(translated: str) -> str:
    return html.unescape(_TAG_RE.sub("", translated))


class MicrosoftEngine(Engine):
    name = "microsoft"
    label = "Microsoft Translator"
    fields = ("api_key", "region", "base_url")
    defaults = {"base_url": "https://api.cognitive.microsofttranslator.com"}
    key_url = "https://portal.azure.com/#create/Microsoft.CognitiveServicesTextTranslation"
    key_help = (
        "1) Inicia sesión en Azure y crea un recurso Translator (hay nivel gratuito F0). "
        "2) En el recurso abre Keys and Endpoint. 3) Copia KEY 1 en Clave API y la Location/Región en Región."
    )

    def translate(self, batch: Batch) -> Dict[str, str]:
        headers = {"Ocp-Apim-Subscription-Key": self.cfg["api_key"]}
        if self.cfg.get("region"):
            headers["Ocp-Apim-Subscription-Region"] = self.cfg["region"]
        body = [{"Text": protect(i.text, batch.glossary)} for i in batch.items]
        data = post_json(
            self.cfg["base_url"].rstrip("/")
            + f"/translate?api-version=3.0&from=en&to={self.target.ms}&textType=html",
            headers,
            body,
        )
        out = {}
        for item, row in zip(batch.items, data if isinstance(data, list) else []):
            try:
                out[item.id] = restore(row["translations"][0]["text"])
            except (KeyError, IndexError, TypeError):
                continue
        return out
