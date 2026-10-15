import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from traductor import workflow as wf


def info(need_collect):
    return SimpleNamespace(need_collect=need_collect)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name) / "ws"

    def tearDown(self):
        self.tmp.cleanup()

    def test_next_step_sequence_for_loose_rpy_game(self):
        game = info(False)
        order = []
        steps = wf.load_state(self.base)
        while (nxt := wf.next_step(game, steps)) is not None:
            order.append(nxt)
            steps = wf.mark(self.base, nxt)
        self.assertEqual(
            order, ["analizar", "generar", "extras", "importar", "traducir", "validar", "instalar"]
        )
        self.assertIsNone(wf.next_step(game, steps))

    def test_scripts_in_rpa_add_extract_and_decompile(self):
        steps = wf.mark(self.base, "analizar")
        self.assertEqual(wf.next_step(info(True), steps), "extraer")
        steps = wf.mark(self.base, "extraer")
        self.assertEqual(wf.next_step(info(True), steps), "decompilar")
        self.assertEqual(wf.next_step(info(False), steps), "generar")  # no aplican si no hace falta

    def test_marking_invalidates_later_steps_but_not_analysis_or_glossary(self):
        for sid in ("analizar", "generar", "extras", "importar", "glosario", "traducir", "validar"):
            wf.mark(self.base, sid)
        steps = wf.mark(self.base, "generar")  # se regenera el tl
        self.assertEqual(set(steps), {"analizar", "generar", "glosario"})
        steps = wf.mark(self.base, "analizar")  # re-analizar no borra nada
        self.assertEqual(set(steps), {"analizar", "generar", "glosario"})

    def test_skipped_optional_step_counts_as_done(self):
        for sid in ("analizar", "generar", "extras"):
            wf.mark(self.base, sid)
        steps = wf.mark(self.base, "importar", skipped=True)
        self.assertEqual(wf.next_step(info(False), steps), "traducir")
        rows = {r["id"]: r["status"] for r in wf.checklist(info(False), steps)}
        self.assertEqual(rows["importar"], "omitido")
        self.assertEqual(rows["traducir"], "siguiente")
        self.assertEqual(rows["instalar"], "pendiente")

    def test_checklist_numbers_are_consecutive_and_skip_inapplicable(self):
        rows = wf.checklist(info(False), {})
        self.assertEqual([r["n"] for r in rows], list(range(1, len(rows) + 1)))
        self.assertNotIn("extraer", [r["id"] for r in rows])
        self.assertIn("extraer", [r["id"] for r in wf.checklist(info(True), {})])

    def test_state_survives_reload_and_bad_file(self):
        wf.mark(self.base, "analizar")
        self.assertIn("analizar", wf.load_state(self.base))
        wf.state_path(self.base).write_text("{no es json", encoding="utf-8")
        self.assertEqual(wf.load_state(self.base), {})


if __name__ == "__main__":
    unittest.main()
