"""Genera assets/icon.ico y assets/logo.png: una «T» blanca sobre baldosa azul, con una franja de texto debajo.

Dibujo propio (la T es una forma, no una tipografía). Solo para desarrollo;
requiere Pillow: pip install pillow
"""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "assets"
# Windows elige el tamaño según la escala de pantalla (100 %: 16/32, 125 %: 20/40, 150 %: 24/48...).
SIZES = [16, 20, 24, 28, 32, 40, 48, 56, 64, 128, 256]
K = 8  # sobremuestreo: se dibuja 8 veces más grande y se reduce
NAVY, LIGHT, WHITE = (31, 58, 95, 255), (236, 240, 247, 255), (255, 255, 255, 255)


def draw(size: int) -> Image.Image:
    S = min(size * K, 2048)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = S // 5
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=r, fill=NAVY)
    # franja inferior clara, como una caja de diálogo, con dos líneas de texto
    d.rounded_rectangle((S * 0.12, S * 0.64, S * 0.88, S * 0.86), radius=r // 2, fill=LIGHT)
    line = max(0.035, 1.3 / size)  # en tamaños pequeños las líneas no bajan de ~1 px
    for i, w in enumerate((0.55, 0.38)):
        y = S * (0.70 + i * 0.075)
        d.rounded_rectangle((S * 0.19, y, S * (0.19 + w), y + S * line), radius=S // 60, fill=NAVY)
    # la «T»: barra y tronco
    d.rectangle((S * 0.30, S * 0.14, S * 0.70, S * 0.25), fill=WHITE)
    d.rectangle((S * 0.445, S * 0.14, S * 0.555, S * 0.56), fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    draw(512).save(ASSETS / "logo.png")
    frames = [draw(n) for n in SIZES]
    frames[-1].save(ASSETS / "icon.ico", sizes=[(n, n) for n in SIZES], append_images=frames[:-1])
    print("creados:", ASSETS / "logo.png", ASSETS / "icon.ico")
