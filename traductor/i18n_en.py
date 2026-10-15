"""Traducciones al inglés (clave = texto original en español).

LOG_PATTERNS sirve para los mensajes del registro con datos variables: el
primer elemento usa {marcadores} que se copian al texto en inglés.
"""

EN = {
    # --- ventana: configuración ---
    "Configuración": "Settings",
    "Carpeta del juego": "Game folder",
    "Ren'Py SDK (carpeta o renpy.exe)": "Ren'Py SDK (folder or renpy.exe)",
    "unrpyc.py (opcional: ya viene incluido)": "unrpyc.py (optional: already included)",
    "Carpeta de trabajo": "Work folder",
    "Examinar…": "Browse…",
    "Buscar SDK": "Find SDK",
    "Idioma de la traducción": "Translation language",
    "Idioma de la interfaz": "Interface language",
    "Motor de traducción (uno por trabajo; cada persona usa su propia clave, guardada cifrada en este equipo)":
        "Translation engine (one per job; everyone uses their own key, stored encrypted on this computer)",
    "Motor": "Engine",
    "Clave API": "API key",
    "Conseguir clave…": "Get key…",
    "Modelo": "Model",
    "Región": "Region",
    "URL base": "Base URL",
    "Líneas por lote": "Lines per batch",
    "Carpeta del Ren'Py SDK": "Ren'Py SDK folder",
    "Todos": "All",
    "Ren'Py SDK": "Ren'Py SDK",
    "Ren'Py SDK encontrado: {path}": "Ren'Py SDK found: {path}",
    "No encontré el Ren'Py SDK en este equipo.\n\nEs gratis y se descarga de renpy.org. ¿Abrir la página de descarga?":
        "I could not find the Ren'Py SDK on this computer.\n\nIt is free and can be downloaded from renpy.org. Open the download page?",
    # --- ventana: guía y botones ---
    "Qué hacer ahora": "What to do now",
    "▶  Traducir este juego automáticamente": "▶  Translate this game automatically",
    "Hacer el siguiente paso": "Do the next step",
    "Hacer el siguiente paso: {title}": "Do the next step: {title}",
    "Todo listo": "All done",
    "Todo listo: abre el juego, debe iniciar en el idioma elegido.":
        "All done: open the game, it should start in the chosen language.",
    "Elige la carpeta del juego para empezar.": "Choose the game folder to start.",
    "(opcional)": "(optional)",
    "Ayuda": "Help",
    "Acerca de": "About",
    "Cancelar": "Cancel",
    "Cerrar": "Close",
    "♥ Apoyar el proyecto": "♥ Support the project",
    "Página del proyecto": "Project page",
    "Reportar un problema": "Report a problem",
    "Dar opinión": "Give feedback",
    "Describe qué pasó (opcional):": "Describe what happened (optional):",
    "Esto se publicará tal cual en GitHub. Se quitaron rutas, correos y claves; revísalo antes de enviar:":
        "This will be posted as-is on GitHub. Paths, e-mails and keys were removed; review it before sending:",
    "Abrir en GitHub": "Open on GitHub",
    "Copiar": "Copy",
    "Paso a paso (manual)": "Step by step (manual)",
    "Ver pendientes": "View pending",
    "Caja de diálogo…": "Dialogue box…",
    "Juego detectado": "Detected game",
    "Pendientes por archivo (tl)": "Pending by file (tl)",
    "Traducciones": "Translations",
    "Habla": "Speaker",
    "Original": "Original",
    "Traducción": "Translation",
    "Archivo": "File",
    "Entradas": "Entries",
    "Pendientes": "Pending",
    "Sin texto / ya traducido": "No text / already translated",
    "Traduce juegos hechos con Ren'Py a otros idiomas.": "Translates games made with Ren'Py into other languages.",
    "Licencia {name}. Software libre.": "{name} license. Free software.",
    "unrpyc (MIT) viene incluido. Ren'Py es de sus autores.":
        "unrpyc (MIT) is included. Ren'Py belongs to its authors.",
    "Completado: {done}/{total} en {time}": "Completed: {done}/{total} in {time}",
    "{done}/{total} · transcurrido {elapsed} · restante ~{remaining}":
        "{done}/{total} · elapsed {elapsed} · remaining ~{remaining}",
    "0/{total} · calculando…": "0/{total} · calculating…",
    "Cancelado por el usuario.": "Cancelled by the user.",
    # --- títulos de las tareas (registro) ---
    "Traducir este juego (automático)": "Translate this game (automatic)",
    "Siguiente paso": "Next step",
    "Revisar el juego": "Review the game",
    "Extraer los scripts": "Extract the scripts",
    "Decompilar con unrpyc": "Decompile with unrpyc",
    "Crear la lista de textos con el SDK": "Create the text list with the SDK",
    "Buscar textos sin marcar": "Find unmarked texts",
    "Usar traducción anterior": "Use earlier translation",
    "Traducir lo que falta": "Translate what is missing",
    "Revisar las traducciones (sin escribir)": "Review the translations (without writing)",
    "Instalar en el juego": "Install into the game",
    "Ver pendientes": "View pending",
    # --- pasos de la guía (workflow) ---
    "Decompilar": "Decompile",
    "Crear la lista de textos": "Create the text list",
    "Usar una traducción anterior": "Use an earlier translation",
    "Glosario de nombres": "Names glossary",
    "Revisar las traducciones": "Review the translations",
    "Detecta la carpeta del juego y cómo están guardados sus textos.":
        "Finds the game folder and how its texts are stored.",
    "Saca los textos de los archivos .rpa/.rpyc a una carpeta aparte, sin tocar el juego.":
        "Takes the texts out of the .rpa/.rpyc files into a separate folder, without touching the game.",
    "Convierte esos scripts a texto legible (con unrpyc).": "Converts those scripts to readable text (with unrpyc).",
    "Ren'Py prepara el archivo de traducción con todas las líneas del juego.":
        "Ren'Py prepares the translation file with every line of the game.",
    "Encuentra botones, avisos y mensajes que el juego no marcó para traducir.":
        "Finds buttons, notices and messages that the game did not mark for translation.",
    "Aprovecha la traducción de otra versión del juego para traducir solo lo nuevo.":
        "Reuses the translation of another version of the game so only what is new gets translated.",
    "Nombres de personajes que no se traducen. Se crea solo.":
        "Character names that are not translated. It is created automatically.",
    "Usa tu motor (Gemini, Grok…). Es el único paso que gasta tu cuota de API.":
        "Uses your engine (Gemini, Grok…). It is the only step that spends your API quota.",
    "Comprueba etiquetas, variables y comillas. No escribe nada todavía.":
        "Checks tags, variables and quotes. It does not write anything yet.",
    "Escribe la traducción en el juego, con respaldo, y lo deja en el idioma elegido.":
        "Writes the translation into the game, with a backup, and sets it to the chosen language.",
    # --- diálogos del modo automático ---
    "Traducción anterior": "Earlier translation",
    "¿Tienes una versión anterior de este juego ya traducida, o un parche de traducción? La app la aprovecha y traduce solo lo que falte.\n\nSi no tienes ninguna, elige «No».":
        "Do you have an earlier version of this game that is already translated, or a translation patch? The app reuses it and translates only what is missing.\n\nIf you have none, choose “No”.",
    "Carpeta del juego o parche con la traducción previa": "Game or patch folder with the earlier translation",
    "Sin traducción anterior: se traduce todo con el motor.": "No earlier translation: everything is translated with the engine.",
    "Falta la clave": "Missing key",
    "Para traducir hace falta la clave de tu motor de traducción.\n\nPulsa «Conseguir clave…», pégala en «Clave API» y vuelve a empezar: la app sigue donde se quedó.":
        "A key for your translation engine is needed to translate.\n\nPress “Get key…”, paste it into “API key” and start again: the app continues where it left off.",
    "Detenido: falta la clave API. Pégala y pulsa de nuevo el botón.": "Stopped: the API key is missing. Paste it and press the button again.",
    "No hay textos nuevos por traducir.": "There are no new texts to translate.",
    "Traducir con {label}": "Translate with {label}",
    "Faltan {n} textos por traducir con {label}.\nEsto usa tu cuota o saldo de la API (con Gemini gratis es sin costo, dentro de sus límites).\n\n¿Continuar?":
        "{n} texts are left to translate with {label}.\nThis uses your API quota or balance (with Gemini's free tier it costs nothing, within its limits).\n\nContinue?",
    "Detenido antes de traducir. Cuando quieras, vuelve a pulsar el botón.": "Stopped before translating. Press the button again whenever you want.",
    "Instalar la traducción": "Install the translation",
    "Se escribirán {n} traducciones en el juego.\n": "{n} translations will be written into the game.\n",
    "{n} líneas no pasaron la validación y quedarán sin traducir.\n": "{n} lines did not pass validation and will stay untranslated.\n",
    "\nSe guarda un respaldo antes de escribir (carpeta «respaldos»).\n\n¿Instalar ahora?":
        "\nA backup is saved before writing (“respaldos” folder).\n\nInstall now?",
    "Instalación cancelada. Pulsa de nuevo cuando quieras instalarla.": "Installation cancelled. Press again whenever you want to install it.",
    "No queda nada por hacer en este juego.": "There is nothing left to do for this game.",
    "Listo. Abre el juego: debe iniciar en {lang}.": "Done. Open the game: it should start in {lang}.",
    # --- claves de API ---
    "=== Cómo conseguir la clave de {name} ===": "=== How to get the {name} key ===",
    "Pega la clave en «Clave API». Nunca la compartas ni la subas a git.":
        "Paste the key into “API key”. Never share it or upload it to git.",
    "1) Inicia sesión en console.x.ai. 2) En Billing agrega saldo (la API se paga aparte de la suscripción de Grok). 3) En API Keys pulsa Create y copia la clave (xai-…).":
        "1) Sign in at console.x.ai. 2) Under Billing add credit (the API is billed separately from the Grok subscription). 3) Under API Keys press Create and copy the key (xai-…).",
    "1) Inicia sesión con tu cuenta de Google. 2) Pulsa Create API key (elige o crea un proyecto). 3) Copia la clave (AIza…). Tiene nivel gratuito con límites diarios.":
        "1) Sign in with your Google account. 2) Press Create API key (choose or create a project). 3) Copy the key (AIza…). It has a free tier with daily limits.",
    "1) Inicia sesión en Azure y crea un recurso Translator (hay nivel gratuito F0). 2) En el recurso abre Keys and Endpoint. 3) Copia KEY 1 en Clave API y la Location/Región en Región.":
        "1) Sign in to Azure and create a Translator resource (there is a free F0 tier). 2) Open Keys and Endpoint in the resource. 3) Copy KEY 1 into API key and the Location/Region into Region.",
    # --- caja de diálogo / glosario ---
    "Original del juego": "Game's original",
    "Contorno discreto (conserva el diseño del juego)": "Discreet outline (keeps the game's design)",
    "Compacta (barra oscura más baja)": "Compact (lower dark bar)",
    "Solo texto (sin barra)": "Text only (no bar)",
    "Caja de diálogo": "Dialogue box",
    "Cambia solo el aspecto de la caja de texto, en el archivo\ngame/{file}. Los scripts del juego no se tocan.":
        "Changes only the look of the text box, in the file\ngame/{file}. The game's scripts are not touched.",
    "Aplicar": "Apply",
    "Caja de diálogo: {mode}. Reinicia el juego para verlo.": "Dialogue box: {mode}. Restart the game to see it.",
    "Glosario": "Glossary",
    "Una línea por término. «Nombre» = no se traduce; «Uncle = Tío» = se traduce siempre así.\nSi lo dejas vacío, la app lo crea sola al traducir.":
        "One line per term. “Name” = not translated; “Uncle = Tío” = always translated that way.\nIf you leave it empty, the app creates it by itself when translating.",
    "Sugerir personajes": "Suggest characters",
    "Guardar": "Save",
    "Glosario: {n} nombres sugeridos automáticamente.": "Glossary: {n} names suggested automatically.",
    # --- errores frecuentes ---
    "Elige la carpeta del juego.": "Choose the game folder.",
    "No se encontró una carpeta `game` con scripts o .rpa dentro de esa ruta.":
        "No `game` folder with scripts or .rpa files was found inside that path.",
    "Falta la carpeta del Ren'Py SDK. Pulsa «Buscar SDK» o indícala arriba (la carpeta donde está renpy.exe).":
        "The Ren'Py SDK folder is missing. Press “Find SDK” or set it above (the folder where renpy.exe is).",
    "No se encontró renpy.exe en la ruta del SDK configurada.": "renpy.exe was not found in the configured SDK path.",
    "El SDK terminó con errores (ver registro).": "The SDK finished with errors (see log).",
    "No hay traducciones todavía (paso 6 o Importar previa).": "There are no translations yet (translate step or Use earlier translation).",
    "Primero extrae los scripts (paso 2).": "Extract the scripts first (step 2).",
    "No hay .rpyc pendientes de decompilar.": "There are no .rpyc files left to decompile.",
    "No hay scripts que extraer: todo está como .rpy.": "There are no scripts to extract: everything is already .rpy.",
    "La respuesta del modelo no es JSON.": "The model's response is not JSON.",
    "La respuesta no es JSON válido.": "The response is not valid JSON.",
    "Formato de respuesta inesperado.": "Unexpected response format.",
    "Se agotó la cuota diaria del servicio. Vuelve a pulsar Traducir mañana: lo ya traducido está en la caché.":
        "The service's daily quota is used up. Press Translate again tomorrow: what is already translated is in the cache.",
    "Idiomas en tl/: ninguno": "Languages in tl/: none",
    "Resultado: todos los scripts están como .rpy; se puede generar tl directo.":
        "Result: every script is already .rpy; the tl can be generated directly.",
    "Resultado: hace falta extraer de .rpa y decompilar con unrpyc.": "Result: the .rpa files must be extracted and decompiled with unrpyc.",
    "Resultado: hace falta decompilar con unrpyc.": "Result: decompiling with unrpyc is needed.",
    "Sin respuesta útil para una línea": "No useful response for one line",
}

