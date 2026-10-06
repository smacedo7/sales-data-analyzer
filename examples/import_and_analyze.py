"""Run the small Level 1 CSV demonstration from any working directory."""
from pathlib import Path
from sales_data_analyzer.analysis import Analysis, FinancialAnalysis, ProductAnalysis
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.importing import CSVImporter, DataImporter


def main() -> None:
    """Import synthetic sales and exercise both abstract contracts."""
    importer: DataImporter = CSVImporter()
    data = importer.load(Path(__file__).resolve().parents[1] / "tests/fixtures/valid_sales.csv",
                         Company("Example shop", "Retail"))
    print(f"Sales: {len(data.sales)}; items: {sum(len(s.items) for s in data.sales)}")
    analyses: tuple[Analysis, ...] = (FinancialAnalysis(), ProductAnalysis())
    for analysis in analyses:
        print(analysis.run(data))


if __name__ == "__main__":
    main()
