"""Rolling-origin comparison of forecast methods against simple baselines.

The last K blocks of 7 days are evaluation blocks. For each block every method is
fitted only on the days before the block and predicts its 7 days. K is the largest
value up to `max_blocks` that still leaves enough training days for every method
that can be evaluated at all (K = 1), so more blocks never exclude a method.
Estimates are floored at zero (revenue cannot be negative) in evaluation and in the
future estimates, and every floored value is reported. A lowest-error method is
named only with at least 14 evaluated days; choosing it on the same days that
measure it is optimistic, and no confidence interval is produced.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from math import isfinite, sqrt
from typing import Literal

from . import DailyRevenue, Prediction
from .methods import DEFAULT_METHODS, ConstantRevenueError, FitSummary, ForecastMethod

MIN_HISTORY_DAYS = 12
"""Shortest history compared: the linear trend's 5 training days plus one 7-day block."""

MIN_EVIDENCE_DAYS = 14
"""Evaluated days needed before a lowest-error method is named."""

CLEAR_DIFFERENCE = 0.05
"""Differences under this share of the best baseline's MAE are not called clear."""

MAX_VALIDATED_HORIZON = 14
"""Horizons beyond this many days are extrapolation and get a warning."""

FALLBACK_METHOD = "last_value"
"""Method used for estimates when the evidence is too limited to name one."""


@dataclass(frozen=True)
class MethodScore:
    """Errors of one method over all evaluated days, in revenue units."""

    method_key: str
    title: str
    kind: Literal["baseline", "model"]
    mae: float
    rmse: float
    relative_mae: float | None
    evaluated_days: int


@dataclass(frozen=True)
class SkippedMethod:
    """A method left out of the comparison and why."""

    method_key: str
    title: str
    reason: Literal["insufficient_history", "constant_revenue"]
    needed_days: int | None


@dataclass(frozen=True)
class ComparisonResult:
    """Evaluation table, flags for honest wording and the chosen method's estimates.

    relative_mae is the MAE divided by the last-value baseline's MAE (None when that
    is zero). `chosen_key` is the method behind `future`: the one requested, else the
    lowest-error one, else the last-value baseline.
    """

    history_days: int
    first_day: date
    last_day: date
    blocks: int
    block_days: int
    origins: tuple[date, ...]
    scores: tuple[MethodScore, ...]
    skipped: tuple[SkippedMethod, ...]
    lowest_error_key: str | None
    model_beats_baselines: bool
    clear_difference: bool
    weak_evidence: bool
    evaluated_days: int
    zero_filled_days: int
    floored_evaluation_days: int
    chosen_key: str
    chosen_title: str
    future: tuple[Prediction, ...]
    floored_future_days: tuple[date, ...]
    extrapolation_warning: bool
    fit: FitSummary | None


def _block_count(
    n: int, methods: Sequence[ForecastMethod], block_days: int, max_blocks: int
) -> int:
    """Return K: the most blocks that keep every method evaluable at K = 1."""
    eligible = [m.min_training_days for m in methods if m.min_training_days <= n - block_days]
    need = max(eligible, default=1)
    blocks = 1
    for k in range(2, max_blocks + 1):
        if n - k * block_days >= need:
            blocks = k
    return blocks


def _floored(values: Sequence[float]) -> tuple[list[float], list[int]]:
    """Return values floored at zero and the positions that were negative."""
    return [max(v, 0.0) for v in values], [i for i, v in enumerate(values) if v < 0]


