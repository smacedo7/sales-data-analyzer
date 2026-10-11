"""One company's catalog and sales, changed only through all-or-nothing operations."""

from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.sales_dataset import SalesDataset


class CompanyWorkspace:
    """Everything recorded for one company during the session."""

    def __init__(self, company: Company) -> None:
        """Create an empty workspace for an existing Company."""
        if not isinstance(company, Company):
            raise TypeError("company must be a Company")
        self._company = company
        self._sales = SalesDataset(company)

    @property
    def company(self) -> Company:
        """Return the workspace's company."""
        return self._company

    @property
    def sales(self) -> SalesDataset:
        """Return all sales of the company (shared, not copied)."""
        return self._sales
