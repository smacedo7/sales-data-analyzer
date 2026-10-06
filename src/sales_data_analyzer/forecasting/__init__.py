"""Daily revenue preparation and temporal regression evaluation.

Scikit-learn is imported only when forecasting is requested. Accounting stays
in Decimal; floating point is used at the statistical boundary.
"""
from dataclasses import dataclass
from datetime import date, timedelta, tzinfo
from decimal import Decimal
from math import isfinite, sqrt
from typing import Literal

from sales_data_analyzer.domain.sales_dataset import SalesDataset


@dataclass(frozen=True)
class DailyRevenue:
    """One calendar day and its exact observed or explicitly assumed revenue."""
    day: date
    revenue: Decimal


@dataclass(frozen=True)
class Prediction:
    """Calendar day and unconstrained linear estimate (which may be negative)."""
    day: date
    revenue: float


@dataclass(frozen=True)
class ErrorMetrics:
    """Out-of-sample errors in revenue units, never confidence intervals."""
    mae: float
    rmse: float


@dataclass(frozen=True)
class ForecastResult:
    """Chronological evaluation and future estimates from a separate full refit.

    Baseline predicts the last training revenue throughout the test period.
    Test actuals/predictions and training observations expose the split for audit.
    """
    training: tuple[DailyRevenue, ...]
    test: tuple[DailyRevenue, ...]
    test_predictions: tuple[Prediction, ...]
    model_errors: ErrorMetrics
    baseline_errors: ErrorMetrics
    baseline_revenue: float
    future: tuple[Prediction, ...]


def daily_revenue(data: SalesDataset, *, missing_days: Literal["reject", "zero"] = "reject",
                  timezone: tzinfo | None = None) -> tuple[DailyRevenue, ...]:
    """Aggregate earliest through latest sale day; no external days are inferred.

    Naive timestamps are local calendar times. Aware timestamps require an
    explicit common timezone. Missing days raise ValueError unless zero is
    explicitly selected (meaning complete recording and no sales that day).
    Raise TypeError for wrong types, ValueError for invalid policy or timezone.
    """
    if not isinstance(data, SalesDataset):
        raise TypeError("data must be a SalesDataset")
    if missing_days not in ("reject", "zero"):
        raise ValueError("missing_days must be 'reject' or 'zero'")
    if timezone is not None and not isinstance(timezone, tzinfo):
        raise TypeError("timezone must be a tzinfo")
    totals: dict[date, Decimal] = {}
    for sale in data.sales:
        timestamp = sale.date_time
        aware = timestamp.utcoffset() is not None
        if aware and timezone is None:
            raise ValueError("aware timestamps require an explicit company timezone")
        if not aware and timezone is not None:
            raise ValueError("cannot convert naive timestamps to a company timezone")
        day = timestamp.astimezone(timezone).date() if aware else timestamp.date()
        totals[day] = totals.get(day, Decimal(0)) + sale.calculate_total()
    if not totals:
        return ()
    current, end = min(totals), max(totals)
    rows: list[DailyRevenue] = []
    while current <= end:
        if current not in totals and missing_days == "reject":
            raise ValueError("history has missing days; explicitly select zero only for complete records")
        rows.append(DailyRevenue(current, totals.get(current, Decimal(0))))
        if current == end:
            break
        current += timedelta(days=1)
    return tuple(rows)


def _positive_integer(value: int, name: str) -> None:
    """Raise TypeError for non-integers/bools and ValueError for nonpositive input."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _errors(actual: list[float], predicted: list[float]) -> ErrorMetrics:
    """Calculate finite MAE/RMSE for equally sized nonempty evaluation vectors."""
    differences = [a - p for a, p in zip(actual, predicted, strict=True)]
    metrics = ErrorMetrics(sum(abs(d) for d in differences) / len(differences),
                           sqrt(sum(d * d for d in differences) / len(differences)))
    if not isfinite(metrics.mae) or not isfinite(metrics.rmse):
        raise ValueError("evaluation errors exceed finite floating-point range")
    return metrics


class RevenueForecaster:
    """Linear trend adapter using calendar offsets available for future days.

    No lags, scaling, tuning or random split are used. At least five training
    days and two test days are required, with nonconstant training revenue.
    """

    def forecast(self, data: SalesDataset, *, horizon: int = 7, test_days: int = 2,
                 missing_days: Literal["reject", "zero"] = "reject",
                 timezone: tzinfo | None = None) -> ForecastResult:
        """Evaluate on final test_days, then refit all history for horizon days.

        Raise TypeError for invalid input types and ValueError for insufficient,
        constant, missing or nonfinite history, invalid counts or date overflow.
        Predictions are not clipped or rounded; accuracy is not guaranteed.
        """
        _positive_integer(horizon, "horizon")
        _positive_integer(test_days, "test_days")
        if test_days < 2:
            raise ValueError("at least two test days are required")
        history = daily_revenue(data, missing_days=missing_days, timezone=timezone)
        if len(history) < test_days + 5:
            raise ValueError("history requires at least five training and two test days")
        try:
            future_dates = tuple(history[-1].day + timedelta(days=i) for i in range(1, horizon + 1))
            values = [float(row.revenue) for row in history]
        except (OverflowError, ValueError) as exc:
            raise ValueError("history or horizon exceeds numeric/calendar range") from exc
        if any(not isfinite(v) for v in values):
            raise ValueError("revenue must be finite at the ML boundary")
        split = len(history) - test_days
        if len(set(values[:split])) < 2:
            raise ValueError("training revenue must vary to learn a trend")
        from sklearn.linear_model import LinearRegression

        origin = history[0].day
        features = [[(row.day - origin).days] for row in history]
        model = LinearRegression().fit(features[:split], values[:split])
        estimates = [float(v) for v in model.predict(features[split:])]
        baseline = values[split - 1]
        model_errors = _errors(values[split:], estimates)
        baseline_errors = _errors(values[split:], [baseline] * test_days)
        model.fit(features, values)
        future_values = [float(v) for v in model.predict([[(day - origin).days] for day in future_dates])]
        if any(not isfinite(v) for v in estimates + future_values):
            raise ValueError("predictions must be finite")
        return ForecastResult(history[:split], history[split:],
            tuple(Prediction(row.day, value) for row, value in zip(history[split:], estimates, strict=True)),
            model_errors, baseline_errors, baseline,
            tuple(Prediction(day, value) for day, value in zip(future_dates, future_values, strict=True)))
