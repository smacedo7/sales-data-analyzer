from datetime import datetime

from .company import Company
from .sale import Sale


class SalesDataset:
    """An ordered collection associating non-empty sales of one company."""

    def __init__(self, company: Company) -> None:
        if not isinstance(company, Company):
            raise TypeError("company must be a Company")
        self._company = company
        self._sales: list[Sale] = []
        self._ids: set[str] = set()

    @property
    def company(self) -> Company:
        return self._company

    @property
    def sales(self) -> tuple[Sale, ...]:
        return tuple(self._sales)

    def add_sale(self, sale: Sale) -> None:
        if not isinstance(sale, Sale):
            raise TypeError("sale must be a Sale")
        if sale.company is not self.company:
            raise ValueError("sale must belong to the dataset company")
        if not sale.items:
            raise ValueError("sale must contain at least one item")
        if sale.id in self._ids:
            raise ValueError("sale id already exists in this dataset")
        if self._sales:
            self._require_same_awareness(self._sales[0].date_time, sale.date_time)
        self._sales.append(sale)
        self._ids.add(sale.id)

    @staticmethod
    def _require_same_awareness(first: datetime, second: datetime) -> None:
        if (first.utcoffset() is None) != (second.utcoffset() is None):
            raise ValueError("datetimes must be consistently naive or timezone-aware")

    def filter_period(self, start: datetime, end: datetime) -> "SalesDataset":
        """Return shared sales in [start, end), preserving insertion order."""
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise TypeError("start and end must be datetimes")
        self._require_same_awareness(start, end)
        if start >= end:
            raise ValueError("start must be earlier than end")
        if self._sales:
            self._require_same_awareness(start, self._sales[0].date_time)
        result = SalesDataset(self.company)
        for sale in self._sales:
            if start <= sale.date_time < end:
                result.add_sale(sale)
        return result
