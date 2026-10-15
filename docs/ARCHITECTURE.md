# Architecture

TraductorRenPy is a plain Python 3.9+ application (tkinter UI, no third-party runtime dependencies).
The translation unit is Ren'Py's own **`tl/<language>/` files**: the app lets the Ren'Py SDK generate them,
translates the pending entries, validates the results and writes them back.

## Pipeline

| Step (id) | Module | What it does |
|---|---|---|
| `analizar` | `detect.py` | Finds the `game` folder (even nested), classifies scripts (`.rpy`, `.rpyc`, inside `.rpa`). |
| `extraer` | `rpa.py`, `pipeline.collect_scripts` | Reads RPA-2/3 indexes with a restricted unpickler (no code execution) and extracts scripts only. |
| `decompilar` | `decompile.py` | Runs bundled [unrpyc](https://github.com/CensoredUsername/unrpyc) on the extracted copy. |
| `generar` | `sdk.py`, `pipeline.generate_tl` | `renpy.exe <project> translate <language>`; uses a rebuilt work project when scripts are not loose. |
| `extras` | `extras.py` | Finds texts Ren'Py does not extract (`renpy.input`, `text`, `textbutton`, notifications…) and adds them to `tl/<language>/zz_extra_strings.rpy` without duplicating any `old`. |
| `importar` | `importer.py` | Reads an earlier/other translation (even compiled or inside an `.rpa`) and matches it by block id and by exact English text. |
| `glosario` | `glossary.py` | Per-game glossary: character names, the game's title, fixed role translations (Spanish only). |
| `traducir` | `translate.py`, `engines/` | Batches with scene context → engine → cache. Never calls the engine for a text that is cached. |
| `validar` | `validate.py` | Tokens (`{..}`, `[..]`, `%s`, `\n`), quotes, newlines, empty output, tag repair. |
| `instalar` | `install.py` | Rewrites only the quoted text of the translated line; BOM + LF; backup; post-write verification that ids and comments are intact. |

`workflow.py` records which steps are done per game (`estado.json` in the work folder) and decides the next one.
`gui.py` is a thin layer: every action is a function in `pipeline.py` that also works without the UI.

## Key design decisions

- **Per-statement entries.** A `translate <lang> <id>:` block can hold several dialogues and non-dialogue
  statements (`voice ...`, `$ ...`). `pending.py` makes one entry per dialogue (`<id>`, `<id>#2`, …) and ignores
  the rest (`is_say`). Getting this wrong silently skips text, so it has dedicated tests.
- **Cache keyed by English text**, not by id: ids change between game versions, text rarely does. It also
  propagates a translation to every duplicate line for free.
- **Comments in column 0.** Some patches put the English comment at column 0 inside the block (`block_end`).
- **Validation is a hard gate.** A line that fails is left untranslated and reported; nothing broken is written.
- **Glossary is enforced at install time** for texts that are exactly a term (e.g. the game's title).
- **Per-game `init offset`.** `uitweaks.find_say_screen` honours `init offset = N` to find the `screen say` that
  really wins before generating a softened copy.
- **No game files in the repo / no keys in the repo.** Keys live in `%APPDATA%` encrypted with DPAPI
  (`keystore.py`); the work folder (`trabajo/`) is git-ignored.

## Engines

`engines/base.py` defines `Engine.translate(Batch) -> {id: text}`. `llm.py` implements Grok (OpenAI-compatible)
and Gemini; `microsoft.py` protects tokens with `notranslate` markup. All share `post_json` (retries, quota
handling, never prints keys). To add an engine: subclass `Engine`, register it in `engines/__init__.py`, add
`key_url`/`key_help`, and add the Spanish→English texts to `i18n_en.py` (a test fails if one is missing).

## Languages and UI

- Target languages: `languages.py` (`code` is the Ren'Py folder name). Spanish-only helpers (`looks_spanish`,
  fixed role names) are gated by `languages.is_spanish`.
- UI language: `i18n.py` + `i18n_en.py`. Source strings are Spanish and act as keys: `tr("…")`. Dynamic log lines
  are translated by patterns (`LOG_PATTERNS`). `tests/test_i18n.py` checks that every `tr(...)` literal in
  `gui.py` has an English version.

## Tests

`python -m unittest discover -s tests -t .` — pure unit tests plus local mock HTTP servers for the engines.
Nothing needs the network, a Ren'Py SDK or a real game. `examples/demo_game` is a harmless project for manual
end-to-end runs.

## Packaging

`build_exe.py` builds a Windows folder with PyInstaller (`--windowed`) and bundles `vendor/unrpyc`. Inside the
`.exe` there is no separate Python, so unrpyc is launched through the program itself (`main.py --unrpyc-run`).