LOG_PATTERNS = [
    # análisis del juego
    ("Proyecto: {path}", "Project: {path}"),
    (".rpy sueltos: {n}", "Loose .rpy files: {n}"),
    (".rpyc sin .rpy: {n}", ".rpyc without .rpy: {n}"),
    (".rpa {name}: ilegible ({err})", ".rpa {name}: unreadable ({err})"),
    (".rpa {name} ({version}, {size} MB): {n} scripts de {total} archivos",
     ".rpa {name} ({version}, {size} MB): {n} scripts out of {total} files"),
    ("Scripts solo dentro de .rpa: {n}", "Scripts only inside .rpa: {n}"),
    ("Idiomas en tl/: {langs}", "Languages in tl/: {langs}"),
    ("{total} entradas: {a} traducidas, {b} pendientes, {c} ya en español, {d} sin texto traducible (nombres, '...', variables)",
     "{total} entries: {a} translated, {b} pending, {c} already in Spanish, {d} without translatable text (names, '...', variables)"),
    ("Lista de pendientes en {path}", "Pending list in {path}"),
    # extraer / decompilar
    ("Copiados {n} .rpyc sueltos.", "Copied {n} loose .rpyc files."),
    ("Extrayendo scripts de {name} ...", "Extracting scripts from {name} ..."),
    ("{n} scripts extraídos.", "{n} scripts extracted."),
    ("Scripts en {path}", "Scripts in {path}"),
    ("Decompilando {n} archivos con {path} ...", "Decompiling {n} files with {path} ..."),
    ("Decompilados: {ok}. Fallidos: {bad}.", "Decompiled: {ok}. Failed: {bad}."),
    ("FALLÓ {name}", "FAILED {name}"),
    ("Aviso: {n} archivos parecen de Ren'Py 7 o anterior; unrpyc apunta a Ren'Py 8. Es solo una advertencia, se revisa el resultado abajo.",
     "Notice: {n} files look like Ren'Py 7 or earlier; unrpyc targets Ren'Py 8. This is only a warning, the result is checked below."),
    ("Aviso: {n} nombres inseguros ignorados en {name}", "Notice: {n} unsafe names ignored in {name}"),
    ("Duplicado en otro .rpa, se omite: {name}", "Duplicate in another .rpa, skipped: {name}"),
    ("{n} archivos no se pudieron decompilar.", "{n} files could not be decompiled."),
    # generar tl
    ("Respaldo de {src} en {dest}", "Backup of {src} in {dest}"),
    ("Respaldo: {dest}", "Backup: {dest}"),
    ("Se partió del tl/{lang} existente del juego.", "Started from the game's existing tl/{lang}."),
    ("Proyecto de trabajo: {path} ({n} scripts)", "Work project: {path} ({n} scripts)"),
    ("tl/{lang}: {a} -> {b} entradas ({d}).", "tl/{lang}: {a} -> {b} entries ({d})."),
    ("Aviso: {n} scripts sin .rpy (sin decompilar), no entran al proyecto:",
     "Notice: {n} scripts without .rpy (not decompiled), they are not part of the project:"),
    ("El SDK terminó con errores (ver registro).", "The SDK finished with errors (see log)."),
    ("renpy terminó con código {n}.", "renpy finished with code {n}."),
    ("El SDK no generó entradas en {path}. Revisa que los scripts sean válidos.",
     "The SDK generated no entries in {path}. Check that the scripts are valid."),
    ("No existe {path}. Primero genera la traducción (paso 4).", "{path} does not exist. Generate the translation first (step 4)."),
    # textos sin marcar
    ("Textos sin marcar en los scripts: {n} ({k} seguros, {p} probables).",
     "Unmarked texts in the scripts: {n} ({k} certain, {p} probable)."),
    ("Agregados {n} a {name}; {m} ya tenían entrada en el tl. Ahora pulsa Pendientes y Traducir.",
     "Added {n} to {name}; {m} already had an entry in the tl. Now press Pending and Translate."),
    # importar
    ("La referencia no tiene tl/{wanted}; se usa tl/{used}.", "The reference has no tl/{wanted}; using tl/{used}."),
    ("Extrayendo tl/{lang} de {name} ...", "Extracting tl/{lang} from {name} ..."),
    ("Referencia ({path}): {n} entradas; {a} diálogos por id, {b} strings.",
     "Reference ({path}): {n} entries; {a} dialogues by id, {b} strings."),
    ("Importadas {n} traducciones ({a} por id, {b} por texto); {c} descartadas por tokens distintos. Quedan {d} pendientes para traducir con el motor.",
     "Imported {n} translations ({a} by id, {b} by text); {c} discarded for different tokens. {d} remain to be translated with the engine."),
    ("La referencia tiene el tl compilado (.rpyc) y hace falta unrpyc para leerlo.",
     "The reference has a compiled tl (.rpyc) and unrpyc is needed to read it."),
    ("No se encontró una carpeta `game` en la referencia.", "No `game` folder was found in the reference."),
    # traducir
    ("{n} textos únicos: {c} ya en caché, {t} por traducir.", "{n} unique texts: {c} already cached, {t} to translate."),
    ("Lote {i}/{total}: {got}/{size} traducidos.", "Batch {i}/{total}: {got}/{size} translated."),
    ("Lote {i}/{total} falló: {err}", "Batch {i}/{total} failed: {err}"),
    ("Respuesta inválida ({err}); se divide el lote de {n} en dos.", "Invalid response ({err}); splitting the batch of {n} in two."),
    ("Sin respuesta útil para una línea ({err}): {text}", "No useful response for one line ({err}): {text}"),
    ("Glosario creado automáticamente: {n} términos ({names}). Puedes editarlo en «7. Glosario…».",
     "Glossary created automatically: {n} terms ({names}). You can edit it in “7. Glossary…”."),
    ("Motor: {engine}. Glosario: {n} términos.", "Engine: {engine}. Glossary: {n} terms."),
    ("Traducidos {n}, de caché {c}, sin traducir {k}. Caché: {path}", "Translated {n}, from cache {c}, untranslated {k}. Cache: {path}"),
    ("SIN TRADUCIR: {text}", "UNTRANSLATED: {text}"),
    # validar / instalar
    ("Se escribirían {n} traducciones ({r} reparadas); fallaron validación: {f}; sin traducir: {u}.",
     "Would write {n} translations ({r} repaired); failed validation: {f}; untranslated: {u}."),
    ("Escritas {n} traducciones ({r} reparadas); fallaron validación: {f}; sin traducir: {u}.",
     "Written {n} translations ({r} repaired); failed validation: {f}; untranslated: {u}."),
    ("Se escribirían {n} correcciones por glosario (p. ej. el título del juego).",
     "Would write {n} glossary corrections (e.g. the game's title)."),
    ("Escritas {n} correcciones por glosario (p. ej. el título del juego).",
     "Written {n} glossary corrections (e.g. the game's title)."),
    ("FALLÓ [{where}] {why}", "FAILED [{where}] {why}"),
    ("... y {n} más en el reporte.", "... and {n} more in the report."),
    ("Reporte: {path}", "Report: {path}"),
    ("Escritos {n} archivos; ids y comentarios intactos.", "Wrote {n} files; ids and comments intact."),
    ("tl/{lang} copiado al juego: {path}", "tl/{lang} copied into the game: {path}"),
    ("{name} ya activa el idioma; se deja como está.", "{name} already sets the language; left as it is."),
    ("Creado {path}", "Created {path}"),
    ("Glosario guardado: {n} términos en {path}", "Glossary saved: {n} terms in {path}"),
    # claves y motores
    ("Falta la clave de API de {name}.", "The API key for {name} is missing."),
    ("Clave rechazada o sin permiso ({detail})", "Key rejected or without permission ({detail})"),
    ("Sin éxito tras {n} intentos ({detail})", "No success after {n} attempts ({detail})"),
    ("El modelo no existe o ya no está disponible para tu cuenta. Cambia el campo Modelo. Detalle: {detail}",
     "The model does not exist or is no longer available for your account. Change the Model field. Detail: {detail}"),
    ("{n} lotes seguidos fallaron; se detiene el trabajo.", "{n} batches in a row failed; the job is stopped."),
    ("Gemini no devolvió traducción ({reason}).", "Gemini returned no translation ({reason})."),
    ("Motor desconocido: {name}", "Unknown engine: {name}"),
    ("No se encontró unrpyc. Configura la ruta de unrpyc.py (descárgalo de https://github.com/CensoredUsername/unrpyc, licencia MIT).",
     "unrpyc was not found. Set the path of unrpyc.py (download it from https://github.com/CensoredUsername/unrpyc, MIT license)."),
]
