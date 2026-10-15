"""Genera assets/icon.ico (solo para desarrollo; requiere Pillow: pip install pillow)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 5
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=(31, 58, 95, 255))
    # franja inferior clara (como una caja de diálogo)
    d.rounded_rectangle(
        (size * 0.12, size * 0.64, size * 0.88, size * 0.86), radius=r // 2, fill=(236, 240, 247, 255)
    )
    for i, w in enumerate((0.55, 0.38)):
        y = size * (0.70 + i * 0.07)
        d.rounded_rectangle((size * 0.19, y, size * (0.19 + w), y + size * 0.035), radius=size // 60, fill=(31, 58, 95, 255))
    font = None
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(name, int(size * 0.56))
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    d.text((size / 2, size * 0.34), "T", font=font, fill=(255, 255, 255, 255), anchor="mm")
    return img


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    draw(256).save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icono creado:", OUT)
