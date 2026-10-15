"""Texto de la ventana «Ayuda» (resumen) y dónde está el tutorial completo (.txt)."""

import sys
from pathlib import Path
from typing import Optional

from . import settings

TUTORIAL_FILES = {"es": "TUTORIAL.txt", "en": "TUTORIAL_EN.txt"}


def tutorial_path(lang: str) -> Optional[Path]:
    """El tutorial junto al .exe, o en docs/ al ejecutar desde el código. None si no se encuentra."""
    name = TUTORIAL_FILES.get(lang, TUTORIAL_FILES["es"])
    candidates = [Path(sys.executable).parent / name, settings.PROJECT_DIR / "docs" / name]
    return next((p for p in candidates if p.is_file()), None)


HELP_ES = """\
CÓMO TRADUCIR UN JUEGO

1. Elige la carpeta del juego
   La que contiene la carpeta «game» (puede estar dentro de otras carpetas).

2. Elige el idioma de la traducción, tu motor y pega tu clave
   Gemini (Google) tiene nivel gratuito. El botón «Conseguir clave…» abre la
   página donde se crea. Cada persona usa su propia clave, que se guarda cifrada
   solo en este equipo.

3. Pulsa «▶ Traducir este juego automáticamente»
   La app hace todos los pasos y solo te pregunta lo necesario:
   • si tienes una versión anterior ya traducida (para aprovecharla),
   • si quieres gastar tu API en lo que falta (te dice cuántos textos son),
   • si quieres instalar la traducción en el juego.

4. Abre el juego
   Debe iniciar en el idioma elegido. Si algo no te gusta, se puede deshacer
   (ver «Deshacer»).

LA LISTA «QUÉ HACER AHORA»
Muestra cada paso con ✓ (hecho), ▶ (el que sigue) o · (pendiente). El botón
«Hacer el siguiente paso» ejecuta justo el que toca. Puedes parar y seguir otro
día: la app recuerda dónde ibas.

SI SE DETIENE O FALLA
Todo lo traducido se guarda tras cada lote: no se pierde nada. Para seguir, pulsa
otra vez «Traducir lo que falta».
• «Cuota diaria agotada»: el nivel gratuito tiene un tope por día. Espera al
  reinicio diario, cambia el modelo, cambia de motor o activa la facturación.
• «Clave rechazada»: revisa que la clave esté bien pegada y sea del motor elegido.
• Líneas sin traducir: cambia de motor (p. ej. Microsoft) y pulsa
  «Traducir lo que falta»; solo procesa lo pendiente.
• Líneas que «no pasaron la validación» (traducidas pero con el formato roto):
  quedan sin traducir en el juego, sin dañarlo. La app ya repara sola los saltos de
  línea de los bordes. Con «Reintentar las que fallaron la validación» se
  traducen de nuevo con el motor elegido (guarda antes una copia de la caché).
  El archivo reporte.txt, en la carpeta de trabajo, dice cuáles son.

JUGAR MIENTRAS TRADUCES
Puedes cancelar, pulsar «9. Revisar» y «10. Instalar» y jugar lo ya traducido
(cierra el juego antes de instalar). Lo que falta se ve en el idioma original.
Luego sigue con «Traducir lo que falta» y vuelve a instalar.

AJUSTES AVANZADOS
• Líneas por lote: más líneas = menos peticiones (ayuda con los límites diarios),
  pero más riesgo de respuestas defectuosas. Para cambiarlo, cancela y continúa.
• Peticiones simultáneas: varios lotes a la vez. Es un modo avanzado pensado para
  cuentas de pago; con el nivel gratuito déjalo en 1.
• Avisar al terminar: sonido, parpadeo en la barra de tareas y una ventana al
  terminar o detenerse un trabajo de más de 30 segundos.
• Crédito en el juego: una línea opcional al final de «Acerca de» del juego
  (vacío = no añade nada). Usa el nombre o alias que quieras hacer público.
• Caja de diálogo…: cambia solo el aspecto de la caja de texto (archivo aparte).

CONTENIDO PARA ADULTOS
Se pide a Gemini y Grok traducir sin censurar, pero el servicio puede bloquear
respuestas: esas líneas quedan sin traducir. Microsoft Translator no filtra, aunque
es más literal. Aplica a juegos con personajes adultos.

QUÉ TOCA LA APP EN TU JUEGO
• Escribe la traducción en game/tl/<idioma>/ y crea game/zz_<idioma>.rpy.
• Antes de escribir, guarda un respaldo en la carpeta de trabajo (subcarpeta
  «respaldos»).
• Los scripts del juego no se modifican.

DESHACER
Copia el respaldo de la carpeta «respaldos» de vuelta sobre game/tl/<idioma>.

REN'PY SDK
Hace falta el Ren'Py SDK (gratis, renpy.org); no se incluye. La app intenta
encontrarlo sola; si no, usa el botón «Buscar SDK».

AVISO DE WINDOWS
Si al abrir el programa Windows muestra «Windows protegió su PC», pulsa
«Más información» y luego «Ejecutar de todas formas»: el programa es gratuito y
no tiene firma digital de pago.

TEXTO DENTRO DE IMÁGENES
Las letras dibujadas dentro de una imagen no se pueden traducir con esta app;
solo el texto que el juego escribe como texto.

USO RESPONSABLE
Traduce solo juegos que tengas derecho a traducir, no compartas los scripts
extraídos ni las traducciones de juegos ajenos sin permiso de sus autores y da
crédito al autor original.

MÁS AYUDA
El botón de abajo abre el tutorial completo (.txt). Preguntas y opiniones:
github.com/TraductorRenPy/TraductorRenPy/discussions
"""

