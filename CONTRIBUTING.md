# Contributing / Colaborar

Thanks for helping! / ¡Gracias por ayudar!

## Before you start

- Open an issue first for big changes, so we can agree on the approach.
- **Never** attach game files, extracted scripts, other people's translations or API keys to issues or pull
  requests. A few lines of the log and a made-up example are enough (the `examples/demo_game` is a good base).

## Development

```bash
python main.py                                   # run the app
python -m unittest discover -s tests -t .        # run the tests (no network, no Ren'Py needed)
```

- Python 3.9+ and the standard library only; please do not add runtime dependencies.
- Every user-facing text goes through `tr("…")` (Spanish is the source text). Add its English version to
  `traductor/i18n_en.py`; `tests/test_i18n.py` fails if one is missing.
- Add tests for what you change. Bugs found in real games should become a small synthetic test
  (see `tests/test_pending.py` for the `voice` line case).
- New target language: add it to `traductor/languages.py`. New engine: see `docs/ARCHITECTURE.md`.

## Pull requests

Keep them focused, describe what changed and how you checked it. Be kind: this is a hobby project.

## Reporting a bug

Use the *Bug report* template. Include the app version, Windows version, Ren'Py SDK version, the engine and
the relevant log lines.
