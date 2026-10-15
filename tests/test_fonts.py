import struct
import tempfile
import unittest
from pathlib import Path

from traductor import fonts


def sfnt(tag: bytes, tables: dict) -> bytes:
    """Fuente mínima: cabecera + directorio + tablas (suficiente para el lector propio)."""
    n = len(tables)
    out = bytearray(tag + struct.pack(">HHHH", n, 0, 0, 0))
    offset = 12 + 16 * n
    blobs = []
    for name, blob in tables.items():
        out += struct.pack(">4sIII", name.encode("latin-1"), 0, offset, len(blob))
        padded = blob + b"\0" * (-len(blob) % 4)
        blobs.append(padded)
        offset += len(padded)
    return bytes(out) + b"".join(blobs)


def cmap_table(mapping: dict) -> bytes:
    """cmap con una subtabla formato 4 (plataforma 3, codificación 1): un segmento por carácter."""
    items = sorted(mapping.items())
    segs = [(cp, cp, (gid - cp) & 0xFFFF) for cp, gid in items] + [(0xFFFF, 0xFFFF, 1)]
    segcount = len(segs)
    body = struct.pack(">HHHH", segcount * 2, 0, 0, 0)
    body += b"".join(struct.pack(">H", e) for _s, e, _d in segs)
    body += struct.pack(">H", 0)
    body += b"".join(struct.pack(">H", s) for s, _e, _d in segs)
    body += b"".join(struct.pack(">H", d) for _s, _e, d in segs)
    body += b"".join(struct.pack(">H", 0) for _ in segs)
    sub = struct.pack(">HHH", 4, 6 + len(body), 0) + body
    return struct.pack(">HH", 0, 1) + struct.pack(">HHI", 3, 1, 12) + sub


