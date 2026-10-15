import pickle
import tempfile
import unittest
import zlib
from pathlib import Path

from traductor.rpa import RpaError, extract_scripts, read_index


def build_rpa(path: Path, files: dict, key: int = 0x42424242, prefix: bytes = b"") -> None:
    """Escribe un RPA-3.0 como lo hace Ren'Py."""
    header_len = 34
    body = bytearray()
    index = {}
    for name, data in files.items():
        offset = header_len + len(body)
        pre = prefix if data else b""
        payload = data[len(pre):] if pre and data.startswith(pre) else data
        body += payload
        index[name] = [(offset ^ key, len(data) ^ key, pre)]
    index_offset = header_len + len(body)
    raw_index = zlib.compress(pickle.dumps(index, 2))
    header = f"RPA-3.0 {index_offset:016x} {key:08x}\n".encode()
    assert len(header) == header_len
    path.write_bytes(header + bytes(body) + raw_index)


class RpaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_extract_only_scripts(self):
        files = {
            "script.rpyc": b"RENPY RPC2 abc",
            "sub/dir/a.rpy": b"label a:\n    return\n",
            "images/bg.png": b"\x89PNG",
        }
        rpa = self.dir / "t.rpa"
        build_rpa(rpa, files)
        out = self.dir / "out"
        res = extract_scripts(rpa, out)
        self.assertEqual(sorted(res.extracted), ["script.rpyc", "sub/dir/a.rpy"])
        self.assertEqual((out / "script.rpyc").read_bytes(), files["script.rpyc"])
        self.assertEqual((out / "sub/dir/a.rpy").read_bytes(), files["sub/dir/a.rpy"])
        self.assertFalse((out / "images").exists())

    def test_prefix_is_prepended(self):
        rpa = self.dir / "p.rpa"
        build_rpa(rpa, {"x.rpyc": b"HEADBODY"}, prefix=b"HEAD")
        extract_scripts(rpa, self.dir / "out")
        self.assertEqual((self.dir / "out/x.rpyc").read_bytes(), b"HEADBODY")

    def test_unsafe_names_are_ignored(self):
        rpa = self.dir / "u.rpa"
        build_rpa(rpa, {"../evil.rpy": b"x", "/abs.rpy": b"x", "ok.rpy": b"x"})
        index = read_index(rpa)
        self.assertEqual([e.name for e in index.entries], ["ok.rpy"])
        self.assertEqual(index.unsafe_names, 2)

    def test_malicious_pickle_is_rejected(self):
        class Evil:
            def __reduce__(self):
                import os
                return (os.system, ("echo pwned",))

        payload = zlib.compress(pickle.dumps({"a.rpy": Evil()}, 2))
        header = f"RPA-3.0 {34:016x} {0:08x}\n".encode()
        rpa = self.dir / "e.rpa"
        rpa.write_bytes(header + payload)
        with self.assertRaises(RpaError):
            read_index(rpa)

    def test_not_an_rpa(self):
        f = self.dir / "n.rpa"
        f.write_bytes(b"hello world\n")
        with self.assertRaises(RpaError):
            read_index(f)


if __name__ == "__main__":
    unittest.main()
