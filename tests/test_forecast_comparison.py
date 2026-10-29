"""User story 5: rolling-origin comparison against baselines (research R9, FR-027 to FR-034)."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import sqrt
import unittest

from sales_data_analyzer.application import (
    InsufficientHistoryError,
    ItemInput,
    SalesSession,
)
from sales_data_analyzer.forecasting import (
    DEFAULT_METHODS,
    DailyRevenue,
    ForecastMethod,
    LastValueBaseline,
    LinearTrendModel,
    MovingAverageBaseline,
    compare_methods,
)

START = date(2026, 1, 5)  # a Monday


def series(values, start: date = START) -> tuple[DailyRevenue, ...]:
    """Return consecutive daily rows with the given revenue values."""
    return tuple(
        DailyRevenue(start + timedelta(days=i), Decimal(str(v))) for i, v in enumerate(values)
    )


def weekly(n: int, trend: float = 2.0) -> tuple[DailyRevenue, ...]:
    """Return a noiseless trend with a strong Saturday effect."""
    return series([100 + trend * i + (40 if i % 7 == 5 else 0) for i in range(n)])


class Spy(ForecastMethod):
    """Records the latest training day and the predicted days; predicts a constant."""

    key = "spy"
    title = "Spy"
    kind = "model"
    explanation = "test double"

    def __init__(self, minimum: int = 1, value: float = 1.0) -> None:
        self.min_training_days = minimum
        self.value = value
        self.calls: list[tuple[date, tuple[date, ...]]] = []

    def predict(self, training: Sequence[DailyRevenue], days: Sequence[date]) -> tuple[float, ...]:
        self.calls.append((training[-1].day, tuple(days)))
        return (self.value,) * len(days)


class BlockRuleTests(unittest.TestCase):
    def test_block_count_and_skipped_needs(self) -> None:
        # n: (K, {skipped key: needed days})
        cases = {
            12: (1, {"moving_average_7": 14, "same_weekday": 21, "weekday_trend": 35}),
            20: (1, {"same_weekday": 21, "weekday_trend": 35}),
            21: (1, {"weekday_trend": 35}),
            34: (2, {"weekday_trend": 42}),
            35: (1, {}),
            63: (4, {}),
        }
        for n, (blocks, skipped) in cases.items():
            with self.subTest(n=n):
                result = compare_methods(weekly(n))
                self.assertEqual(result.blocks, blocks)
                self.assertEqual({s.method_key: s.needed_days for s in result.skipped}, skipped)
                self.assertEqual(result.evaluated_days, 7 * blocks)

    def test_moving_average_needs_14_days_at_twelve(self) -> None:
        result = compare_methods(weekly(12), methods=(LastValueBaseline(), MovingAverageBaseline()))
        self.assertEqual([s.method_key for s in result.scores], ["last_value"])
        self.assertEqual(result.skipped[0].needed_days, 14)

    def test_fewer_than_twelve_days_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            compare_methods(weekly(11))

    def test_gaps_and_bad_horizons_are_refused(self) -> None:
        rows = weekly(20)
        with self.assertRaises(ValueError):
            compare_methods(rows[:5] + rows[6:])
        for horizon in (0, 366):
            with self.subTest(horizon=horizon), self.assertRaises(ValueError):
                compare_methods(rows, horizon=horizon)
        with self.assertRaises(TypeError):
            compare_methods(rows, horizon=True)


class LeakageTests(unittest.TestCase):
    def test_methods_never_see_their_evaluation_days(self) -> None:
        spy = Spy(minimum=5)
        rows = weekly(40)
        result = compare_methods(rows, methods=(LastValueBaseline(), spy), method="spy")
        self.assertEqual(result.blocks, 4)
        origins = result.origins
        self.assertEqual(origins, tuple(rows[n].day for n in (12, 19, 26, 33)))
        evaluation_calls = spy.calls[:-1]
        for (latest, days), origin in zip(evaluation_calls, origins, strict=True):
            self.assertLess(latest, origin)
            self.assertEqual(days[0], origin)
            self.assertEqual(len(days), 7)
        latest, days = spy.calls[-1]  # final refit on the whole history
        self.assertEqual(latest, rows[-1].day)
        self.assertEqual(days[0], rows[-1].day + timedelta(days=1))

    def test_all_methods_are_scored_on_the_same_days(self) -> None:
        result = compare_methods(weekly(63))
        self.assertEqual({s.evaluated_days for s in result.scores}, {28})


class MetricTests(unittest.TestCase):
    def test_mae_rmse_and_relative_mae_by_hand(self) -> None:
        rows = series([10] * 5 + [12, 8, 10, 14, 6, 10, 10])  # 12 days, K = 1, last value 10
        spy = Spy(value=11.0)
        result = compare_methods(rows, methods=(LastValueBaseline(), spy))
        scores = {s.method_key: s for s in result.scores}
        errors = [2, -2, 0, 4, -4, 0, 0]
        self.assertAlmostEqual(scores["last_value"].mae, sum(map(abs, errors)) / 7)
        self.assertAlmostEqual(scores["last_value"].rmse, sqrt(sum(e * e for e in errors) / 7))
        self.assertAlmostEqual(scores["spy"].mae, sum(abs(e - 1) for e in errors) / 7)
        self.assertAlmostEqual(
            scores["spy"].relative_mae, scores["spy"].mae / scores["last_value"].mae
        )
        self.assertEqual(scores["last_value"].relative_mae, 1.0)

    def test_relative_mae_is_undefined_when_the_baseline_is_perfect(self) -> None:
        result = compare_methods(series([10] * 12), methods=(LastValueBaseline(), Spy()))
        self.assertTrue(all(s.relative_mae is None for s in result.scores))

    def test_ties_go_to_the_earlier_method(self) -> None:
        rows = series([10] * 20)
        result = compare_methods(rows, methods=(LastValueBaseline(), MovingAverageBaseline()))
        self.assertEqual([s.method_key for s in result.scores], ["last_value", "moving_average_7"])


class WordingFlagTests(unittest.TestCase):
    def test_strong_evidence_names_the_lowest_error_model(self) -> None:
        result = compare_methods(weekly(63))
        self.assertEqual(result.lowest_error_key, "weekday_trend")
        self.assertTrue(result.model_beats_baselines)
        self.assertTrue(result.clear_difference)
        self.assertFalse(result.weak_evidence)
        self.assertEqual(result.chosen_key, "weekday_trend")
        self.assertAlmostEqual(result.fit.weekday_effects[4], 40.0, places=6)

    def test_weak_evidence_names_nothing_and_uses_last_value(self) -> None:
        result = compare_methods(weekly(21))
        self.assertTrue(result.weak_evidence)
        self.assertIsNone(result.lowest_error_key)
        self.assertEqual(result.chosen_key, "last_value")
        self.assertIsNone(result.fit)

    def test_model_not_strictly_better_does_not_beat_baselines(self) -> None:
        rows = series([10] * 20 + [10] * 8)
        result = compare_methods(rows, methods=(LastValueBaseline(), Spy(value=10.0)))
        self.assertFalse(result.model_beats_baselines)
        self.assertFalse(result.clear_difference)

    def test_differences_under_five_percent_are_not_clear(self) -> None:
        rows = series([10] * 5 + [20] * 7)  # the last value misses by 10 on every day
        methods = (LastValueBaseline(), Spy(value=10.4))
        near = compare_methods(rows, methods=methods)  # spy MAE 9.6: 4% lower
        self.assertTrue(near.model_beats_baselines)
        self.assertFalse(near.clear_difference)
        far = compare_methods(rows, methods=(LastValueBaseline(), Spy(value=15.0)))
        self.assertTrue(far.model_beats_baselines)
        self.assertTrue(far.clear_difference)

    def test_constant_revenue_skips_the_regressions(self) -> None:
        result = compare_methods(series([10] * 40))
        reasons = {s.method_key: s.reason for s in result.skipped}
        self.assertEqual(
            reasons, {"linear_trend": "constant_revenue", "weekday_trend": "constant_revenue"}
        )

    def test_unknown_or_unscored_method_is_refused(self) -> None:
        for key in ("nope", "weekday_trend"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare_methods(weekly(21), method=key)

    def test_extrapolation_warning_above_fourteen_days(self) -> None:
        self.assertFalse(compare_methods(weekly(21), horizon=14).extrapolation_warning)
        self.assertTrue(compare_methods(weekly(21), horizon=15).extrapolation_warning)

    def test_negative_estimates_are_floored_and_reported(self) -> None:
        falling = series([100 - 10 * i for i in range(12)])  # 100 down to -10 by trend
        result = compare_methods(
            falling,
            horizon=3,
            methods=(LastValueBaseline(), LinearTrendModel()),
            method="linear_trend",
        )
        self.assertGreater(result.floored_evaluation_days, 0)
        self.assertTrue(all(p.revenue >= 0 for p in result.future))
        self.assertEqual(result.floored_future_days, tuple(p.day for p in result.future))

    def test_floored_days_are_counted_once_and_scored_as_zero(self) -> None:
        rows = series([10] * 5 + [0] * 7)
        negative = Spy(value=-5.0)
        result = compare_methods(rows, methods=(LastValueBaseline(), negative, Spy(value=-1.0)))
        self.assertEqual(result.floored_evaluation_days, 7)  # two methods, same 7 days
        spy = next(s for s in result.scores if s.method_key == "spy")
        self.assertEqual(spy.mae, 0.0)  # floored to 0, which equals the actual revenue

    def test_built_in_methods_only_receive_days_before_each_origin(self) -> None:
        seen: list[tuple[str, date, date]] = []

        class Recording(ForecastMethod):
            """Delegates to a real method and records the last training day it got."""

            def __init__(self, inner: ForecastMethod) -> None:
                self.inner = inner
                self.key, self.title, self.kind = inner.key, inner.title, inner.kind
                self.min_training_days, self.explanation = inner.min_training_days, ""

            def predict(self, training, days):
                seen.append((self.key, training[-1].day, days[0]))
                return self.inner.predict(training, days)

        rows = weekly(63)
        plain = compare_methods(rows)
        recorded = compare_methods(rows, methods=tuple(Recording(m) for m in DEFAULT_METHODS))
        self.assertEqual(
            [(s.method_key, s.mae) for s in plain.scores],
            [(s.method_key, s.mae) for s in recorded.scores],
        )
        evaluation = [(key, last, first) for key, last, first in seen if first in plain.origins]
        self.assertEqual(len(evaluation), 5 * 4)
        for key, last, first in evaluation:
            self.assertEqual(last, first - timedelta(days=1), key)

    def test_weak_evidence_wording_hides_beat_claims(self) -> None:
        from sales_data_analyzer.cli.formatting import format_comparison

        result = compare_methods(weekly(21))
        self.assertTrue(result.weak_evidence)
        text = "\n".join(format_comparison(result, "scope"))
        self.assertNotIn("beat", text)
        self.assertNotIn("clear difference", text)

    def test_future_estimates_come_from_a_refit_on_the_whole_history(self) -> None:
        rows = series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 50])
        result = compare_methods(rows, horizon=1, methods=(LastValueBaseline(),))
        self.assertEqual(result.future[0].revenue, 50.0)

    def test_default_methods_unchanged(self) -> None:
        self.assertEqual(len(DEFAULT_METHODS), 5)


class SessionComparisonTests(unittest.TestCase):
    """compare_forecasts reuses daily_revenue, the missing-day policy and UTC offsets."""

    def build(self, days: Sequence[int]) -> SalesSession:
        session = SalesSession()
        workspace = session.create_company("Acme", "Retail")
        workspace.register_product("001", "Pen", "Office")
        for day in days:
            workspace.record_sale(
                f"S{day}",
                datetime(2026, 1, 1, 10) + timedelta(days=day),
                [ItemInput("001", 1 + day % 3, Decimal("10"), Decimal("4"))],
            )
        return session

    def test_too_little_history(self) -> None:
        with self.assertRaises(InsufficientHistoryError) as caught:
            self.build(range(11)).compare_forecasts()
        self.assertEqual(
            (caught.exception.available_days, caught.exception.required_days), (11, 12)
        )

    def test_missing_days_need_the_zero_policy_and_are_counted(self) -> None:
        session = self.build([d for d in range(20) if d not in (4, 9)])
        with self.assertRaises(ValueError) as caught:
            session.compare_forecasts()
        self.assertIn("missing days", str(caught.exception))
        result = session.compare_forecasts(missing_days="zero")
        self.assertEqual(result.zero_filled_days, 2)
        self.assertEqual(result.history_days, 20)

    def test_level_two_forecast_is_unchanged(self) -> None:
        session = self.build(range(14))
        before = session.run_forecast()
        session.compare_forecasts()
        self.assertEqual(session.run_forecast(), before)


if __name__ == "__main__":
    unittest.main()
