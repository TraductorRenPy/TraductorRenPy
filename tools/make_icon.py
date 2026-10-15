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


SNAP_UP_TO = 64  # hasta este tamaño, cada borde se alinea a la cuadrícula de píxeles (iconos nítidos)


def draw(size: int) -> Image.Image:
    S = min(size * K, 2048)
    f = S / size  # píxeles del lienzo grande por cada píxel del icono final
    snap = size <= SNAP_UP_TO

    def px(v):  # fracción del icono -> píxeles del icono final (enteros si se alinea)
        return round(v * size) if snap else v * size

    def span(half):  # tramo simétrico alrededor del centro
        left = px(0.5 - half)
        return left, size - left

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size * 0.2
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=r * f, fill=NAVY)
    # franja inferior clara, como una caja de diálogo, con dos líneas de texto
    x0, x1 = span(0.38)
    d.rounded_rectangle((x0 * f, px(0.64) * f, x1 * f, px(0.86) * f), radius=r * f / 2, fill=LIGHT)
    thick = max(1, px(0.035)) if snap else size * 0.035
    lx = px(0.19)
    for i, w in enumerate((0.55, 0.38)):
        y = px(0.70 + i * 0.075)
        d.rounded_rectangle((lx * f, y * f, (lx + px(w)) * f, (y + thick) * f), radius=min(thick * f / 2, S // 60), fill=NAVY)
    # la «T»: barra y tronco
    b0, b1 = span(0.20)
    t0, t1 = span(0.055)
    if snap and t1 - t0 < 2:
        t0, t1 = (size // 2) - 1, (size // 2) + 1
    d.rectangle((b0 * f, px(0.14) * f, b1 * f - 1, px(0.25) * f - 1), fill=WHITE)
    d.rectangle((t0 * f, px(0.14) * f, t1 * f - 1, px(0.56) * f - 1), fill=WHITE)
    return img.resize((size, size), Image.BOX if snap else Image.LANCZOS)  # BOX: bordes alineados quedan exactos


if __name__ == "__main__":
    draw(512).save(ASSETS / "logo.png")
    draw(1024).save(ASSETS / "logo-1024.png")  # alta resolución, para Ko-fi, GitHub y otros sitios
    frames = [draw(n) for n in SIZES]
    frames[-1].save(ASSETS / "icon.ico", sizes=[(n, n) for n in SIZES], append_images=frames[:-1])
    print("creados: logo.png, logo-1024.png, icon.ico en", ASSETS)
