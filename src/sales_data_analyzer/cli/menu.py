"""Numbered terminal menu over the application session.

Input and output are injected (`input_fn`, `output_fn`) so scripted sessions can
drive the menu in tests exactly as a person would at the keyboard.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from sales_data_analyzer.application import (
    ApplicationError,
    CatalogConflictError,
    DuplicateSaleError,
    ItemInput,
    NoSalesInSelectionError,
    PersistenceError,
    ProductInUseError,
    SalesSession,
    StorageLimitError,
)
from sales_data_analyzer.importing import ImportValidationError

from .formatting import (
    explain_forecast_error,
    format_financial,
    format_forecast,
    format_id_list,
    format_catalog,
    format_import_summary,
    format_money,
    format_products,
    format_sales,
    format_scope,
    is_missing_days_error,
    plural,
)
from .parsing import (
    InputError,
    parse_amount,
    parse_date,
    parse_datetime,
    parse_path,
    parse_positive_int,
    parse_text,
    parse_utc_offset,
    parse_yes_no,
)

DATA_NOTICE = "Data is kept in memory only and is lost when you exit."
SAVED_NOTICE = "Data is saved in {location}."
NEEDS_COMPANY = "Not done: create or select a company first."
MAX_HORIZON = 365
DEFAULT_HORIZON = 7
DEFAULT_TEST_DAYS = 2


@dataclass(frozen=True)
class _Option:
    """One menu entry; handlers needing a company are guarded by the loop."""

    number: int
    label: str
    handler: Callable[[], None] | None
    needs_company: bool = True


class TerminalMenu:
    """Interactive loop that maps menu choices to application use cases."""

    def __init__(
        self,
        session: SalesSession | None = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        """Create a menu over session (a new one by default) with injectable I/O."""
        self.session = session if session is not None else SalesSession()
        self._input = input_fn
        self._output = output_fn
        self._options = self._build_options()

    def _build_options(self) -> tuple[_Option, ...]:
        """Return the menu entries in display order (0 = Exit is handled by run)."""
        return (
            _Option(1, "Create company", self._create_company, needs_company=False),
            _Option(2, "Select company", self._select_company, needs_company=False),
            _Option(3, "Register product", self._register_product),
            _Option(4, "List products", self._list_products),
            _Option(5, "Find product", self._find_product),
            _Option(6, "Record sale", self._record_sale),
            _Option(7, "Import CSV", self._import_csv),
            _Option(8, "Set period", self._set_period),
            _Option(9, "Clear period", self._clear_period),
            _Option(10, "Financial analysis", self._financial_analysis),
            _Option(11, "Product analysis", self._product_analysis),
            _Option(12, "Revenue forecast", self._forecast),
            _Option(13, "Edit company", self._edit_company),
            _Option(14, "Edit product", self._edit_product),
            _Option(15, "Delete product", self._delete_product),
            _Option(16, "List sales", self._list_sales),
            _Option(17, "Delete sale", self._delete_sale),
        )

    # -- loop -----------------------------------------------------------------

    @property
    def _location(self) -> str | None:
        """Return where the session's data is stored, or None in memory mode."""
        repository = self.session.repository
        return None if repository is None else repository.location

    def run(self) -> int:
        """Run until the user exits or input ends; return exit status 0.

        In memory mode exit asks for confirmation because data would be lost; with
        a database every change is already saved, so exit is immediate.
        """
        self._say_start()
        try:
            while True:
                self._show_menu()
                choice = self._input("Choose an option: ").strip()
                if choice == "0":
                    if self._location is not None:
                        self._say(SAVED_NOTICE.format(location=self._location))
                        return 0
                    if self._confirm_exit():
                        return 0
                    continue
                option = self._find_option(choice)
                if option is None:
                    self._say("Invalid option.")
                    continue
                self._dispatch(option)
        except EOFError, KeyboardInterrupt:
            self._say("")
            if self._location is not None:
                self._say(SAVED_NOTICE.format(location=self._location))
            else:
                self._say(DATA_NOTICE.replace("is lost when you exit", "was discarded"))
            return 0

    def _say_start(self) -> None:
        """Print the title and where data lives (with stored counts for a database)."""
        if self._location is None:
            self._say("Sales Data Analyzer - level 2 (terminal)")
            self._say(DATA_NOTICE)
            return
        workspaces = self.session.workspaces
        products = sum(len(w.products) for w in workspaces)
        sales = sum(len(w.sales.sales) for w in workspaces)
        self._say("Sales Data Analyzer - level 3 (terminal)")
        self._say(f"Database: {self._location}")
        self._say(f"Loaded {len(workspaces)} company(ies), {products} product(s), {sales} sale(s).")

    def _show_menu(self) -> None:
        """Print the header with the current company and the numbered options."""
        self._say("")
        self._say(self._header())
        for option in self._options:
            self._say(f"{option.number:>2}. {option.label}")
        self._say(" 0. Exit")

    def _header(self) -> str:
        """Describe the selected company for the menu header."""
        workspace = self.session.current
        if workspace is None:
            return "Company: none"
        company = workspace.company
        try:
            count = len(self.session.selected_sales().sales)
        except ValueError:  # defensive: the header must never stop the menu
            return f"Company: {company.name} ({company.sector})"
        selection = self.session.selection.describe()
        return (
            f"Company: {company.name} ({company.sector}) | "
            f"Selection: {selection} ({plural(count, 'sale')})"
        )

    def _find_option(self, choice: str) -> _Option | None:
        """Return the option for a typed number, or None when it is not listed."""
        for option in self._options:
            if choice == str(option.number):
                return option
        return None

    def _dispatch(self, option: _Option) -> None:
        """Run one handler, turning every error into a message for the user."""
        if option.needs_company and self.session.current is None:
            self._say(NEEDS_COMPANY)
            return
        if option.handler is None:
            self._say("Not done: this option is not available yet.")
            return
        try:
            option.handler()
        except EOFError, KeyboardInterrupt:
            raise
        except ImportValidationError as error:
            self._say(_describe_import_error(error))
        except (PersistenceError, StorageLimitError) as error:
            self._say(f"Not done: {error}. Nothing was changed.")
        except (ApplicationError, ValueError, TypeError) as error:
            self._say(f"Not done: {error}.")
        except Exception as error:  # the menu must survive any failure
            self._say(f"Unexpected error ({type(error).__name__}). Your data is unchanged.")

    def _confirm_exit(self) -> bool:
        """Ask before discarding the session's data."""
        self._say("All data from this session will be lost.")
        return self._ask("Exit? [y/N] ", parse_yes_no)

    # -- companies (US1) ---------------------------------------------------------

    def _create_company(self) -> None:
        """Ask for name and sector, then create and select the company."""
        name = self._ask("Company name: ", parse_text)
        sector = self._ask("Sector: ", parse_text)
        workspace = self.session.create_company(name, sector)
        self._say(f"Company created and selected: {workspace.company.name}")

    def _select_company(self) -> None:
        """List companies and select one by its number."""
        workspaces = self.session.workspaces
        if not workspaces:
            self._say("No companies yet.")
            return
        for number, workspace in enumerate(workspaces, start=1):
            self._say(f"{number}. {workspace.company.name} ({workspace.company.sector})")
        index = self._ask("Company number: ", parse_positive_int)
        workspace = self.session.select_company(index)
        self._say(f"Selected: {workspace.company.name}")

    # -- catalog and manual sales (US4) --------------------------------------------

    def _register_product(self) -> None:
        """Ask for ID, name and category and add the product to the catalog."""
        workspace = self.session.require_current()
        product_id = self._ask("Product ID: ", parse_text)
        name = self._ask("Name: ", parse_text)
        category = self._ask("Category: ", parse_text)
        product = workspace.register_product(product_id, name, category)
        self._say(f"Product registered: {product.id} {product.name} ({product.category})")

    def _list_products(self) -> None:
        """Print the catalog ordered by ID."""
        for line in format_catalog(self.session.require_current().products):
            self._say(line)

    def _find_product(self) -> None:
        """Look a product up by ID."""
        workspace = self.session.require_current()
        product = workspace.find_product(self._ask("Product ID: ", parse_text))
        if product is None:
            self._say("Product not found.")
            return
        self._say(f"{product.id}: {product.name} ({product.category})")

    def _record_sale(self) -> None:
        """Ask for a sale and its items; store it only when it has valid items."""
        workspace = self.session.require_current()
        if not workspace.products:
            self._say("Not done: the catalog is empty; register or import products first.")
            return
        sale_id = self._ask("Sale ID: ", parse_text)
        if workspace.has_sale(sale_id):
            self._say("Not done: this sale ID already exists in this company.")
            return
        date_time = self._ask("Date and time (YYYY-MM-DDTHH:MM:SS): ", parse_datetime)
        items: list[ItemInput] = []
        while True:
            product_id = self._input("Product ID (blank to finish): ").strip()
            if not product_id:
                break
            product = workspace.find_product(product_id)
            if product is None:
                self._say("Product not found in the catalog; try again or leave blank.")
                continue
            quantity = self._ask("Quantity: ", parse_positive_int)
            price = self._ask("Unit price: ", parse_amount)
            cost = self._ask("Unit cost: ", parse_amount)
            items.append(ItemInput(product.id, quantity, price, cost))
            self._say(f"Item added: {product.name} x {quantity}")
        if not items:
            self._say("Not done: a sale needs at least one item. Nothing was stored.")
            return
        sale = workspace.record_sale(sale_id, date_time, items)
        self._say(
            f"Sale {sale.id} recorded: {plural(len(sale.items), 'item')}, "
            f"total {format_money(sale.calculate_total())}."
        )

    # -- import (US2) -------------------------------------------------------------

    def _import_csv(self) -> None:
        """Import a CSV file into the selected company, reporting refusals with IDs."""
        workspace = self.session.require_current()
        path = self._ask("CSV file path: ", parse_path)
        try:
            summary = workspace.import_sales(path)
        except DuplicateSaleError as error:
            self._say(
                f"Import refused: {len(error.sale_ids)} sale ID(s) already exist in this "
                f"company: {format_id_list(error.sale_ids)}. Nothing was imported."
            )
            return
        except CatalogConflictError as error:
            self._say(
                f"Import refused: {len(error.product_ids)} product ID(s) have a different "
                f"name or category in the catalog: {format_id_list(error.product_ids)}. "
                "Nothing was imported."
            )
            return
        self._say(format_import_summary(summary))

    # -- selection and analyses (US3) ---------------------------------------------

    def _set_period(self) -> None:
        """Ask for an inclusive date range and make it the active selection."""
        self.session.require_current()
        if self.session.data_is_aware():
            self._say("These sales have time zone offsets: dates are interpreted in UTC.")
        start = self._ask("Start date (YYYY-MM-DD): ", parse_date)
        end = self._ask("End date (YYYY-MM-DD, included): ", parse_date)
        self.session.set_period(start, end)
        count = len(self.session.selected_sales().sales)
        self._say(f"Selection: {self.session.selection.describe()} ({plural(count, 'sale')})")

    def _clear_period(self) -> None:
        """Select all data again."""
        self.session.clear_period()
        self._say("Selection: all data")

    def _scope(self) -> str:
        """Describe the current company and selection for result headers."""
        workspace = self.session.require_current()
        count = len(self.session.selected_sales().sales)
        return format_scope(workspace.company.name, self.session.selection.describe(), count)

    def _financial_analysis(self) -> None:
        """Print the financial analysis of the selection."""
        result = self.session.run_financial_analysis()
        for line in format_financial(result, self._scope()):
            self._say(line)

    def _product_analysis(self) -> None:
        """Print the product analysis of the selection with catalog names."""
        result = self.session.run_product_analysis()
        names = {p.id: p.name for p in self.session.require_current().products}
        for line in format_products(result, self._scope(), names):
            self._say(line)

    # -- forecast (US5) -------------------------------------------------------------

    def _forecast(self) -> None:
        """Ask the forecast parameters, run it and explain results or refusals."""
        workspace = self.session.require_current()
        if not self.session.selected_sales().sales:
            self._say(explain_forecast_error(NoSalesInSelectionError()))
            return
        horizon = self._ask(
            f"Days to forecast (1-{MAX_HORIZON}, blank = {DEFAULT_HORIZON}): ", _parse_horizon
        )
        test_days = self._ask(
            f"Test days (at least 2, blank = {DEFAULT_TEST_DAYS}): ", _parse_test_days
        )
        offset = None
        if self.session.data_is_aware():
            self._say("These sales have time zone offsets; days are grouped by a UTC offset.")
            offset = self._ask("UTC offset (+HH:MM or -HH:MM, blank = +00:00): ", _parse_offset)
        options = {"horizon": horizon, "test_days": test_days, "utc_offset": offset}
        try:
            result = self.session.run_forecast(**options)
        except ValueError as error:
            self._say(explain_forecast_error(error))
            if not is_missing_days_error(error):
                return
            question = (
                "Treat missing days as zero revenue? Only answer yes if your records "
                "are complete. [y/N] "
            )
            if not self._ask(question, parse_yes_no):
                self._say("Forecast cancelled.")
                return
            try:
                result = self.session.run_forecast(missing_days="zero", **options)
            except ValueError as retry_error:
                self._say(explain_forecast_error(retry_error))
                return
        scope = f"{workspace.company.name} - {self.session.selection.describe()}"
        for line in format_forecast(result, scope):
            self._say(line)

    # -- maintenance (level 3) ------------------------------------------------------

    def _edit_company(self) -> None:
        """Ask for a new name and sector (blank keeps each) and apply both together."""
        self.session.require_current()
        name = self._ask("New name (blank = keep): ", _parse_optional_text)
        sector = self._ask("New sector (blank = keep): ", _parse_optional_text)
        company = self.session.update_company(name, sector).company
        self._say(f"Company updated: {company.name} ({company.sector})")

    def _edit_product(self) -> None:
        """Ask for a product and its new name and category (blank keeps each)."""
        workspace = self.session.require_current()
        product = workspace.find_product(self._ask("Product ID: ", parse_text))
        if product is None:
            self._say("Product not found.")
            return
        name = self._ask("New name (blank = keep): ", _parse_optional_text)
        category = self._ask("New category (blank = keep): ", _parse_optional_text)
        product = workspace.update_product(product.id, name, category)
        self._say(f"Product updated: {product.id} {product.name} ({product.category})")

    def _delete_product(self) -> None:
        """Delete an unsold product after confirmation."""
        workspace = self.session.require_current()
        product = workspace.find_product(self._ask("Product ID: ", parse_text))
        if product is None:
            self._say("Product not found.")
            return
        in_use = workspace.sales_with_product(product.id)
        if in_use:
            self._say(_in_use_message(in_use))
            return
        if not self._ask(f"Delete product {product.id} {product.name}? [y/N] ", parse_yes_no):
            self._say("Nothing was deleted.")
            return
        try:
            workspace.delete_product(product.id)
        except ProductInUseError as error:
            self._say(_in_use_message(error.sale_count))
            return
        self._say(f"Product deleted: {product.id}")

    def _list_sales(self) -> None:
        """Print the sales of the active selection."""
        workspace = self.session.require_current()
        for line in format_sales(workspace.list_sales(self.session.selected_sales())):
            self._say(line)

    def _delete_sale(self) -> None:
        """Delete a sale and its items after confirmation."""
        workspace = self.session.require_current()
        sale = workspace.find_sale(self._ask("Sale ID: ", parse_text))
        if sale is None:
            self._say("Sale not found.")
            return
        question = (
            f"Delete sale {sale.id} ({plural(len(sale.items), 'item')}, "
            f"total {format_money(sale.calculate_total())})? [y/N] "
        )
        if not self._ask(question, parse_yes_no):
            self._say("Nothing was deleted.")
            return
        workspace.delete_sale(sale.id)
        self._say(f"Sale deleted: {sale.id}")

    # -- prompt helpers ---------------------------------------------------------

    def _say(self, line: str) -> None:
        """Write one line of output."""
        self._output(line)

    def _ask[T](self, prompt: str, parser: Callable[[str], T]) -> T:
        """Prompt until parser accepts the answer; InputError explains the format."""
        while True:
            try:
                return parser(self._input(prompt))
            except InputError as error:
                self._say(f"Invalid value: {error}.")


