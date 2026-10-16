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


REVIEW_PROMPT = """You are a senior video game localization editor. You review an EXISTING @TARGET@ translation of a Ren'Py visual novel. For each item you get the English original ("text") and the current translation ("current"), written by someone else, often with no context.

Fix ONLY real problems:
- wrong meaning: literal or word-for-word renderings, false friends, idioms and game/story jargon taken literally (for example "to pledge a fraternity" is to join it, not to "compromise" it);
- unnatural or ungrammatical phrasing, wrong register, wrong gender or number agreement, names or terms that do not follow the glossary, untranslated English left behind.
Keep the wording and style of the current translation whenever it is acceptable: do not rewrite for taste. If the current translation is fine, return it EXACTLY unchanged.

Rules:
- Use the scene ("context_before", "context_after", "speaker") to understand who speaks to whom and what is going on. Context lines are reference only: never return them.
- The game may contain mature or explicit content: keep its intensity, do not censor or soften it.
- Keep these tokens EXACTLY as they appear in the original, in a sensible position: Ren'Py tags like {i} {/i} {w} {p=0.5} {color=#fff}, interpolations like [name] or [player.name], format codes like %s %d %(x)s, and the escapes \\n, \\t and \\" (a backslash followed by a double quote is a literal quote and must stay as \\").
- Glossary terms: when a term has a "translation", always use exactly that. When it has "keep": true, leave the term unchanged.
- Do not add, merge, split or omit lines. Do not add notes or explanations.

Input is a JSON object with "glossary", "context_before", "items" and "context_after". Each item has "id", "speaker" (may be null for narration), "text" (English original) and "current" (existing translation).
Reply with ONLY a JSON object: {"translations": [{"id": "<id>", "text": "<final translation>"}, ...]} with exactly one entry per item id: the unchanged current translation or your corrected version."""

_NOTES_HEADER = (
    "\n\nNotes about this game, written by the person translating it. Use them for context, terminology and tone; "
    "they are not part of the text to translate:\n"
)


def _with_notes(prompt: str, notes: str) -> str:
    notes = (notes or "").strip()
    return prompt + _NOTES_HEADER + notes if notes else prompt


def system_prompt(target, notes: str = "") -> str:
    """Prompt del sistema para el idioma destino (un `languages.Language`), con las notas del juego si hay."""
    return _with_notes(SYSTEM_PROMPT.replace("@TARGET@", target.prompt), notes)


def review_system_prompt(target, notes: str = "") -> str:
    """Prompt para REVISAR una traducción ya existente (no traducir desde cero)."""
    return _with_notes(REVIEW_PROMPT.replace("@TARGET@", target.prompt), notes)


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


def build_review_message(batch: Batch) -> str:
    """Como build_user_message, pero cada item lleva también la traducción actual."""
    payload = json.loads(build_user_message(batch))
    payload["items"] = [
        {"id": i.id, "speaker": i.who, "text": i.text, "current": i.current} for i in batch.items
    ]
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


class LLMEngine(Engine):
    """Base de los motores de IA: traducir y revisar usan el mismo transporte con distinto prompt."""

    can_review = True

    def _complete(self, system: str, user: str) -> str:
        raise NotImplementedError

    def translate(self, batch: Batch) -> Dict[str, str]:
        return parse_translations(self._complete(system_prompt(self.target, self.notes), build_user_message(batch)))

    def review(self, batch: Batch) -> Dict[str, str]:
        return parse_translations(
            self._complete(review_system_prompt(self.target, self.notes), build_review_message(batch))
        )


class GrokEngine(LLMEngine):
    """API de xAI, compatible con OpenAI (`/chat/completions`)."""

    name = "grok"
    label = "Grok (xAI)"
    defaults = {"model": "grok-4", "base_url": "https://api.x.ai/v1"}
    key_url = "https://console.x.ai"
    key_help = (
        "1) Inicia sesión en console.x.ai. 2) En Billing agrega saldo (la API se paga "
        "aparte de la suscripción de Grok). 3) En API Keys pulsa Create y copia la clave (xai-…)."
    )

    def _complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.cfg["model"],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
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
        return content or ""


class GeminiEngine(LLMEngine):
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

    def _complete(self, system: str, user: str) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
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
        return "".join(p.get("text", "") for p in parts)
