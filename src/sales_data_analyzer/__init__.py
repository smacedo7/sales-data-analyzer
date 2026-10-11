"""Sales Data Analyzer: sales domain, CSV import, analyses and forecasting."""


def main() -> None:
    """Console-script entry point: run the terminal menu and exit with its status."""
    from sales_data_analyzer.cli import run

    raise SystemExit(run())
