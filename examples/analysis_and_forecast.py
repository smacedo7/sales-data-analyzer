"""Run deterministic accounting and daily revenue forecasting without downloads."""
from datetime import datetime, timedelta
from decimal import Decimal

from sales_data_analyzer.analysis import FinancialAnalysis, ProductAnalysis
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.domain.sales_dataset import SalesDataset
from sales_data_analyzer.forecasting import RevenueForecaster


def main() -> None:
    """Build fourteen synthetic days, print analyses, evaluation and future values."""
    company = Company("Example shop", "Retail")
    product = Product("coffee", company, "Coffee", "Beverages")
    data = SalesDataset(company)
    for day in range(14):
        sale = Sale(str(day), company, datetime(2026, 1, 1) + timedelta(days=day))
        sale.add_item(product, day + 1, Decimal("10"), Decimal("4"))
        data.add_sale(sale)
    for analysis in (FinancialAnalysis(), ProductAnalysis()):
        print(analysis.run(data))
    forecast = RevenueForecaster().forecast(data, horizon=3, test_days=3)
    print("Model errors:", forecast.model_errors)
    print("Last-training-day baseline errors:", forecast.baseline_errors)
    print("Future predictions:", forecast.future)


if __name__ == "__main__":
    main()