def compare_methods(
    history: Sequence[DailyRevenue],
    *,
    horizon: int = 7,
    methods: Sequence[ForecastMethod] = DEFAULT_METHODS,
    block_days: int = 7,
    max_blocks: int = 4,
    method: str | None = None,
    zero_filled_days: int = 0,
) -> ComparisonResult:
    """Evaluate methods on the last blocks of history, then forecast horizon days.

    history must be contiguous daily rows (as returned by `daily_revenue`).
    zero_filled_days is only reported: how many history days were filled with zero.
    Raise TypeError for wrong types and ValueError for fewer than 12 days, a
    horizon outside 1-365, an unknown or unscored method key, or a horizon past
    the last calendar day.
    """
    history = tuple(history)
    if not all(isinstance(row, DailyRevenue) for row in history):
        raise TypeError("history must contain DailyRevenue rows")
    if isinstance(horizon, bool) or not isinstance(horizon, int):
        raise TypeError("horizon must be an integer")
    if not 1 <= horizon <= 365:
        raise ValueError("horizon must be from 1 to 365 days")
    n = len(history)
    if n < MIN_HISTORY_DAYS:
        raise ValueError(f"the comparison needs at least {MIN_HISTORY_DAYS} days of history")
    if any(b.day - a.day != timedelta(days=1) for a, b in zip(history, history[1:], strict=False)):
        raise ValueError("history must have one row per consecutive day")
    try:
        future_days = tuple(history[-1].day + timedelta(days=i) for i in range(1, horizon + 1))
    except OverflowError:
        raise ValueError("history or horizon exceeds numeric/calendar range") from None

    blocks = _block_count(n, methods, block_days, max_blocks)
    starts = [n - k * block_days for k in range(blocks, 0, -1)]
    actual = [float(row.revenue) for start in starts for row in history[start : start + block_days]]

    errors: dict[str, list[float]] = {}
    skipped: list[SkippedMethod] = []
    floored_days: set[date] = set()
    for candidate in methods:
        if candidate.min_training_days > starts[0]:
            needed = candidate.min_training_days + blocks * block_days
            skipped.append(
                SkippedMethod(candidate.key, candidate.title, "insufficient_history", needed)
            )
            continue
        try:
            predicted: list[float] = []
            for start in starts:
                days = [row.day for row in history[start : start + block_days]]
                values, negative = _floored(candidate.predict(history[:start], days))
                floored_days.update(days[i] for i in negative)
                predicted += values
        except ConstantRevenueError:
            skipped.append(SkippedMethod(candidate.key, candidate.title, "constant_revenue", None))
            continue
        errors[candidate.key] = [a - p for a, p in zip(actual, predicted, strict=True)]

    by_key = {m.key: m for m in methods}
    order = {m.key: i for i, m in enumerate(methods)}
    raw = {key: _mae_rmse(diffs) for key, diffs in errors.items()}
    base = raw.get(FALLBACK_METHOD, (None, None))[0]
    scores = tuple(
        sorted(
            (
                MethodScore(
                    key, by_key[key].title, by_key[key].kind, mae, rmse,
                    mae / base if base else None, len(actual),
                )
                for key, (mae, rmse) in raw.items()
            ),
            key=lambda s: (s.mae, order[s.method_key]),
        )
    )  # fmt: skip

    evaluated = len(actual)
    weak = evaluated < MIN_EVIDENCE_DAYS
    lowest = scores[0].method_key if scores and not weak else None
    best_baseline = next((s for s in scores if s.kind == "baseline"), None)
    best_model = next((s for s in scores if s.kind == "model"), None)
    beats = clear = False
    if best_baseline is not None and best_model is not None:
        beats = best_model.mae < best_baseline.mae
        clear = abs(best_model.mae - best_baseline.mae) >= CLEAR_DIFFERENCE * best_baseline.mae
        clear = clear and best_model.mae != best_baseline.mae

    if method is not None:
        if method not in raw:
            raise ValueError("the chosen method was not evaluated")
        chosen_key = method
    else:
        chosen_key = lowest or FALLBACK_METHOD
    if chosen_key not in by_key:
        raise ValueError("the last-value baseline must be among the methods")
    chosen = by_key[chosen_key]
    future_values, future_negative = _floored(chosen.predict(history, future_days))
    future = tuple(Prediction(d, v) for d, v in zip(future_days, future_values, strict=True))

    return ComparisonResult(
        history_days=n,
        first_day=history[0].day,
        last_day=history[-1].day,
        blocks=blocks,
        block_days=block_days,
        origins=tuple(history[start].day for start in starts),
        scores=scores,
        skipped=tuple(skipped),
        lowest_error_key=lowest,
        model_beats_baselines=beats,
        clear_difference=clear,
        weak_evidence=weak,
        evaluated_days=evaluated,
        zero_filled_days=zero_filled_days,
        floored_evaluation_days=len(floored_days),
        chosen_key=chosen_key,
        chosen_title=chosen.title,
        future=future,
        floored_future_days=tuple(future_days[i] for i in future_negative),
        extrapolation_warning=horizon > MAX_VALIDATED_HORIZON,
        fit=chosen.fit_summary(history),
    )


def _mae_rmse(differences: Sequence[float]) -> tuple[float, float]:
    """Return finite MAE and RMSE of the errors."""
    mae = sum(abs(d) for d in differences) / len(differences)
    rmse = sqrt(sum(d * d for d in differences) / len(differences))
    if not isfinite(mae) or not isfinite(rmse):
        raise ValueError("evaluation errors exceed finite floating-point range")
    return mae, rmse
