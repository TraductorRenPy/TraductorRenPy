# Third-party software / Software de terceros

## unrpyc (included in `vendor/unrpyc/`)

- Purpose: decompiles `.rpyc` files to `.rpy` (step "Decompile").
- Project: <https://github.com/CensoredUsername/unrpyc>
- License: MIT — Copyright (c) 2012-2024 Yuri K. Schlesner, CensoredUsername, Jackmcbarn.
  The full license text is in [`vendor/unrpyc/LICENSE`](vendor/unrpyc/LICENSE) and must stay with the code.
- Only the files needed at run time are included (the upstream `testcases/` folder, which contains
  Ren'Py sample games, was removed). Files are otherwise unmodified.

## Ren'Py SDK (NOT included)

TraductorRenPy runs the Ren'Py SDK (`renpy.exe ... translate <language>`) that the user installs
separately from <https://www.renpy.org/>. Ren'Py is licensed by its authors (MIT and LGPL parts);
this project neither includes nor redistributes it.

## Python and Tk

The Windows `.exe` is built with PyInstaller and bundles the Python runtime and Tk, which are
distributed under the Python Software Foundation License and the Tcl/Tk license.

## Translation services

Gemini (Google), Grok (xAI) and Microsoft Translator are third-party services used with the **user's own
API key** and subject to their own terms. No keys are included in this project.
