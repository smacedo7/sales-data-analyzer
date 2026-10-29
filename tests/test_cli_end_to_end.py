"""End-to-end: run the real entry point in a subprocess with scripted input."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def _run_menu(lines: list[str], database: Path, home: Path) -> subprocess.CompletedProcess[str]:
    """Run `python -m sales_data_analyzer --database DATABASE` feeding lines to stdin.

    Every per-user folder points into `home` so a mistake can never reach the
    user's real database.
    """
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
        "XDG_DATA_HOME": str(home / "data"),
    }
    return subprocess.run(
        [sys.executable, "-m", "sales_data_analyzer", "--database", str(database)],
        input="\n".join(lines) + "\n",
        capture_output=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )


class EndToEndTests(unittest.TestCase):
    """Quickstart scenario A plus invalid inputs and a restart (level 2 SC-001..SC-004, FR-001)."""

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.home = Path(folder.name) / "home"
        self.home.mkdir()
        self.database = Path(folder.name) / "e2e.sqlite3"

    def run_menu(self, lines: list[str]) -> subprocess.CompletedProcess[str]:
        """Run the program on the test database."""
        return _run_menu(lines, self.database, self.home)

    def test_scenario_a_with_invalid_inputs(self) -> None:
        valid = str(FIXTURES / "valid_sales.csv")
        result = self.run_menu(
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
        self.assertIn(f"Data is saved in {self.database}.", output)

        restarted = self.run_menu(["2", "1", "10", "0"])
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        self.assertIn("Loaded 1 company(ies), 2 product(s), 2 sale(s).", restarted.stdout)
        self.assertIn("Selected: Café Açaí", restarted.stdout)
        self.assertIn("Revenue ............ 45.40", restarted.stdout)
        self.assertEqual([p for p in self.home.rglob("*") if p.is_file()], [])

    def test_end_of_input_exits_cleanly(self) -> None:
        result = self.run_menu(["1", "Shop"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"Data is saved in {self.database}.", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_without_option_the_database_goes_to_the_user_data_folder(self) -> None:
        env = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "LOCALAPPDATA": str(self.home / "AppData" / "Local"),
            "XDG_DATA_HOME": str(self.home / "data"),
        }
        result = subprocess.run(
            [sys.executable, "-m", "sales_data_analyzer"],
            input="1\nShop\nRetail\n0\n",
            capture_output=True,
            encoding="utf-8",
            env=env,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        (created,) = [p for p in self.home.rglob("sales.sqlite3")]
        self.assertIn(f"Database: {created}", result.stdout)

    def test_unusable_database_exits_with_status_two(self) -> None:
        self.database.write_text("plain text, not a database\n" * 50, encoding="utf-8")
        before = self.database.read_bytes()
        result = self.run_menu([])
        self.assertEqual(result.returncode, 2)
        self.assertIn("Cannot open the database: the file is not a database.", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
