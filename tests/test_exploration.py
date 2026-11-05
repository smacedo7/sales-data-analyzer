"""User story 4: exact grouped summaries (FR-022 to FR-026)."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import unittest

from sales_data_analyzer.analysis import FinancialAnalysis
from sales_data_analyzer.application import (
    ItemInput,
    NoSalesInSelectionError,
    SalesSession,
    Selection,
)
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.sales_dataset import SalesDataset
from sales_data_analyzer.exploration import (
    category_totals,
    compare_periods,
    temporal_summary,
    weekday_profile,
)

# 2026-01-01 is a Thursday (ISO week 1); 2026-01-05 is the Monday of week 2.
DAYS = (date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 4), date(2026, 1, 5), date(2026, 2, 1))


def build_session(days=DAYS, *, aware: bool = False) -> SalesSession:
    """Return a session with one sale per day: n x Pen at 0.10 and one Ink at 3.33."""
    session = SalesSession()
    workspace = session.create_company("Acme", "Retail")
    workspace.register_product("001", "Pen", "Office")
    workspace.register_product("002", "Ink", "Supplies")
    zone = timezone(timedelta(hours=-3)) if aware else None
    for number, day in enumerate(days, start=1):
        moment = datetime(day.year, day.month, day.day, 22, 30, tzinfo=zone)
        workspace.record_sale(
            f"S{number}",
            moment,
            [
                ItemInput("001", number, Decimal("0.10"), Decimal("0.03")),
                ItemInput("002", 1, Decimal("3.33"), Decimal("1.11")),
            ],
        )
    return session


class TemporalSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = build_session()
        self.data = self.session.current.sales
        self.financial = FinancialAnalysis().run(self.data).financial

    def test_sums_equal_financial_analysis_exactly_for_every_granularity(self) -> None:
        for granularity in ("day", "week", "month"):
            for policy in ("reject", "zero"):
                with self.subTest(granularity=granularity, policy=policy):
                    rows = temporal_summary(self.data, granularity, missing_days=policy).rows
                    self.assertEqual(sum(r.revenue for r in rows), self.financial.revenue)
                    self.assertEqual(sum(r.cost for r in rows), self.financial.cost)
                    self.assertEqual(sum(r.sale_count for r in rows), self.financial.sale_count)
                    for row in rows:
                        self.assertIsInstance(row.revenue, Decimal)
                        self.assertEqual(row.gross_profit, row.revenue - row.cost)

    def test_week_labels_and_bounds_follow_iso_weeks(self) -> None:
        rows = temporal_summary(self.data, "week").rows
        self.assertEqual([r.label for r in rows], ["2026-W01", "2026-W02", "2026-W05"])
        self.assertEqual((rows[0].start, rows[0].end), (date(2025, 12, 29), date(2026, 1, 4)))
        self.assertEqual(rows[0].sale_count, 3)

    def test_month_rows(self) -> None:
        rows = temporal_summary(self.data, "month").rows
        self.assertEqual([r.label for r in rows], ["2026-01", "2026-02"])
        self.assertEqual(rows[0].end, date(2026, 1, 31))
        self.assertEqual(rows[1].revenue, Decimal("3.83"))

    def test_reject_lists_only_days_with_sales_and_counts_the_others(self) -> None:
        summary = temporal_summary(self.data, "day")
        self.assertEqual([r.start for r in summary.rows], list(DAYS))
        self.assertEqual(summary.missing_days, 32 - 5)
        self.assertFalse(summary.zero_filled)

    def test_zero_fills_every_day_of_the_span(self) -> None:
        summary = temporal_summary(self.data, "day", missing_days="zero")
        self.assertEqual(len(summary.rows), 32)
        self.assertEqual(summary.rows[2].label, "2026-01-03")
        self.assertEqual((summary.rows[2].revenue, summary.rows[2].sale_count), (Decimal(0), 0))

    def test_offset_data_uses_utc_days(self) -> None:
        session = build_session((date(2026, 1, 1),), aware=True)
        summary = session.sales_over_time("day")
        # 22:30 at -03:00 is 01:30 UTC on the next day.
        self.assertEqual(summary.rows[0].start, date(2026, 1, 2))
        self.assertTrue(summary.days_are_utc)

    def test_invalid_arguments(self) -> None:
        with self.assertRaises(ValueError):
            temporal_summary(self.data, "year")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            temporal_summary(self.data, "day", missing_days="drop")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            temporal_summary([], "day")  # type: ignore[arg-type]

    def test_empty_dataset_has_no_rows(self) -> None:
        summary = temporal_summary(SalesDataset(Company("X", "Y")), "day")
        self.assertEqual((summary.rows, summary.missing_days), ((), 0))


class WeekdayProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = build_session().current.sales

    def test_reject_counts_only_days_with_sales(self) -> None:
        profile = weekday_profile(self.data)
        self.assertEqual(len(profile), 7)
        sunday = profile[6]  # 2026-01-04 and 2026-02-01
        self.assertEqual(sunday.occurrences, 2)
        self.assertEqual(sunday.total_revenue, Decimal("3.63") + Decimal("3.83"))
        self.assertEqual(sunday.average_revenue, Decimal("3.73"))
        self.assertIsNone(profile[1].average_revenue)  # no Tuesday sales

    def test_zero_divides_by_every_occurrence_in_the_grid(self) -> None:
        profile = weekday_profile(self.data, missing_days="zero")
        self.assertEqual(profile[6].occurrences, 5)  # Sundays from Jan 4 to Feb 1
        self.assertEqual(profile[6].average_revenue, Decimal("7.46") / 5)
        self.assertEqual(profile[1].average_revenue, Decimal(0))
        self.assertEqual(sum(p.occurrences for p in profile), 32)


class CategoryAndComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = build_session()
        self.data = self.session.current.sales

    def test_category_totals_use_catalog_categories(self) -> None:
        self.session.current.update_product("001", None, "Writing")
        rows = self.session.category_totals()
        self.assertEqual([r.category for r in rows], ["Supplies", "Writing"])
        self.assertEqual(rows[0].revenue, Decimal("16.65"))
        self.assertEqual((rows[1].revenue, rows[1].quantity), (Decimal("1.50"), 15))
        self.assertEqual(
            sum(r.revenue for r in rows), FinancialAnalysis().run(self.data).financial.revenue
        )

    def test_mapping_overrides_the_item_product_category(self) -> None:
        rows = category_totals(self.data, {"001": "Supplies"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].gross_profit, rows[0].revenue - rows[0].cost)

    def test_period_comparison_and_zero_base(self) -> None:
        first = Selection(date(2026, 1, 1), date(2026, 1, 2))
        second = Selection(date(2026, 1, 4), date(2026, 1, 5))
        comparison = self.session.compare_periods(first, second)
        self.assertEqual(comparison.first.revenue, Decimal("3.43") + Decimal("3.53"))
        self.assertEqual(comparison.revenue_change, Decimal("0.40"))
        self.assertEqual(comparison.sale_count_change, 0)
        empty = Selection(date(2025, 1, 1), date(2025, 1, 2))
        against_empty = self.session.compare_periods(empty, second)
        self.assertIsNone(against_empty.revenue_change_ratio)
        self.assertIsNone(against_empty.sale_count_change_ratio)
        self.assertEqual(self.session.selection, Selection())

    def test_overlapping_periods_are_allowed(self) -> None:
        period = Selection(date(2026, 1, 1), date(2026, 1, 31))
        comparison = compare_periods(
            self.session.current.sales.filter_period(datetime(2026, 1, 1), datetime(2026, 2, 1)),
            self.session.current.sales.filter_period(datetime(2026, 1, 1), datetime(2026, 2, 1)),
        )
        self.assertEqual(comparison.revenue_change_ratio, Decimal(0))
        self.assertEqual(self.session.compare_periods(period, period).revenue_change, Decimal(0))

    def test_results_hold_no_pandas_objects(self) -> None:
        results = (
            temporal_summary(self.data, "week"),
            *weekday_profile(self.data),
            *category_totals(self.data),
            compare_periods(self.data, self.data),
        )
        for result in results:
            for value in vars(result).values():
                self.assertFalse(type(value).__module__.startswith("pandas"), value)

    def test_empty_selection_is_refused_by_the_session(self) -> None:
        self.session.set_period(date(2025, 1, 1), date(2025, 1, 2))
        for call in (
            lambda: self.session.sales_over_time("day"),
            self.session.weekday_profile,
            self.session.category_totals,
        ):
            with self.assertRaises(NoSalesInSelectionError):
                call()


if __name__ == "__main__":
    unittest.main()