def _parse_optional_text(text: str) -> str | None:
    """Return trimmed text, or None when blank (keep the current value)."""
    value = text.strip()
    return value or None


def _in_use_message(sale_count: int) -> str:
    """Explain why a sold product cannot be deleted."""
    return f"Not done: this product appears in {plural(sale_count, 'sale')} and cannot be deleted."


def _parse_horizon(text: str) -> int:
    """Return the forecast horizon in days; blank means the default."""
    if not text.strip():
        return DEFAULT_HORIZON
    return parse_positive_int(text, maximum=MAX_HORIZON)


def _parse_test_days(text: str) -> int:
    """Return the number of test days (at least 2); blank means the default."""
    if not text.strip():
        return DEFAULT_TEST_DAYS
    value = parse_positive_int(text)
    if value < 2:
        raise InputError("expected at least 2 test days")
    return value


def _parse_offset(text: str) -> timedelta:
    """Return a UTC offset; blank means +00:00."""
    return timedelta(0) if not text.strip() else parse_utc_offset(text)


def _describe_import_error(error: ImportValidationError) -> str:
    """Return the import diagnostic without raw values; line 0 means the file itself."""
    if error.line == 0:
        return f"Import refused: {error.reason}."
    return f"Import refused at line {error.line}, field {error.field}: {error.reason}."
