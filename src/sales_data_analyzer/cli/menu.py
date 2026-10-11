"""Numbered terminal menu over the application session.

Input and output are injected (`input_fn`, `output_fn`) so scripted sessions can
drive the menu in tests exactly as a person would at the keyboard.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sales_data_analyzer.application import (
    ApplicationError,
    CatalogConflictError,
    DuplicateSaleError,
    SalesSession,
)
from sales_data_analyzer.importing import ImportValidationError

from .formatting import (
    format_financial,
    format_id_list,
    format_import_summary,
    format_products,
    format_scope,
    plural,
)
from .parsing import (
    InputError,
    parse_date,
    parse_path,
    parse_positive_int,
    parse_text,
    parse_yes_no,
)

DATA_NOTICE = "Data is kept in memory only and is lost when you exit."
NEEDS_COMPANY = "Not done: create or select a company first."


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
            _Option(3, "Register product", None),
            _Option(4, "List products", None),
            _Option(5, "Find product", None),
            _Option(6, "Record sale", None),
            _Option(7, "Import CSV", self._import_csv),
            _Option(8, "Set period", self._set_period),
            _Option(9, "Clear period", self._clear_period),
            _Option(10, "Financial analysis", self._financial_analysis),
            _Option(11, "Product analysis", self._product_analysis),
            _Option(12, "Revenue forecast", None),
        )

    # -- loop -----------------------------------------------------------------

    def run(self) -> int:
        """Run until the user confirms exit or input ends; return exit status 0."""
        self._say("Sales Data Analyzer - level 2 (terminal)")
        self._say(DATA_NOTICE)
        try:
            while True:
                self._show_menu()
                choice = self._input("Choose an option: ").strip()
                if choice == "0":
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
            self._say(DATA_NOTICE.replace("is lost when you exit", "was discarded"))
            return 0

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


def _describe_import_error(error: ImportValidationError) -> str:
    """Return the import diagnostic without raw values; line 0 means the file itself."""
    if error.line == 0:
        return f"Import refused: {error.reason}."
    return f"Import refused at line {error.line}, field {error.field}: {error.reason}."
