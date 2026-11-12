"""Desktop window: open the database, home page, navigation locks and companies."""

from pathlib import Path
import unittest
from unittest import mock

from support.qt import StoredWindowTestCase, application

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


class OpenAndHomeTests(StoredWindowTestCase):
    def store(self, *companies: tuple[str, str]) -> None:
        repository = SQLiteSalesRepository.open(self.path)
        session = SalesSession(repository)
        for name, sector in companies:
            session.create_company(name, sector)
        repository.close()

    def test_home_lists_stored_companies_and_locks_company_pages(self) -> None:
        self.store(("Acme", "Retail"), ("Bolt", "Tools"))
        window = self.open_window()
        home = window.page("home")
        self.assertIs(window.current_page, home)
        self.assertEqual(len(home.open_buttons), 2)
        self.assertFalse(home.empty_label.isVisibleTo(home))
        self.assertEqual(window.company_label.text(), "Nenhuma empresa selecionada")
        self.assertFalse(window.period_row.isVisibleTo(window))
        self.assertEqual(window.database_label.text(), f"Banco de dados: {self.path}")
        window.go("sales")  # locked without a company
        self.assertIs(window.current_page, home)
        self.assertIn("Escolha ou cadastre uma empresa", window.statusBar().currentMessage())

    def test_opening_a_company_shows_its_overview_and_unlocks_the_navigation(self) -> None:
        self.store(("Acme", "Retail"))
        window = self.open_window()
        window.page("home").open_buttons[0].click()
        self.assertEqual(window.session.current.company.name, "Acme")
        self.assertIs(window.current_page, window.page("overview"))
        self.assertEqual(window.company_label.text(), "Acme · Retail")
        self.assertEqual(window.selection_label.text(), "Todo o histórico · 0 vendas")
        window.go("sales")
        self.assertIs(window.current_page, window.page("sales"))

    def test_empty_database_explains_there_are_no_companies(self) -> None:
        window = self.open_window()
        home = window.page("home")
        self.assertTrue(home.empty_label.isVisibleTo(home))
        self.assertEqual(home.empty_label.text(), "Você ainda não cadastrou nenhuma empresa.")


class CreateAndEditTests(StoredWindowTestCase):
    def test_new_company_is_stored_selected_and_survives_reopen(self) -> None:
        window = self.open_window()
        self.prompter.queue("company", CompanyValues("Café Açaí", "Food"))
        window.page("home").new_button.click()
        self.assertEqual(window.company_label.text(), "Café Açaí · Food")
        self.assertIs(window.current_page, window.page("overview"))
        self.assertEqual(self.prompter.warnings, [])
        self.assertEqual(row_counts(self.path)["company"], 1)
        stored = self.reopen().workspaces[0].company
        self.assertEqual((stored.name, stored.sector), ("Café Açaí", "Food"))

    def test_duplicate_name_is_refused_in_portuguese_and_nothing_is_stored(self) -> None:
        window = self.open_window()
        self.prompter.queue(
            "company", CompanyValues("Acme", "Retail"), CompanyValues(" acme ", "X")
        )
        window.new_company()
        window.new_company()
        self.assertEqual(
            self.prompter.warnings,
            ["Já existe uma empresa com esse nome (maiúsculas e espaços não contam)."],
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
        window.edit_company_button.click()
        self.assertIn("company form (Acme)", self.prompter.questions)
        self.assertEqual(window.company_label.text(), "Acme Ltd · Tools")
        stored = self.reopen().workspaces[0].company
        self.assertEqual((stored.name, stored.sector), ("Acme Ltd", "Tools"))

    def test_edit_without_company_is_explained(self) -> None:
        window = self.open_window()
        window.edit_company()
        self.assertEqual(self.prompter.warnings, ["Escolha ou cadastre uma empresa primeiro."])


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
            ["Não foi possível gravar no banco de dados. Nada foi alterado."],
        )
        self.assertEqual(window.company_label.text(), "Acme · Retail")
        self.assertEqual(self.reopen().workspaces[0].company.name, "Acme")

    def test_change_by_another_copy_asks_to_restart(self) -> None:
        window = self.open_window()
        self.prompter.queue("company", CompanyValues("Acme", "Retail"))
        with mock.patch.object(
            window.session.repository, "add_company", side_effect=ConcurrentChangeError()
        ):
            window.new_company()
        self.assertEqual(len(self.prompter.warnings), 1)
        self.assertIn("outra cópia do programa", self.prompter.warnings[0])
        self.assertIn("feche e abra o programa novamente", self.prompter.warnings[0])
        self.assertEqual(window.session.workspaces, ())

    def test_unexpected_error_is_reported_and_the_window_stays_usable(self) -> None:
        window = self.open_window()
        self.prompter.queue("company", CompanyValues("A", "B"), CompanyValues("A", "B"))
        with mock.patch.object(window.session, "create_company", side_effect=RuntimeError("boom")):
            window.new_company()
        self.assertEqual(
            self.prompter.warnings,
            ["Ocorreu um erro inesperado (RuntimeError). Seus dados não foram alterados."],
        )
        self.assertNotIn("boom", self.prompter.warnings[0])
        window.new_company()
        self.assertEqual(window.company_label.text(), "A · B")


class CompanyFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def test_valid_values_are_trimmed(self) -> None:
        dialog = CompanyDialog()
        self.assertEqual(dialog.windowTitle(), "Nova empresa")
        dialog.name_edit.setText("  Acme ")
        dialog.sector_edit.setText("Retail")
        self.assertEqual(dialog.values(), CompanyValues("Acme", "Retail"))
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_blank_field_keeps_the_form_open_and_names_the_field(self) -> None:
        dialog = CompanyDialog("Acme", "")
        self.assertEqual(dialog.windowTitle(), "Editar empresa")
        dialog.accept()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.error_label.text(), "Setor: preencha este campo")


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
            self.assertTrue(errors[0].startswith("Não foi possível abrir o banco de dados: "))
            self.assertTrue(errors[0].endswith("O arquivo não foi alterado."))

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


class DemoFlowTests(StoredWindowTestCase):
    def test_demo_button_creates_stores_and_opens_the_demo_company(self) -> None:
        window = self.open_window()
        window.page("home").demo_button.click()
        self.assertIs(window.current_page, window.page("overview"))
        self.assertEqual(len(self.prompter.notices), 1)
        self.assertTrue(
            self.prompter.notices[0].startswith("Pronto! A empresa “Café Aurora (demo)”")
        )
        self.assertEqual(len(window.page("overview").cards), 6)
        stored = self.reopen().workspaces[0]
        self.assertEqual(len(stored.products), 6)
        window.go("home")
        window.page("home").demo_button.click()  # second time: selects it, no duplicate
        self.assertEqual(len(window.session.workspaces), 1)
        self.assertEqual(
            window.statusBar().currentMessage(),
            "A empresa de demonstração já existe; ela foi selecionada.",
        )
