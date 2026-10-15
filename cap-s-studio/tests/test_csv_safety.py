from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from cap_s.csv_safety import spreadsheet_safe_cell


class CsvSafetyTests(unittest.TestCase):
    def test_formula_like_labels_are_literal_text(self) -> None:
        for label in ("=1+1", "+HYPERLINK('a')", "-cmd|' /C", "@SUM(A1:A2)", "  =1+2"):
            with self.subTest(label=label):
                self.assertEqual(spreadsheet_safe_cell(label), "'" + label)

    def test_numeric_columns_are_not_rewritten(self) -> None:
        for value in (12.5, -4.5, "-4.5", "+1.0", "-1.2e-5", "NaN", "normal_file.xlsx"):
            with self.subTest(value=value):
                self.assertEqual(spreadsheet_safe_cell(value), value)



if __name__ == "__main__":
    unittest.main()