def truetype(mapping: dict, sizes: list) -> bytes:
    """glyf/loca: `sizes[i]` = bytes del glifo i (0 = glifo vacío)."""
    glyf = b"".join(b"\x01" * s for s in sizes)
    offs, pos = [0], 0
    for s in sizes:
        pos += s
        offs.append(pos)
    head = b"\0" * 50 + struct.pack(">h", 0) + b"\0" * 2  # indexToLocFormat = 0 (corto)
    maxp = struct.pack(">IH", 0x00010000, len(sizes))
    loca = b"".join(struct.pack(">H", o // 2) for o in offs)
    return sfnt(b"\x00\x01\x00\x00", {"cmap": cmap_table(mapping), "glyf": glyf, "head": head, "loca": loca,
                                        "maxp": maxp})


def cff(mapping: dict, charstrings: list) -> bytes:
    """CFF mínima con una fuente y sus charstrings."""
    def index(items):
        if not items:
            return struct.pack(">H", 0)
        offs, pos = [1], 1
        for it in items:
            pos += len(it)
            offs.append(pos)
        return struct.pack(">HB", len(items), 1) + bytes(offs) + b"".join(items)

    header = bytes([1, 0, 4, 1])
    name_idx = index([b"T"])
    string_idx, gsubr = index([]), index([])
    top_idx_len = len(index([b"\0" * 6]))
    cs_offset = len(header) + len(name_idx) + top_idx_len + len(string_idx) + len(gsubr)
    top = index([bytes([29]) + struct.pack(">i", cs_offset) + bytes([17])])
    blob = header + name_idx + top + string_idx + gsubr + index(charstrings)
    return sfnt(b"OTTO", {"cmap": cmap_table(mapping), "CFF ": blob})


MAP = {ord("n"): 1, ord("ñ"): 2, ord("é"): 3}  # á no está en la fuente


class CheckFontTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, data):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_truetype_detects_missing_and_empty_glyphs(self):
        font = self.write("a.ttf", truetype(MAP, [10, 10, 0, 10]))  # la ñ (glifo 2) está vacía
        self.assertEqual(fonts.check_font(font, "nñéá"), ["ñ", "á"])  # ñ vacía, á sin glifo

    def test_cff_detects_missing_and_empty_glyphs(self):
        charstrings = [b"\x01" * 8, b"\x01" * 8, bytes([14]), b"\x01" * 8]  # glifo 2: solo «endchar»
        font = self.write("a.otf", cff(MAP, charstrings))
        self.assertEqual(fonts.check_font(font, "nñéá"), ["ñ", "á"])

    def test_a_good_font_has_no_problems(self):
        font = self.write("ok.ttf", truetype(MAP, [10, 10, 10, 10]))
        self.assertEqual(fonts.check_font(font, "nñé"), [])

    def test_unreadable_files_return_none(self):
        self.assertIsNone(fonts.check_font(self.write("bad.ttf", b"not a font"), "ñ"))
        self.assertIsNone(fonts.check_font(self.dir / "no-existe.ttf", "ñ"))


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.game = Path(self.tmp.name) / "game"
        self.game.mkdir()

    def font(self, name, good):
        """Fuente con todas las letras del español; si `good` es False, la ñ está vacía."""
        chars = fonts.needed_chars("spanish")
        mapping = {ord(c): i + 1 for i, c in enumerate(chars)}
        sizes = [10] * (len(chars) + 1)
        if not good:
            sizes[mapping[ord("ñ")]] = 0
        (self.game / name).write_bytes(truetype(mapping, sizes))

    def script(self, text):
        (self.game / "options.rpy").write_text(text, encoding="utf-8")

    def test_proposes_a_good_font_with_the_same_weight(self):
        self.font("Fancy-Bold.ttf", good=False)
        self.font("Plain.ttf", good=True)
        self.font("Strong-Bold.ttf", good=True)
        self.script('define gui.text_font = "Fancy-Bold.ttf"\ndefine gui.x = "Plain.ttf"\n'
                    'style a:\n    font "Strong-Bold.ttf"\n')
        report = fonts.analyze(self.game, [self.game], "Spanish")
        self.assertEqual([p.name for p in report.problems], ["Fancy-Bold.ttf"])
        self.assertEqual(report.problems[0].replacement, "Strong-Bold.ttf")
        self.assertIn("ñ", report.problems[0].chars)

    def test_falls_back_to_the_font_that_ships_with_renpy(self):
        self.font("Only.ttf", good=False)
        self.script('define gui.text_font = "Only.ttf"\n')
        report = fonts.analyze(self.game, [self.game], "spanish")
        self.assertEqual(report.problems[0].replacement, fonts.RENPY_FALLBACK)

    def test_ignores_fonts_the_game_never_uses_and_languages_without_special_letters(self):
        self.font("Unused.ttf", good=False)
        self.script("define x = 1\n")
        self.assertEqual(fonts.analyze(self.game, [self.game], "spanish").problems, [])
        self.font("Used.ttf", good=False)
        self.script('define gui.text_font = "Used.ttf"\n')
        self.assertEqual(fonts.analyze(self.game, [self.game], "english").problems, [])  # sin letras propias

    def test_fonts_in_tags_and_subfolders_are_found(self):
        (self.game / "fonts").mkdir()
        self.font("Deco.ttf", good=False)
        (self.game / "fonts" / "Deco.ttf").write_bytes((self.game / "Deco.ttf").read_bytes())
        (self.game / "Deco.ttf").unlink()
        self.script('text "{font=fonts/Deco.ttf}Hola{/font}"\n')
        report = fonts.analyze(self.game, [self.game], "spanish")
        self.assertEqual([p.name for p in report.problems], ["fonts/Deco.ttf"])

    def test_render_fix_uses_the_exact_language_name(self):
        text = fonts.render_fix("Spanish", [fonts.FontProblem("A.otf", ["ñ", "¿"], "B.ttf")])
        self.assertIn("translate Spanish python:", text)
        self.assertIn('config.font_replacement_map[("A.otf", _b, _i)] = ("B.ttf", _b, _i)', text)
        self.assertEqual(fonts.fix_filename("Spanish"), "zz_fuentes_Spanish.rpy")
        compile(text.replace("translate Spanish python:", "if True:"), "zz", "exec")  # el cuerpo es Python válido

    def test_write_fix_creates_the_file(self):
        path = fonts.write_fix(self.game, "spanish", [fonts.FontProblem("A.otf", ["ñ"], "B.ttf")])
        self.assertTrue(path.read_text(encoding="utf-8-sig").startswith("# Arreglo de fuentes"))


if __name__ == "__main__":
    unittest.main()
