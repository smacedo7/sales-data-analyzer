# Forecast method comparison (level 3)

Menu option `20` compares five interpretable ways of predicting daily revenue on
the selected sales and shows which one made the smallest errors on recent weeks.
It does not replace the level 2 forecast (option `12`), which is unchanged.

## Candidates

| Method | Kind | Rule | Minimum training days |
| --- | --- | --- | --- |
| Last value | baseline | repeats the last known day | 1 |
| 7-day average | baseline | repeats the mean of the last 7 days | 7 |
| Same weekday last week | baseline | repeats the latest value of the same weekday | 14 |
| Linear trend | model | straight line on the day number (as level 2) | 5, varying revenue |
| Linear trend + weekday | model | straight line plus one effect per weekday, Monday as reference | 28, varying revenue |

Baselines have no fitted parameters. They are the benchmarks a model must beat
before it is worth anything. The two models are ordinary least squares
regressions (scikit-learn `LinearRegression`), so their coefficients can be read
directly: "Saturdays sell 40.00 more than Mondays; revenue grows 1.43 per day".

All methods share the `ForecastMethod` interface
(`forecasting/methods.py`), so the comparison treats them polymorphically.

## Chronological evaluation

The comparison uses rolling origins: the last `K` blocks of 7 days are evaluation
blocks. For each block every method is fitted only on the days before it and
predicts the 7 days of the block. No method ever sees a day it is scored on.

- At least **12 days** of history are needed (5 training days + one block).
- `K` is the largest value up to 4 that still leaves enough training days for
  every method that can be evaluated with one block. More blocks therefore never
  exclude a method. Crossing a minimum can change `K`: with 34 days `K = 2`, with
  35 days the weekday model becomes eligible and `K = 1`.
- A method whose minimum is not met is listed as skipped with the total history
  it would need (`minimum + 7 × K`). Regressions on constant revenue are skipped
  too.
- Metrics over all evaluated days: MAE (typical miss in revenue units), RMSE
  (weighs large misses more) and the MAE divided by the last-value MAE (below 1
  means lower error here; "n/a" when the last value made no error).
- Ties go to the simpler method (table order above).

## Honest wording

- A lowest-error method is named only with at least **14 evaluated days**
  (`K ≥ 2`). With fewer, the table is shown, nothing is named and the estimates
  use the last-value baseline unless the user picks another method.
- "No model beat the best baseline" is printed unless a model has a strictly
  lower MAE than the best baseline.
- A difference under **5 %** of the best baseline's MAE is reported as "no clear
  difference".
- Negative estimates are floored at 0 in evaluation and output; the number of
  floored evaluation days is reported and floored future days are marked.
  Flooring can only lower the error of the trend models, a small bias in their
  favour that is disclosed here.
- With "treat missing days as zero", the number of filled days is printed:
  weekly methods learn from those zeros.
- Errors are measured 7 days ahead; horizons above 14 days print an extrapolation
  warning.

## Limitations

Past errors do not guarantee future accuracy. Choosing the lowest error on the
same days that measure it is optimistic; a separate final hold-out would need
more history than most demo datasets have. Holidays, promotions and prices are
not modeled, and no confidence intervals are produced. Days follow the level 2
rules: local calendar days for timestamps without offset, and days of a chosen
UTC offset for data with offsets.
