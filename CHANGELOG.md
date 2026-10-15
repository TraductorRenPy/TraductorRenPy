# Changelog

## 1.0.0

First public release.

- One-button automatic mode, guide list with remembered progress, manual step-by-step buttons.
- Engines: Gemini, Grok (xAI), Microsoft Translator; per-game glossary; scene context; response splitting and
  retries; free-tier rate-limit handling; cache by English text.
- Extraction of scripts from `.rpa` (RPA-2/3), decompilation with bundled unrpyc, `tl` generation with the Ren'Py SDK.
- Detection of unmarked texts (`renpy.input`, screen `text`/`textbutton`, notifications…).
- Reuse of earlier translations and community patches (by id and by text), `q=` artifact cleanup.
- Validation (tokens, quotes, tags) with automatic tag repair; backups; post-write verification.
- 8 target languages and any other Ren'Py language name; English and Spanish interface.
- Optional dialogue-box tweaks in a separate file (including a softened copy of custom `screen say`).
- "Report a problem" (opens a pre-filled GitHub issue with a sanitized diagnostic you review first) and "Give feedback"
  buttons; they appear once the project URLs are set.
- API keys stored encrypted (Windows DPAPI). Automatic Ren'Py SDK detection. Windows `.exe` build script.
