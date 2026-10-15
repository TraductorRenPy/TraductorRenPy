# Changelog

## 1.0.6

- The translation credit is no longer optional: **"Translated with TraductorRenPy"** (in the translation's language)
  and the project page address are always added at the end of the game's "About" screen. It is skipped only when the
  game has no "About" screen or it is not translated yet. Installing again never repeats it.
- Ren'Py language names are case-sensitive ("Spanish" is not "spanish"). If the game already has the language you
  typed with another capitalization (e.g. a community translation in `tl/Spanish`), the app now uses that exact
  name and says so in the log, instead of creating a parallel language the game never shows.

## 1.0.5

- **Font check** when installing (and a "Game fonts..." button): detects game fonts that do not draw the target
  language's letters (missing glyphs or empty ones, e.g. n-tilde and the opening question mark) and, with your
  permission, writes `zz_fuentes_<language>.rpy` to use another font only with that language. Pure Python reader,
  no extra dependencies.
- Games that already have a translation: the glossary no longer overwrites names that the other translation
  adapted. Only the game title is forced on entries that were already translated.
- Updated Help and tutorials (letters that do not show, games with an existing translation, language names are
  case-sensitive in Ren'Py).

## 1.0.4

- New button **"Retry the lines that failed validation"**: it saves a copy of the cache, removes those lines and
  translates them again with the chosen engine (they used to stay in the cache and were never retried).
- Updated in-app **Help** (what to do when it stops, playing while you translate, advanced settings, adult content,
  undo, the Windows warning) with a button that opens the full tutorial.
- Full **tutorials** as plain text inside the zip: `TUTORIAL.txt` (Spanish) and `TUTORIAL_EN.txt` (English).

## 1.0.3

- Validation now restores the `\n` line breaks at the start or end of a text when the model drops them
  (they were the most common reason for lines being left untranslated). Interior breaks and lost tags are still
  rejected, never guessed.

## 1.0.2

- Plain-text instructions inside the zip (`LEEME.txt` / `READ_ME_FIRST.txt`), including what to do when Windows
  shows "Windows protected your PC". Releases now get a description with the same warning.
- Optional **translation credit**: a line added at the end of the game's "About" screen (empty by default).
- **Notification** (sound, taskbar flash and a window) when a long job finishes or stops.
  Expected errors such as an exhausted daily quota now show a clear message instead of a technical trace.
- Remaining-time estimate uses the **recent pace** instead of the overall average.
- **Simultaneous requests** (advanced, for paid accounts): several batches at once, with a shared pause when the
  service asks to wait. Default 1 (unchanged behavior).
- Sharper icon at small sizes (every edge aligned to the pixel grid) and a 1024 px logo.

## 1.0.1

- Changing the interface language now offers to restart the application by itself (it waits if a job is running).
- New window and `.exe` icon (a white "T" on a blue tile with a text strip, with sizes for every screen scale).
  The window no longer shows the default Tk feather.
- "Support the project" now opens the donation form directly instead of the full Ko-fi page.
- "Give feedback" button, linked to the repository Discussions.

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
