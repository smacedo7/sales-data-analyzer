"""End-to-end: run the real entry point in a subprocess with scripted input."""

import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def _run_menu(lines: list[str]) -> subprocess.CompletedProcess[str]:
    """Run `python -m sales_data_analyzer` feeding lines to standard input."""
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "sales_data_analyzer"],
        input="\n".join(lines) + "\n",
        capture_output=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )


class EndToEndTests(unittest.TestCase):
    """Quickstart scenario A plus invalid inputs (SC-001, SC-003, SC-004)."""

    def test_scenario_a_with_invalid_inputs(self) -> None:
        valid = str(FIXTURES / "valid_sales.csv")
        result = _run_menu(
            [
                "abc",  # invalid option
                "10",  # needs a company
                "1",
                "",  # empty name is asked again
                "Café Açaí",
                "Retail",
                "7",
                valid,
                "10",
                "7",
                f'"{valid}"',  # quoted path, as Windows drag-and-drop adds
                "8",
                "2026-13-01",  # invalid date is asked again
                "2026-01-02",
                "2026-01-02",
                "10",
                "12",
                "",
                "",
                "0",
                "y",
            ]
        )
        output = result.stdout
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", output + result.stderr)
        self.assertIn("Invalid option.", output)
        self.assertIn("Not done: create or select a company first.", output)
        self.assertIn("Company created and selected: Café Açaí", output)
        self.assertIn("Imported 2 sales, 3 items. Products: 2 new, 0 reused.", output)
        self.assertIn("Revenue ............ 45.40", output)
        self.assertIn("Cost ............... 18.20", output)
        self.assertIn("Gross profit ....... 27.20", output)
        self.assertIn(
            "Import refused: 2 sale ID(s) already exist in this company: 001, 002.", output
        )
        self.assertIn("Invalid value:", output)
        self.assertIn("Selection: 2026-01-02 to 2026-01-02 (1 sale)", output)
        self.assertIn("Revenue ............  5.00", output)
        self.assertIn("Not enough history: 1 day(s) available, at least 7 needed", output)

    def test_end_of_input_exits_cleanly(self) -> None:
        result = _run_menu(["1", "Shop"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Data is kept in memory only and was discarded.", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
