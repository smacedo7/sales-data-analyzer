"""Desktop window, user story 1: open the database and choose or register a company."""

from pathlib import Path
import unittest
from unittest import mock

from support.qt import WindowTestCase, application

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from sales_data_analyzer.application import (
    ConcurrentChangeError,
    PersistenceError,
    SalesSession,
)
from sales_data_analyzer.gui import OPEN_FAILURE_STATUS, run
from sales_data_analyzer.gui.forms import CompanyDialog, CompanyValues
from sales_data_analyzer.persistence import SQLiteSalesRepository

from support.databases import row_counts, temporary_database


class StoredWindowTestCase(WindowTestCase):
    """A window over a session loaded from a temporary database file."""

    def setUp(self) -> None:
        context = temporary_database()
        self.path = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def open_window(self):
        """Open the database like one program run and return the window."""
        repository = SQLiteSalesRepository.open(self.path)
        self.addCleanup(repository.close)
        return self.window(SalesSession.open(repository))

    def reopen(self) -> SalesSession:
        """Return the stored data as a new run would load it."""
        repository = SQLiteSalesRepository.open(self.path)
        self.addCleanup(repository.close)
        return SalesSession.open(repository)


class OpenAndListTests(StoredWindowTestCase):
    def test_stored_companies_are_listed_and_none_is_selected(self) -> None:
        repository = SQLiteSalesRepository.open(self.path)
        session = SalesSession(repository)
        session.create_company("Acme", "Retail")
        session.create_company("Bolt", "Tools")
        repository.close()

        window = self.open_window()
        box = window.company_box
        self.assertEqual(
            [box.itemText(i) for i in range(box.count())],
            ["No company selected", "Acme (Retail)", "Bolt (Tools)"],
        )
        self.assertEqual(box.currentIndex(), 0)
        self.assertFalse(window.tabs.isEnabled())
        self.assertFalse(window.edit_company_button.isEnabled())
        self.assertEqual(window.selection_label.text(), "No company selected")
        self.assertEqual(window.database_label.text(), f"Database: {self.path}")

    def test_choosing_a_company_selects_it_and_enables_the_tabs(self) -> None:
        repository = SQLiteSalesRepository.open(self.path)
        SalesSession(repository).create_company("Acme", "Retail")
        repository.close()
        window = self.open_window()
        window.company_box.activated.emit(1)
        self.assertEqual(window.session.current.company.name, "Acme")
        self.assertTrue(window.tabs.isEnabled())
        self.assertEqual(window.selection_label.text(), "Selection: Acme - all data (0 sales)")
        window.company_box.activated.emit(0)  # the placeholder keeps the selection
        self.assertEqual(window.company_box.currentIndex(), 1)


class CreateAndEditTests(StoredWindowTestCase):
    def test_new_company_is_stored_selected_and_survives_reopen(self) -> None:
        window = self.open_window()
        self.prompter.queue("company", CompanyValues("Café Açaí", "Food"))
        QTest.mouseClick(window.new_company_button, Qt.MouseButton.LeftButton)
        self.assertEqual(window.company_box.currentText(), "Café Açaí (Food)")
        self.assertEqual(self.prompter.warnings, [])
        self.assertEqual(row_counts(self.path)["company"], 1)
        stored = self.reopen().workspaces[0].company
        self.assertEqual((stored.name, stored.sector), ("Café Açaí", "Food"))

    def test_duplicate_name_is_refused_and_nothing_is_stored(self) -> None:
        window = self.open_window()
        self.prompter.queue(
            "company", CompanyValues("Acme", "Retail"), CompanyValues(" acme ", "X")
        )
        window.new_company()
        window.new_company()
        self.assertEqual(
            self.prompter.warnings, ["Not done: a company with this name already exists."]
        )
        self.assertEqual(row_counts(self.path)["company"], 1)

    def test_cancelled_form_changes_nothing(self) -> None:
        window = self.open_window()
        self.prompter.queue("company", None)
        window.new_company()
        self.assertEqual(window.session.workspaces, ())
        self.assertNoPendingAnswers()

    def test_edit_stores_both_values(self) -> None:
        window = self.open_window()
        self.prompter.queue(
            "company", CompanyValues("Acme", "Retail"), CompanyValues("Acme Ltd", "Tools")
        )
        window.new_company()
        window.edit_company()
        self.assertIn("company form (Acme)", self.prompter.questions)
        self.assertEqual(window.company_box.currentText(), "Acme Ltd (Tools)")
        stored = self.reopen().workspaces[0].company
        self.assertEqual((stored.name, stored.sector), ("Acme Ltd", "Tools"))

    def test_edit_without_company_is_explained(self) -> None:
        window = self.open_window()
        window.edit_company()
        self.assertEqual(self.prompter.warnings, ["Not done: create or select a company first."])


