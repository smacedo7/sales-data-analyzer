"""Interpretable daily revenue forecast methods behind one interface.

Baselines have no fitted parameters and are the benchmarks; models are ordinary
least squares regressions on the day number (and weekday). Every method receives
only its training rows, so evaluation code controls what each one can see.
Predictions are floats (the statistical boundary) and are not floored here.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Literal

from . import DailyRevenue


class ConstantRevenueError(ValueError):
    """Raised by regression methods when training revenue does not vary."""

    def __init__(self) -> None:
        super().__init__("training revenue must vary to learn a trend")


@dataclass(frozen=True)
class FitSummary:
    """Readable coefficients of a regression fit.

    weekday_effects holds Tuesday..Sunday differences from Monday (six values),
    or None for the plain trend.
    """

    trend_per_day: float
    weekday_effects: tuple[float, ...] | None = None


class ForecastMethod(ABC):
    """One way of predicting daily revenue from earlier days.

    `min_training_days` is the shortest contiguous training history the method
    accepts; callers must not pass less.
    """

    key: str
    title: str
    kind: Literal["baseline", "model"]
    min_training_days: int
    explanation: str

    @abstractmethod
    def predict(self, training: Sequence[DailyRevenue], days: Sequence[date]) -> tuple[float, ...]:
        """Return one estimate per day in days, using only training rows.

        Raise ValueError when training is shorter than `min_training_days`, and
        ConstantRevenueError for regressions on constant revenue.
        """

    def fit_summary(self, training: Sequence[DailyRevenue]) -> FitSummary | None:
        """Return readable coefficients for regressions; None for baselines."""
        return None

    def _check(self, training: Sequence[DailyRevenue]) -> list[float]:
        """Validate the training length and return revenue as finite floats."""
        if len(training) < self.min_training_days:
            raise ValueError(f"{self.title} needs {self.min_training_days} training days")
        values = [float(row.revenue) for row in training]
        if not all(isfinite(value) for value in values):
            raise ValueError("revenue must be finite at the ML boundary")
        return values

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class LastValueBaseline(ForecastMethod):
    """Repeat the last training day."""

    key = "last_value"
    title = "Last value"
    kind = "baseline"
    min_training_days = 1
    explanation = "repeats the revenue of the last known day"

    def predict(self, training: Sequence[DailyRevenue], days: Sequence[date]) -> tuple[float, ...]:
        """Return the last training revenue for every day."""
        return (self._check(training)[-1],) * len(days)


class MovingAverageBaseline(ForecastMethod):
    """Repeat the mean of the last `window` training days."""

    kind = "baseline"

    def __init__(self, window: int = 7) -> None:
        if isinstance(window, bool) or not isinstance(window, int) or window < 1:
            raise ValueError("window must be a positive integer")
        self.window = window
        self.key = f"moving_average_{window}"
        self.title = f"{window}-day average"
        self.min_training_days = window
        self.explanation = f"repeats the mean revenue of the last {window} days"

    def predict(self, training: Sequence[DailyRevenue], days: Sequence[date]) -> tuple[float, ...]:
        """Return the mean of the last window days for every day."""
        recent = self._check(training)[-self.window :]
        return (sum(recent) / len(recent),) * len(days)


class SeasonalNaiveBaseline(ForecastMethod):
    """Use the most recent training value with the same weekday."""

    kind = "baseline"

    def __init__(self, period: int = 7) -> None:
        if period != 7:
            raise ValueError("only the weekly period (7 days) is supported")
        self.period = period
        self.key = "same_weekday"
        self.title = "Same weekday last week"
        self.min_training_days = 2 * period
        self.explanation = "repeats the revenue of the same weekday in the last known week"

    def predict(self, training: Sequence[DailyRevenue], days: Sequence[date]) -> tuple[float, ...]:
        """Return, for each day, the latest training revenue on that weekday."""
        values = self._check(training)
        latest = {row.day.weekday(): value for row, value in zip(training, values, strict=True)}
        return tuple(latest[day.weekday()] for day in days)


class _Regression(ForecastMethod):
    """Ordinary least squares on features computable for future days."""

    kind = "model"

    def _features(self, origin: date, day: date) -> list[float]:
        """Return the regression features of one day."""
        raise NotImplementedError

    def _fit(self, training: Sequence[DailyRevenue]):  # -> (LinearRegression, origin)
        """Fit the regression on training rows; refuse constant revenue."""
        values = self._check(training)
        if len(set(values)) < 2:
            raise ConstantRevenueError()
        from sklearn.linear_model import LinearRegression

        origin = training[0].day
        features = [self._features(origin, row.day) for row in training]
        return LinearRegression().fit(features, values), origin

    def predict(self, training: Sequence[DailyRevenue], days: Sequence[date]) -> tuple[float, ...]:
        """Fit on training rows and return unfloored estimates for days."""
        if not days:
            return ()
        model, origin = self._fit(training)
        estimates = tuple(
            float(v) for v in model.predict([self._features(origin, d) for d in days])
        )
        if not all(isfinite(value) for value in estimates):
            raise ValueError("predictions must be finite")
        return estimates


class LinearTrendModel(_Regression):
    """Straight line on the day number, the level 2 forecast model."""

    key = "linear_trend"
    title = "Linear trend"
    min_training_days = 5
    explanation = "straight line through daily revenue over time"

    def _features(self, origin: date, day: date) -> list[float]:
        return [float((day - origin).days)]

    def fit_summary(self, training: Sequence[DailyRevenue]) -> FitSummary:
        """Return the fitted revenue change per day."""
        model, _ = self._fit(training)
        return FitSummary(float(model.coef_[0]))


class WeekdayTrendModel(_Regression):
    """Straight line plus one effect per weekday, Monday as the reference."""

    key = "weekday_trend"
    title = "Linear trend + weekday"
    min_training_days = 28
    explanation = "straight line over time plus a typical difference for each weekday"

    def _features(self, origin: date, day: date) -> list[float]:
        weekday = day.weekday()
        return [float((day - origin).days)] + [1.0 if weekday == d else 0.0 for d in range(1, 7)]

    def fit_summary(self, training: Sequence[DailyRevenue]) -> FitSummary:
        """Return the trend per day and the six weekday differences from Monday."""
        model, _ = self._fit(training)
        coefficients = [float(c) for c in model.coef_]
        return FitSummary(coefficients[0], tuple(coefficients[1:]))


DEFAULT_METHODS: tuple[ForecastMethod, ...] = (
    LastValueBaseline(),
    MovingAverageBaseline(7),
    SeasonalNaiveBaseline(7),
    LinearTrendModel(),
    WeekdayTrendModel(),
)
"""Candidates in table order; ties in error go to the earlier (simpler) one."""
