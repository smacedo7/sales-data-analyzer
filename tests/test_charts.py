"""User story 6: text bars and PNG chart files (FR-035, FR-036)."""

from datetime import date
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from sales_data_analyzer.charts import bar_lines
from sales_data_analyzer.charts.images import (
    DAILY_FILE,
    MONTHLY_FILE,
    PRODUCTS_FILE,
    ChartInputs,
    ChartWriteError,
    save_charts,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
INPUTS = ChartInputs(
    title="Acme - all data",
    daily=((date(2026, 1, 1), Decimal("5.10")), (date(2026, 1, 2), Decimal("9"))),
    monthly=(("2026-01", Decimal("14.10")),),
    top_products=(("001 Pen", Decimal("10")), ("002 Ink", Decimal("4.10"))),
    forecast=((date(2026, 1, 3), 9.5),),
    forecast_title="Last value",
)


class BarLineTests(unittest.TestCase):
    def test_bars_are_proportional_and_values_exact(self) -> None:
        lines = bar_lines([("a", Decimal("10")), ("bbb", Decimal("5.005"))], width=10)
        self.assertEqual(lines, ["a   | ########## 10", "bbb | #####      5.005"])

    def test_all_zero_and_tiny_values(self) -> None:
        self.assertEqual(bar_lines([("x", Decimal(0))], width=4), ["x |      0"])
        lines = bar_lines([("big", Decimal(1000)), ("tiny", Decimal("0.01"))], width=40)
        self.assertEqual(lines[1].split("|")[1].count("#"), 1)
        self.assertEqual(lines[0].split("|")[1].count("#"), 40)

    def test_long_labels_align_and_formatter_is_used(self) -> None:
        lines = bar_lines(
            [("a very long label", Decimal(2)), ("b", Decimal(1))],
            width=4,
            value_text=lambda v: f"<{v}>",
        )
        self.assertEqual(lines[0].index("|"), lines[1].index("|"))
        self.assertTrue(lines[1].endswith("<1>"))

    def test_invalid_input(self) -> None:
        self.assertEqual(bar_lines([]), [])
        with self.assertRaises(ValueError):
            bar_lines([("x", Decimal(-1))])
        with self.assertRaises(ValueError):
            bar_lines([("x", Decimal(1))], width=0)


class SaveChartsTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name) / "reports"

    def test_three_png_files_are_written(self) -> None:
        written = save_charts(INPUTS, self.folder, replace=lambda path: True)
        self.assertEqual([p.name for p in written], [DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE])
        for path in written:
            self.assertEqual(path.read_bytes()[:8], PNG_SIGNATURE)
        self.assertEqual(
            sorted(p.name for p in self.folder.iterdir()), sorted(p.name for p in written)
        )

    def test_replace_callback_is_respected(self) -> None:
        save_charts(INPUTS, self.folder, replace=lambda path: True)
        (self.folder / MONTHLY_FILE).write_bytes(b"keep")
        asked: list[str] = []

        def replace(path: Path) -> bool:
            asked.append(path.name)
            return path.name != MONTHLY_FILE

        written = save_charts(INPUTS, self.folder, replace=replace)
        self.assertEqual(asked, [DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE])
        self.assertEqual([p.name for p in written], [DAILY_FILE, PRODUCTS_FILE])
        self.assertEqual((self.folder / MONTHLY_FILE).read_bytes(), b"keep")

    def test_unwritable_folder_leaves_no_file(self) -> None:
        self.folder.parent.joinpath("file").write_text("x")
        with self.assertRaises(ChartWriteError):
            save_charts(INPUTS, self.folder.parent / "file" / "sub", replace=lambda path: True)
        self.folder.mkdir()
        with mock.patch("os.replace", side_effect=PermissionError("denied")):
            with self.assertRaises(ChartWriteError):
                save_charts(INPUTS, self.folder, replace=lambda path: True)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_charts_without_data_are_skipped(self) -> None:
        empty = ChartInputs("Acme", (), (), ())
        self.assertEqual(save_charts(empty, self.folder, replace=lambda path: True), ())

    def test_no_window_backend_and_no_import_for_text_charts(self) -> None:
        code = (
            "import sys\n"
            "from decimal import Decimal\n"
            "from sales_data_analyzer.charts import bar_lines\n"
            "import sales_data_analyzer.cli\n"
            "bar_lines([('a', Decimal(1))])\n"
            "assert 'matplotlib' not in sys.modules, 'matplotlib loaded'\n"
            "assert 'pandas' not in sys.modules, 'pandas loaded'\n"
        )
        subprocess.run([sys.executable, "-c", code], check=True)
        save_charts(INPUTS, self.folder, replace=lambda path: True)
        self.assertNotIn("matplotlib.pyplot", sys.modules)


if __name__ == "__main__":
    unittest.main()
