"""Desktop window, user stories 2 and 3: catalog, manual sales and CSV import."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from support.qt import StoredWindowTestCase, application

from PySide6.QtWidgets import QDialog

from sales_data_analyzer.application import ItemInput
from sales_data_analyzer.cli.parsing import InputError
from sales_data_analyzer.gui.forms import (
    CompanyValues,
    ProductDialog,
    ProductValues,
    SaleDialog,
    SaleValues,
)
from sales_data_analyzer.gui.widgets import cells

from support.databases import row_counts

FIXTURES = Path(__file__).parent / "fixtures"
MOMENT = datetime(2026, 3, 2, 9, 30)


class CatalogAndSalesTestCase(StoredWindowTestCase):
    """A stored window with company 'Acme' selected."""

    def setUp(self) -> None:
        super().setUp()
        self.win = self.open_window()
        self.prompter.queue("company", CompanyValues("Acme", "Retail"))
        self.win.new_company()
        self.catalog, self.sales = self.win.page("catalog"), self.win.page("sales")

    def register(self, *products: tuple[str, str, str]) -> None:
        for values in products:
            self.prompter.queue("product", ProductValues(*values))
            self.catalog.register_product()


class CatalogTests(CatalogAndSalesTestCase):
    def test_register_lists_by_id_and_survives_reopen(self) -> None:
        self.register(("P2", "Ink", "Supplies"), ("P1", "Pen", "Office"))
        self.assertEqual(
            cells(self.catalog.table), [["P1", "Pen", "Office"], ["P2", "Ink", "Supplies"]]
        )
        stored = self.reopen().workspaces[0].products
        self.assertEqual([p.id for p in stored], ["P1", "P2"])

    def test_duplicate_id_is_refused_and_the_catalog_is_unchanged(self) -> None:
        self.register(("P1", "Pen", "Office"), (" P1 ", "Other", "X"))
        self.assertEqual(
            self.prompter.warnings, ["Já existe um produto com o código P1 no catálogo."]
        )
        self.assertEqual(cells(self.catalog.table), [["P1", "Pen", "Office"]])
        self.assertEqual(row_counts(self.path)["product"], 1)

    def test_edit_keeps_the_id_and_stores_name_and_category(self) -> None:
        self.register(("P1", "Pen", "Office"))
        self.catalog.select("P1")
        self.prompter.queue("product", ProductValues("P1", "Blue pen", "Writing"))
        self.catalog.edit_product()
        self.assertIn("product form (P1)", self.prompter.questions)
        self.assertEqual(cells(self.catalog.table), [["P1", "Blue pen", "Writing"]])
        stored = self.reopen().workspaces[0].products[0]
        self.assertEqual((stored.name, stored.category), ("Blue pen", "Writing"))

    def test_actions_without_a_selected_row_are_explained(self) -> None:
        self.catalog.edit_product()
        self.catalog.delete_product()
        self.assertEqual(self.prompter.warnings, ["Selecione um produto na tabela primeiro."] * 2)

    def test_unsold_product_is_deleted_only_after_confirmation(self) -> None:
        self.register(("P1", "Pen", "Office"))
        self.catalog.select("P1")
        self.prompter.queue("confirm", False, True)
        self.catalog.delete_product()
        self.assertEqual(row_counts(self.path)["product"], 1)
        self.catalog.select("P1")
        self.catalog.delete_product()
        self.assertEqual(self.prompter.questions[-1], "Excluir o produto P1 — Pen?")
        self.assertEqual(cells(self.catalog.table), [])
        self.assertEqual(row_counts(self.path)["product"], 0)

    def test_sold_product_is_kept_with_the_sale_count(self) -> None:
        self.register(("P1", "Pen", "Office"))
        workspace = self.win.session.current
        workspace.record_sale("S1", MOMENT, [ItemInput("P1", 1, Decimal(2), Decimal(1))])
        self.win.refresh()
        self.catalog.select("P1")
        self.catalog.delete_product()
        self.assertEqual(
            self.prompter.warnings,
            ["O produto aparece em 1 venda e por isso não pode ser excluído."],
        )
        self.assertEqual(row_counts(self.path)["product"], 1)


class ManualSaleTests(CatalogAndSalesTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.register(("P1", "Pen", "Office"), ("P2", "Ink", "Supplies"))

    def sale(self, sale_id: str, *items: ItemInput, moment: datetime = MOMENT) -> None:
        self.prompter.queue("sale", SaleValues(sale_id, moment, tuple(items)))
        self.sales.record_sale()

    def test_sale_with_two_items_is_listed_with_its_exact_total_and_survives_reopen(self) -> None:
        self.sale(
            "S1",
            ItemInput("P1", 3, Decimal("1.005"), Decimal("0.5")),
            ItemInput("P2", 1, Decimal("10"), Decimal("4")),
        )
        self.assertEqual(self.prompter.warnings, [])
        self.assertEqual(cells(self.sales.table), [["S1", "02/03/2026 09:30:00", "2", "13,02"]])
        self.assertEqual(self.sales.count_label.text(), "1 venda")
        stored = self.reopen().workspaces[0].sales.sales[0]
        self.assertEqual(stored.items[0].unit_price, Decimal("1.005"))
        self.assertEqual(stored.calculate_total(), Decimal("13.015"))

    def test_service_refusals_store_nothing(self) -> None:
        self.sale("S1", ItemInput("P1", 1, Decimal(1), Decimal(1)))
        cases = {
            "duplicate": ("S1", (ItemInput("P1", 1, Decimal(1), Decimal(1)),), MOMENT),
            "empty": ("S2", (), MOMENT),
            "unknown": ("S3", (ItemInput("NOPE", 1, Decimal(1), Decimal(1)),), MOMENT),
            "aware": (
                "S4",
                (ItemInput("P1", 1, Decimal(1), Decimal(1)),),
                MOMENT.replace(tzinfo=timezone(timedelta(hours=-3))),
            ),
        }
        for values in cases.values():
            sale_id, items, moment = values
            self.prompter.queue("sale", SaleValues(sale_id, moment, items))
            self.sales.record_sale()
        self.assertEqual(
            self.prompter.warnings,
            [
                "Já existe uma venda com o código S1 nesta empresa.",
                "Uma venda precisa de pelo menos um item.",
                "O produto NOPE não está no catálogo.",
                "Uma empresa não pode misturar vendas com e sem fuso horário.",
            ],
        )
        self.assertEqual(row_counts(self.path)["sale"], 1)
        self.assertEqual(len(cells(self.sales.table)), 1)

    def test_empty_catalog_is_explained_before_the_form(self) -> None:
        for product_id in ("P1", "P2"):
            self.catalog.select(product_id)
            self.prompter.queue("confirm", True)
            self.catalog.delete_product()
        self.sales.record_sale()
        self.assertEqual(
            self.prompter.warnings,
            ["O catálogo está vazio. Cadastre ou importe produtos antes de registrar uma venda."],
        )
        self.assertNotIn("sale form", self.prompter.questions)

    def test_delete_asks_first_and_removes_items(self) -> None:
        self.sale("S1", ItemInput("P1", 2, Decimal("1.50"), Decimal(1)))
        self.sales.table.clearSelection()  # recording selected the new sale
        self.sales.delete_sale()
        self.sales.select("S1")
        self.prompter.queue("confirm", False)
        self.sales.delete_sale()
        self.assertEqual(row_counts(self.path)["sale"], 1)
        self.sales.select("S1")
        self.prompter.queue("confirm", True)
        self.sales.delete_sale()
        self.assertEqual(self.prompter.warnings, ["Selecione uma venda na tabela primeiro."])
        self.assertEqual(self.prompter.questions[-1], "Excluir a venda S1 (1 item, total 3,00)?")
        self.assertEqual(cells(self.sales.table), [])
        counts = row_counts(self.path)
        self.assertEqual((counts["sale"], counts["sale_item"]), (0, 0))

    def test_list_follows_the_selected_period(self) -> None:
        self.sale("S1", ItemInput("P1", 1, Decimal(1), Decimal(1)))
        self.sale(
            "S2", ItemInput("P1", 1, Decimal(1), Decimal(1)), moment=MOMENT + timedelta(days=3)
        )
        self.win.session.set_period(MOMENT.date(), MOMENT.date())
        self.win.refresh()
        self.assertEqual([row[0] for row in cells(self.sales.table)], ["S1"])


class ImportTests(CatalogAndSalesTestCase):
    def test_valid_file_reports_the_summary_and_fills_both_tables(self) -> None:
        self.prompter.queue("open_csv", FIXTURES / "valid_sales.csv")
        self.sales.import_csv()
        self.assertEqual(self.prompter.warnings, [])
        self.assertEqual(
            self.prompter.notices,
            ["Importação concluída: 2 vendas e 3 itens. Produtos: 2 novos e 0 reaproveitados."],
        )
        self.assertEqual([row[0] for row in cells(self.catalog.table)], ["007", "008"])
        self.assertEqual(len(cells(self.sales.table)), 2)
        self.assertEqual(row_counts(self.path)["sale_item"], 3)

    def test_refusals_import_nothing(self) -> None:
        self.prompter.queue("open_csv", FIXTURES / "valid_sales.csv")
        self.sales.import_csv()
        before = row_counts(self.path)
        self.prompter.queue(
            "open_csv", FIXTURES / "invalid_sales.csv", FIXTURES / "valid_sales.csv",
            FIXTURES / "aware_sales.csv", FIXTURES / "missing.csv",
        )  # fmt: skip
        for _ in range(4):
            self.sales.import_csv()
        warnings = self.prompter.warnings
        self.assertEqual(len(warnings), 4)
        self.assertTrue(
            warnings[0].startswith(
                "Importação recusada: a linha 2 tem um problema na coluna “quantity”"
            )
        )
        self.assertEqual(
            warnings[1],
            "Importação recusada: 2 códigos de venda do arquivo já existem nesta empresa "
            "(001, 002). Nada foi importado.",
        )
        self.assertEqual(
            warnings[2], "Uma empresa não pode misturar vendas com e sem fuso horário."
        )
        self.assertTrue(warnings[3].startswith("Importação recusada"))
        self.assertNotIn(str(FIXTURES), " ".join(warnings))
        self.assertEqual(row_counts(self.path), before)

    def test_catalog_conflict_names_the_product(self) -> None:
        self.register(("007", "Coffee", "Beverages"))
        self.prompter.queue("open_csv", FIXTURES / "valid_sales.csv")
        self.sales.import_csv()
        self.assertEqual(
            self.prompter.warnings,
            [
                "Importação recusada: o produto 007 do arquivo tem nome ou categoria diferentes "
                "no catálogo. Nada foi importado."
            ],
        )
        self.assertEqual(row_counts(self.path)["sale"], 0)

    def test_cancelled_file_dialog_does_nothing(self) -> None:
        self.prompter.queue("open_csv", None)
        self.sales.import_csv()
        self.assertEqual((self.prompter.warnings, self.prompter.notices), ([], []))


class FormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def products(self):
        from sales_data_analyzer.application import SalesSession

        workspace = SalesSession().create_company("Acme", "Retail")
        workspace.register_product("P1", "Pen", "Office")
        workspace.register_product("P2", "Ink", "Supplies")
        return workspace.products

    def test_product_form_for_editing_locks_the_id(self) -> None:
        product = self.products()[0]
        dialog = ProductDialog(product)
        self.assertTrue(dialog.id_edit.isReadOnly())
        dialog.name_edit.setText(" Blue pen ")
        self.assertEqual(dialog.values(), ProductValues("P1", "Blue pen", "Office"))

    def test_sale_form_parses_exact_amounts_and_offsets(self) -> None:
        dialog = SaleDialog(self.products(), now=MOMENT)
        self.assertEqual(dialog.datetime_edit.text(), "2026-03-02T09:30:00")
        dialog.id_edit.setText("S9")
        dialog.datetime_edit.setText("2026-03-02T09:30:00.5-03:00")
        dialog.set_item(0, "P2", "2", "0.1", "0.05")
        row = dialog.add_item()
        dialog.set_item(row, "P1", "1", "12.345678", "0")
        values = dialog.values()
        self.assertEqual(values.sale_id, "S9")
        self.assertEqual(values.date_time.utcoffset(), timedelta(hours=-3))
        self.assertEqual(
            values.items,
            (
                ItemInput("P2", 2, Decimal("0.1"), Decimal("0.05")),
                ItemInput("P1", 1, Decimal("12.345678"), Decimal("0")),
            ),
        )

    def test_sale_form_names_the_invalid_field_and_stays_open(self) -> None:
        cases = {
            ("", "2026-03-02T09:30:00", "1", "1", "1"): "Código da venda: preencha",
            ("S", "2026-02-30T09:30:00", "1", "1", "1"): "Data e hora: use o formato",
            ("S", "2026-03-02T09:30:00", "0", "1", "1"): "Item 1, quantidade: use um número",
            ("S", "2026-03-02T09:30:00", "1", "-1", "1"): "Item 1, preço unitário: use um valor",
            ("S", "2026-03-02T09:30:00", "1", "1", "1,5"): "Item 1, custo unitário: use um valor",
        }
        for (sale_id, moment, quantity, price, cost), field in cases.items():
            with self.subTest(field=field):
                dialog = SaleDialog(self.products(), now=MOMENT)
                dialog.id_edit.setText(sale_id)
                dialog.datetime_edit.setText(moment)
                dialog.set_item(0, "P1", quantity, price, cost)
                with self.assertRaises(InputError) as caught:
                    dialog.values()
                self.assertTrue(str(caught.exception).startswith(field))
                dialog.accept()
                self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
                self.assertIn(field, dialog.error_label.text())

    def test_remove_item_leaves_an_empty_sale_for_the_service_to_refuse(self) -> None:
        dialog = SaleDialog(self.products(), now=MOMENT)
        dialog.id_edit.setText("S1")
        dialog.remove_item()
        self.assertEqual(dialog.values().items, ())


if __name__ == "__main__":
    unittest.main()
