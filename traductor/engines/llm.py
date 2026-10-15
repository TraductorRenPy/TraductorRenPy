"""Motores basados en modelos de lenguaje: Grok (xAI) y Gemini."""

import json
import re
from typing import Dict

from .base import BadResponse, Batch, Engine, EngineError, post_json

SYSTEM_PROMPT = """You are a professional video game localizer. You translate lines of a Ren'Py visual novel from English into @TARGET@.

Rules:
- Translate faithfully and naturally, keeping each speaker's tone and personality. The game may contain mature or explicit content: translate it faithfully, without censoring or softening it.
- Keep these tokens EXACTLY as they appear, untranslated and in a sensible position: Ren'Py tags like {i} {/i} {w} {p=0.5} {color=#fff}, interpolations like [name] or [player.name], format codes like %s %d %(x)s, and the escapes \\n, \\t and \\" (a backslash followed by a double quote is a literal quote and must stay as \\").
- Text inside tags such as {i}...{/i} must still be translated; only the tags stay.
- Glossary terms: when a term has a "translation", always use exactly that. When it has "keep": true, leave the term unchanged.
- "context_before" and "context_after" are neighbouring lines for reference only. Never translate or return them.
- Do not add, merge, split or omit lines. Do not add notes or explanations.

Input is a JSON object with "speakers" (optional), "glossary", "context_before", "items" and "context_after". Each item has "id", "speaker" (may be null for narration) and "text".
Reply with ONLY a JSON object: {"translations": [{"id": "<id>", "text": "<translated text>"}, ...]} with exactly one entry per item id."""


def system_prompt(target) -> str:
    """Prompt del sistema para el idioma destino (un `languages.Language`)."""
    return SYSTEM_PROMPT.replace("@TARGET@", target.prompt)


def build_user_message(batch: Batch) -> str:
    def lines(pairs):
        return [{"speaker": w, "text": t} for w, t in pairs]

    payload = {
        "glossary": [
            {"term": t.src, "translation": t.dst} if t.dst else {"term": t.src, "keep": True}
            for t in batch.glossary
        ],
        "context_before": lines(batch.before),
        "items": [{"id": i.id, "speaker": i.who, "text": i.text} for i in batch.items],
        "context_after": lines(batch.after),
    }
    return json.dumps(payload, ensure_ascii=False)


def parse_translations(raw: str) -> Dict[str, str]:
    """Extrae {id: texto} de la respuesta del modelo (JSON, con o sin ```)."""
    raw = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.S)
    if fence:
        raw = fence.group(1)
    try:
        data = json.loads(raw)
    except ValueError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise BadResponse("La respuesta del modelo no es JSON.")
        try:
            data = json.loads(raw[start : end + 1])
        except ValueError:
            raise BadResponse("La respuesta del modelo no es JSON.")
    if isinstance(data, dict):
        data = data.get("translations", [])
    if not isinstance(data, list):
        raise BadResponse("Formato de respuesta inesperado.")
    out = {}
    for row in data:
        if isinstance(row, dict) and "id" in row and isinstance(row.get("text"), str):
            out[str(row["id"])] = row["text"]
    return out


class GrokEngine(Engine):
    """API de xAI, compatible con OpenAI (`/chat/completions`)."""

    name = "grok"
    label = "Grok (xAI)"
    defaults = {"model": "grok-4", "base_url": "https://api.x.ai/v1"}
    key_url = "https://console.x.ai"
    key_help = (
        "1) Inicia sesión en console.x.ai. 2) En Billing agrega saldo (la API se paga "
        "aparte de la suscripción de Grok). 3) En API Keys pulsa Create y copia la clave (xai-…)."
    )

    def translate(self, batch: Batch) -> Dict[str, str]:
        payload = {
            "model": self.cfg["model"],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt(self.target)},
                {"role": "user", "content": build_user_message(batch)},
            ],
        }
        data = post_json(
            self.cfg["base_url"].rstrip("/") + "/chat/completions",
            {"Authorization": f"Bearer {self.cfg['api_key']}"},
            payload,
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise BadResponse("Respuesta de Grok sin contenido.")
        return parse_translations(content or "")


class GeminiEngine(Engine):
    name = "gemini"
    label = "Gemini (Google)"
    defaults = {
        "model": "gemini-3.1-flash-lite",  # gemini-2.5-flash ya no está para cuentas nuevas
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
    }
    min_interval = 4.6  # ~13 llamadas/min: bajo el límite gratuito de 15 RPM de los modelos lite
    key_url = "https://aistudio.google.com/apikey"
    key_help = (
        "1) Inicia sesión con tu cuenta de Google. 2) Pulsa Create API key (elige o crea un "
        "proyecto). 3) Copia la clave (AIza…). Tiene nivel gratuito con límites diarios."
    )
    _SAFETY = [
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    ]

    def translate(self, batch: Batch) -> Dict[str, str]:
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt(self.target)}]},
            "contents": [{"role": "user", "parts": [{"text": build_user_message(batch)}]}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
            "safetySettings": [
                {"category": c, "threshold": "BLOCK_NONE"} for c in self._SAFETY
            ],
        }
        self._throttle()
        data = post_json(
            f"{self.cfg['base_url'].rstrip('/')}/models/{self.cfg['model']}:generateContent",
            {"x-goog-api-key": self.cfg["api_key"]},  # cabecera, no en la URL
            payload,
        )
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "sin candidatos")
            raise BadResponse(f"Gemini no devolvió traducción ({reason}).")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return parse_translations("".join(p.get("text", "") for p in parts))
