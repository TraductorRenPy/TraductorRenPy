# Changelog

## 1.1.4

- **License**: from this version the program is free to use but all rights are reserved, and the source code is no
  longer published. This repository now holds only the downloads (Releases), the documentation, issues and
  discussions. Versions 1.0.0 to 1.1.3 were published under the MIT License and stay under it for anyone who
  already has them. There are no functional changes.

## 1.1.3

- **Fix**: the translation credit was not added to games whose "About" text is empty (the Ren'Py template leaves
  `gui.about` blank and the screen only shows "Made with Ren'Py"). On install the app now creates
  `game/zz_credit.rpy`, which sets the credit only when that text is empty. Delete the file to remove it.

## 1.1.2

- **Fix**: texts with several paragraphs shown through `[variable]` (e.g. the history list of a character sheet) stayed
  in English. Ren'Py draws each paragraph as a separate fragment, so the stored whole-block translation never matched.
  On install the app now also writes one entry per paragraph (`zz_dynamic_strings.rpy`), reusing the translation
  already made (no extra API cost). If the translation has a different number of paragraphs than the original, it is
  not guessed.

## 1.1.1

- **Fix**: the app's own `zz_*` files could keep the language name with the wrong capitalization (`spanish` instead of
  `Spanish`) from an earlier run, and installing again copied them over the game, so the extra translations (phone
  messages, character sheets...) went to a language the game never shows. Extras and install now rewrite the language
  name in those `zz_*` files to the exact name before copying. Other people's translation files are never touched.

## 1.1.0

- **Fix (data loss)**: the app launched the Ren'Py SDK against the game with the game's own save folder
  (`%APPDATA%/RenPy/<save_directory>`). With games made with an old Ren'Py (Python 2, e.g. 7.x) the SDK (Python 3)
  rewrote the persistent data (preferences, gallery, seen text) in a format the game cannot read, so the game lost
  them. The SDK now runs with an isolated save folder inside the work folder and never touches the game's data.
  Saved games (`.save`) were never affected.

- "Improve existing translation" now honors the **Simultaneous requests** setting (it ran one batch at a time
  before, ignoring it). Same safeguards as translating: a fatal error or repeated failures stop the job, Cancel only
  waits for batches already sent, and everything reviewed is saved.
- **Faster, cheaper review**: the AI now returns only the lines it corrects (short answers), so each request carries
  twice the lines per batch (up to 100). Lines it does not list count as correct and are remembered. On a 40,000-line
  game this goes from about 1,020 requests to about 370.
- Phrases of one or two words are skipped by default (they almost never have errors); a checkbox includes them.

## 1.0.9

- **Improve existing translation** (new button): asks Gemini or Grok to review every line of an already translated
  game (e.g. a community translation made without context) with its scene, the glossary and the game notes, and to
  fix only real errors. Reviewed lines are cached (`revision.json`, resumable), a readable report is written
  (`revision.txt`) and nothing touches the game until you press "Apply corrections" (backup + verification).
- **Game notes** (new button): per-game context (setting, vocabulary, tone) that is also used when translating.
- Texts that a game shows through `"[variable]"` (character sheet descriptions, histories...) were never translated:
  Ren'Py translates the screen's text, not the variable's content. On install the app now creates
  `game/zz_dynamic_text.rpy` (a `config.replace_text` hook that translates each text fragment right before drawing
  it) and `tl/<language>/zz_dynamic_strings.rpy` (the same translations without the edge line breaks, which the hook
  could not match). No extra API cost. Tested in Ren'Py: `[variable]` texts now show translated.

## 1.0.8

- **Update notice**: on start the app asks GitHub for the latest Release and, if it is newer, shows a notice with a
  "Download" button (it only opens the page; it installs nothing). It can be turned off ("Check for updates on
  start") and there is a "Check for updates" button in "About". Failures are silent; nothing about you or your games
  is sent (the request does reveal your IP to GitHub, like any web visit).

## 1.0.7

- The translation-language field now says it can be typed, and shows the exact language name when the app finds
  the game already has it with another capitalization (e.g. `Spanish`).
- New **"Start over..."** button: clear only the window, restart a game's list (keeps the cache) or delete a game's
  whole work folder (with confirmation). Clearing the game folder now also empties the summary and tables, which
  used to keep showing the previous game.

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
