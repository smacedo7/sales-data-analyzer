"""Exact accounting analyses with immutable, explicitly typed results."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.sales_dataset import SalesDataset


@dataclass(frozen=True)
class FinancialMetrics:
    """Accounting totals; margin is a ratio, undefined ratios are None."""
    revenue: Decimal
    cost: Decimal
    gross_profit: Decimal
    gross_margin: Decimal | None
    average_order_value: Decimal | None
    sale_count: int


@dataclass(frozen=True)
class ProductMetrics:
    """Totals for one company-scoped product ID; catalog names are not keys."""
    product_id: str
    quantity: int
    revenue: Decimal
    gross_profit: Decimal


@dataclass(frozen=True)
class AnalysisResult:
    """Immutable company-associated result: financial metrics or product rows.

    Product rows use ID order. Rankings contain IDs sorted by descending metric,
    then ascending ID for ties. Financial results leave product fields empty;
    product results leave financial metrics None. No mutable catalog metadata
    or third-party dataframe is required by this contract.
    """
    company: Company
    title: str
    financial: FinancialMetrics | None = None
    products: tuple[ProductMetrics, ...] = ()
    quantity_ranking: tuple[str, ...] = ()
    revenue_ranking: tuple[str, ...] = ()


class Analysis(ABC):
    """Polymorphic contract for descriptive analyses of one sales dataset."""

    @abstractmethod
    def run(self, data: SalesDataset) -> AnalysisResult:
        """Analyze data without mutation; raise TypeError for other inputs."""
        raise NotImplementedError


def _require_dataset(data: SalesDataset) -> None:
    """Reject non-dataset inputs with TypeError before reading domain values."""
    if not isinstance(data, SalesDataset):
        raise TypeError("data must be a SalesDataset")


class FinancialAnalysis(Analysis):
    """Calculate exact totals from historical item prices and costs."""

    def run(self, data: SalesDataset) -> AnalysisResult:
        """Return totals, profit, margin and ticket; empty totals are Decimal zero.

        Margin is None at zero revenue; ticket is None without transactions.
        Raise TypeError if data is not a SalesDataset.
        """
        _require_dataset(data)
        revenue = sum((s.calculate_total() for s in data.sales), Decimal(0))
        cost = sum((s.calculate_cost() for s in data.sales), Decimal(0))
        count = len(data.sales)
        profit = revenue - cost
        return AnalysisResult(data.company, "Financial analysis", FinancialMetrics(
            revenue, cost, profit, profit / revenue if revenue else None,
            revenue / count if count else None, count,
        ))


class ProductAnalysis(Analysis):
    """Group sold products by company-scoped ID and rank deterministically."""

    def run(self, data: SalesDataset) -> AnalysisResult:
        """Return quantity/revenue/profit rows and rankings; exclude unsold products.

        Distinct Product objects with the same ID are grouped together. Empty
        data produces empty tuples. Raise TypeError for non-dataset inputs.
        """
        _require_dataset(data)
        grouped: dict[str, ProductMetrics] = {}
        for sale in data.sales:
            for item in sale.items:
                key = item.product.id
                previous = grouped.get(key, ProductMetrics(key, 0, Decimal(0), Decimal(0)))
                revenue = item.calculate_subtotal()
                grouped[key] = ProductMetrics(key, previous.quantity + item.quantity,
                    previous.revenue + revenue,
                    previous.gross_profit + revenue - item.calculate_cost())
        rows = tuple(grouped[key] for key in sorted(grouped))
        return AnalysisResult(data.company, "Product analysis", products=rows,
            quantity_ranking=tuple(r.product_id for r in sorted(rows, key=lambda r: (-r.quantity, r.product_id))),
            revenue_ranking=tuple(r.product_id for r in sorted(rows, key=lambda r: (-r.revenue, r.product_id))))
