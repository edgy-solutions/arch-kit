"""Tests the UAF grid rows. All values are made up."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ARCH_KIT_CONFIG", str(HERE / "testdata" / "arch-kit.yaml"))

import render_html  # noqa: E402

ROW_TH = '<th scope="row">{}</th>'


def grid(ids):
    return render_html.grid_uaf([[i] for i in ids], {}, {}, "UAF")


class MiRow(unittest.TestCase):
    def test_mi_id_is_placed(self):
        self.assertEqual(render_html.uaf_cells([["Mi-Pm-VS"]]), {("Mi", "Pm"): ["Mi-Pm-VS"]})

    def test_mi_row_between_en_and_me(self):
        html = grid(["Mi-Pm-VS"])
        en, mi, me = (html.find(ROW_TH.format(r)) for r in ("En", "Mi", "Me"))
        self.assertTrue(0 < en < mi < me)
        self.assertEqual(html.count(ROW_TH.format("Mi")), 1)
        self.assertEqual(html[en:mi].count('<th scope="row">'), 1)
        self.assertEqual(html[mi:me].count('<th scope="row">'), 1)

    def test_no_mi_id_no_mi_row_and_old_html(self):
        ids = ["Op-Mv-VS", "Sv-Tx-VS"]
        html = grid(ids)
        self.assertNotIn(ROW_TH.format("Mi"), html)
        saved = list(render_html.UAF_ROWS)
        try:
            render_html.UAF_ROWS[:] = [r for r in saved if r != "Mi"]
            old = grid(ids)
        finally:
            render_html.UAF_ROWS[:] = saved
        self.assertEqual(len(saved) - 1, 15)
        self.assertEqual(html, old)


if __name__ == "__main__":
    unittest.main()
