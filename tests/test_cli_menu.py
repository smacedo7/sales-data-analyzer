"""Scripted terminal sessions exercising the menu like a user would."""

import unittest

from sales_data_analyzer.cli.menu import DATA_NOTICE, NEEDS_COMPANY, TerminalMenu

from menu_script import Script


class MenuShellTests(unittest.TestCase):
    """Start, invalid input, exit confirmation and failure containment."""

    def test_start_shows_notice_and_exit_confirms(self) -> None:
        script = Script(["0", "y"])
        self.assertEqual(script.run(), 0)
        self.assertIn(DATA_NOTICE, script.output)
        self.assertIn("Company: none", script.output)
        self.assertIn("All data from this session will be lost.", script.output)

    def test_exit_declined_keeps_running(self) -> None:
        script = Script(["0", "n", "0", "y"])
        self.assertEqual(script.run(), 0)
        self.assertEqual(script.output.count("Exit? [y/N] "), 2)

    def test_invalid_option_and_answer(self) -> None:
        script = Script(["99", "abc", "0", "maybe", "y"])
        self.assertEqual(script.run(), 0)
        self.assertEqual(script.output.count("Invalid option."), 2)
        self.assertIn("Invalid value: answer y or n.", script.output)

    def test_end_of_input_exits_cleanly(self) -> None:
        script = Script([])
        self.assertEqual(script.run(), 0)
        self.assertIn("Data is kept in memory only and was discarded.", script.output)

    def test_company_guard(self) -> None:
        for option in map(str, range(3, 13)):
            with self.subTest(option=option):
                script = Script([option, "0", "y"])
                script.run()
                self.assertIn(NEEDS_COMPANY, script.output)

    def test_unexpected_error_is_contained_without_message(self) -> None:
        script = Script(["1", "0", "y"])

        def explode() -> None:
            raise RuntimeError("secret/path/data.csv")

        script.menu._options = tuple(
            option.__class__(option.number, option.label, explode, False)
            if option.number == 1
            else option
            for option in script.menu._options
        )
        self.assertEqual(script.run(), 0)
        self.assertIn("Unexpected error (RuntimeError). Your data is unchanged.", script.output)
        self.assertNotIn("secret", script.text)

    def test_default_session_is_created(self) -> None:
        self.assertIsNotNone(TerminalMenu(input_fn=lambda _: "", output_fn=lambda _: None).session)


if __name__ == "__main__":
    unittest.main()