class FailureTests(StoredWindowTestCase):
    def test_storage_failure_keeps_the_old_values(self) -> None:
        window = self.open_window()
        self.prompter.queue("company", CompanyValues("Acme", "Retail"), CompanyValues("New", "X"))
        window.new_company()
        with mock.patch.object(
            window.session.repository, "update_company", side_effect=PersistenceError()
        ):
            window.edit_company()
        self.assertEqual(
            self.prompter.warnings,
            ["Not done: the database could not be updated. Nothing was changed."],
        )
        self.assertEqual(window.company_box.currentText(), "Acme (Retail)")
        self.assertEqual(self.reopen().workspaces[0].company.name, "Acme")

    def test_change_by_another_copy_asks_to_restart(self) -> None:
        window = self.open_window()
        self.prompter.queue("company", CompanyValues("Acme", "Retail"))
        with mock.patch.object(
            window.session.repository, "add_company", side_effect=ConcurrentChangeError()
        ):
            window.new_company()
        self.assertEqual(len(self.prompter.warnings), 1)
        self.assertIn("another copy of the program; restart it", self.prompter.warnings[0])
        self.assertEqual(window.session.workspaces, ())

    def test_unexpected_error_is_reported_and_the_window_stays_usable(self) -> None:
        window = self.open_window()
        self.prompter.queue("company", CompanyValues("A", "B"), CompanyValues("A", "B"))
        with mock.patch.object(window.session, "create_company", side_effect=RuntimeError("boom")):
            window.new_company()
        self.assertEqual(
            self.prompter.warnings, ["Unexpected error (RuntimeError). Your data is unchanged."]
        )
        window.new_company()
        self.assertEqual(window.company_box.currentText(), "A (B)")


class CompanyFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def test_valid_values_are_trimmed(self) -> None:
        dialog = CompanyDialog()
        dialog.name_edit.setText("  Acme ")
        dialog.sector_edit.setText("Retail")
        self.assertEqual(dialog.values(), CompanyValues("Acme", "Retail"))
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_blank_field_keeps_the_form_open_and_names_the_field(self) -> None:
        dialog = CompanyDialog("Acme", "")
        self.assertEqual(dialog.windowTitle(), "Edit company")
        dialog.accept()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(
            dialog.error_label.text(), "Invalid value: Sector: a non-empty value is required."
        )


class StartUpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def test_unreadable_file_is_reported_unchanged_with_status_two(self) -> None:
        with temporary_database() as path:
            path.write_bytes(b"not a database at all")
            errors: list[str] = []
            status = run(["--database", str(path)], show_error=errors.append, execute=False)
            self.assertEqual(status, OPEN_FAILURE_STATUS)
            self.assertEqual(path.read_bytes(), b"not a database at all")
            self.assertEqual(len(errors), 1)
            self.assertTrue(errors[0].startswith("Cannot open the database: "))
            self.assertTrue(errors[0].endswith("The file was not changed."))

    def test_new_file_opens_and_the_repository_is_closed(self) -> None:
        with temporary_database() as path:
            original = SQLiteSalesRepository.close
            with mock.patch.object(
                SQLiteSalesRepository, "close", autospec=True, side_effect=original
            ) as close:
                status = run(["--database", str(path)], show_error=self.fail, execute=False)
            self.assertEqual(status, 0)
            self.assertTrue(Path(path).exists())
            close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