HELP_EN = """\
HOW TO TRANSLATE A GAME

1. Choose the game folder
   The one that contains the "game" folder (it can be inside other folders).

2. Choose the translation language and your engine, and paste your key
   Gemini (Google) has a free tier. The "Get key…" button opens the page where
   it is created. Everyone uses their own key, which is stored encrypted only
   on this computer.

3. Press "▶ Translate this game automatically"
   The app runs every step and only asks what it needs:
   • whether you have an earlier translated version (to reuse it),
   • whether you want to spend your API quota on what is missing (it tells you
     how many texts that is),
   • whether you want to install the translation into the game.

4. Open the game
   It should start in the chosen language. If you don't like something it can be
   undone (see "Undo").

THE "WHAT TO DO NOW" LIST
It shows each step as ✓ (done), ▶ (next) or · (pending). The "Do the next step"
button runs exactly the one that is due. You can stop and continue another day:
the app remembers where you were.

IF IT STOPS OR FAILS
Everything translated is saved after each batch: nothing is lost. To continue,
press "Translate what is missing" again.
• "Daily quota exhausted": the free tier has a daily cap. Wait for the daily
  reset, change the model, change the engine or enable billing.
• "Key rejected": check the key is pasted correctly and belongs to the chosen engine.
• Untranslated lines: change engine (e.g. Microsoft) and press
  "Translate what is missing"; it only processes what is pending.
• Lines that "failed validation" (translated but with broken formatting):
  they stay untranslated in the game, without harming it. The app already repairs
  the line breaks at the edges by itself. "Retry the lines that failed
  validation" translates them again with the chosen engine (it saves a copy of
  the cache first). The reporte.txt file, in the work folder, lists them.

PLAY WHILE YOU TRANSLATE
You can cancel, press "9. Review" and "10. Install" and play what is already
translated (close the game before installing). What is missing shows in the
original language. Then continue with "Translate what is missing" and install again.

ADVANCED SETTINGS
• Lines per batch: more lines = fewer requests (helps with daily limits), but a
  higher risk of defective answers. To change it, cancel and continue.
• Simultaneous requests: several batches at once. An advanced mode meant for
  paid accounts; on the free tier leave it at 1.
• Notify when done: sound, taskbar flash and a window when a job longer than
  30 seconds finishes or stops.
• Credit in the game: an optional line at the end of the game's "About" screen
  (empty = adds nothing). Use the name or alias you want to make public.
• Dialogue box…: changes only the look of the text box (separate file).

ADULT CONTENT
Gemini and Grok are asked to translate without censoring, but the service may
block answers: those lines stay untranslated. Microsoft Translator does not
filter, though it is more literal. This applies to games with adult characters.

WHAT THE APP TOUCHES IN YOUR GAME
• It writes the translation into game/tl/<language>/ and creates game/zz_<language>.rpy.
• Before writing, it saves a backup in the work folder ("respaldos" subfolder).
• The game's scripts are never modified.

UNDO
Copy the backup from the "respaldos" folder back over game/tl/<language>.

REN'PY SDK
The Ren'Py SDK (free, renpy.org) is required; it is not included. The app tries
to find it by itself; if it can't, use the "Find SDK" button.

WINDOWS WARNING
If Windows shows "Windows protected your PC" when you open the program, click
"More info" and then "Run anyway": the program is free and has no paid digital
signature.

TEXT INSIDE IMAGES
Letters drawn inside an image cannot be translated with this app; only text the
game writes as text.

RESPONSIBLE USE
Only translate games you have the right to translate, do not share extracted
scripts or translations of other people's games without their authors'
permission, and credit the original author.

MORE HELP
The button below opens the full tutorial (.txt). Questions and feedback:
github.com/TraductorRenPy/TraductorRenPy/discussions
"""
