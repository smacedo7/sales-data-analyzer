"""CSV boundary, atomicity and accounting integration tests."""
import csv
from decimal import Decimal
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sales_data_analyzer.analysis import FinancialAnalysis, ProductAnalysis
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.sales_dataset import SalesDataset
from sales_data_analyzer.importing import CSVImporter, DataImporter, FIELDS, ImportValidationError

FIXTURES = Path(__file__).parent / "fixtures"
BASE = ['001', '2026-01-01T10:00:00', '007', 'Coffee', 'Drinks', '2', '10.10', '4.05']


class ImportTests(unittest.TestCase):
    """Exercise complete files through the public importer contract."""

    def setUp(self) -> None:
        """Create an explicitly owned company and stateless importer."""
        self.company = Company('Shop', 'Retail')
        self.importer: DataImporter = CSVImporter()

    def load_text(self, text: str, encoding: str = 'utf-8') -> SalesDataset:
        """Import a temporary file without retaining test artifacts."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sales.csv'
            path.write_bytes(text.encode(encoding))
            return self.importer.load(path, self.company)

    def text(self, rows: list[list[str]], header: tuple[str, ...] = FIELDS) -> str:
        """Serialize quoted synthetic records."""
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
        return stream.getvalue()

    def test_grouping_precision_identity_and_analyses(self) -> None:
        """Noncontiguous repeated items remain separate and share catalog objects."""
        data = self.importer.load(FIXTURES / 'valid_sales.csv', self.company)
        self.assertEqual([s.id for s in data.sales], ['001', '002'])
        first = data.sales[0]
        self.assertEqual(len(first.items), 2)
        self.assertIs(first.items[0].product, first.items[1].product)
        self.assertIs(data.company, self.company)
        self.assertEqual(first.items[0].product.id, '007')
        self.assertEqual(first.items[0].unit_price, Decimal('10.10'))
        metrics = FinancialAnalysis().run(data).financial
        self.assertEqual((metrics.revenue, metrics.cost, metrics.gross_profit),
                         (Decimal('45.40'), Decimal('18.20'), Decimal('27.20')))
        self.assertEqual(ProductAnalysis().run(data).products[0].quantity, 4)

    def test_invalid_fields(self) -> None:
        """Reject empty fields, nonintegers, unsafe numbers and malformed dates."""
        cases = {f: [''] for f in FIELDS}
        cases['quantity'] += ['0', '-1', '1.5', 'True', '1e2']
        cases['unit_price'] += ['NaN', 'Infinity', '-1', '1,20', '1e2', '1_000']
        cases['unit_cost'] += ['-0.01', 'inf']
        cases['date_time'] += ['2026-02-30T10:00:00', '20260101', '2026-01-01',
                               '2026-01-01T10:00:00+01:60', '2026-01-01T25:00:00']
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    row = BASE.copy()
                    row[FIELDS.index(field)] = value
                    with self.assertRaises(ImportValidationError) as caught:
                        self.load_text(self.text([row]))
                    self.assertEqual((caught.exception.line, caught.exception.field), (2, field))
                    self.assertEqual(self.company.name, 'Shop')

    def test_header_and_record_shape(self) -> None:
        """Reject duplicate/missing/extra columns, empty files and blank records."""
        invalid = ['', self.text([]), self.text([BASE], FIELDS[:-1]),
                   self.text([BASE], FIELDS + ('extra',)),
                   self.text([BASE], FIELDS[:-1] + ('unit_price',)),
                   self.text([BASE[:-1]]), self.text([BASE + ['extra']]),
                   self.text([[]]), ','.join(FIELDS) + '\n"unterminated']
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ImportValidationError):
                self.load_text(text)

    def test_inconsistent_catalog_or_sale(self) -> None:
        """Reject late metadata/timestamp errors without leaking partial datasets."""
        for field, value in [('product', 'Other'), ('category', 'Other'),
                             ('date_time', '2026-01-02T10:00:00')]:
            row = BASE.copy()
            row[FIELDS.index(field)] = value
            with self.subTest(field=field), self.assertRaises(ImportValidationError) as caught:
                self.load_text(self.text([BASE, row]))
            self.assertEqual(caught.exception.line, 3)
        self.assertEqual(len(self.importer.load(FIXTURES / 'valid_sales.csv', self.company).sales), 2)

    def test_timezone_policy(self) -> None:
        """Equal instants with different offsets group; mixed awareness fails."""
        first, second = BASE.copy(), BASE.copy()
        first[1] = '2026-01-01T10:00:00-03:00'
        second[1] = '2026-01-01T13:00:00Z'
        data = self.load_text(self.text([first, second]))
        self.assertEqual(data.sales[0].date_time.hour, 13)
        self.assertEqual(len(data.sales[0].items), 2)
        second[1] = BASE[1]
        with self.assertRaises(ImportValidationError):
            self.load_text(self.text([first, second]))
        second[0], second[1] = '002', '2026-01-02T10:00:00+02:00'
        self.assertEqual(len(self.load_text(self.text([first, second])).sales), 2)

    def test_bom_quotes_multiline_reordered_header_and_zero_money(self) -> None:
        """Accept standard quoting, BOM, reordered columns and zero amounts."""
        row = BASE.copy()
        row[3], row[6], row[7] = 'Coffee, "special"\nblend', '0', '0.00'
        text = self.text([list(reversed(row))], tuple(reversed(FIELDS)))
        data = self.load_text('\ufeff' + text)
        self.assertEqual(data.sales[0].items[0].product.name, row[3])
        self.assertEqual(data.sales[0].calculate_total(), Decimal(0))
        bad = self.text([row, BASE[:-1]])
        with self.assertRaises(ImportValidationError) as caught:
            self.load_text(bad)
        self.assertEqual(caught.exception.line, 4)

    def test_file_errors_and_invalid_fixture(self) -> None:
        """Report missing files, invalid encoding and synthetic invalid records."""
        with tempfile.TemporaryDirectory() as directory:
            for path in (Path(directory), Path(directory) / 'missing'):
                with self.assertRaises(ImportValidationError) as caught:
                    self.importer.load(path, self.company)
                self.assertEqual(caught.exception.field, 'file')
        with self.assertRaises(ImportValidationError):
            self.load_text(self.text([BASE]).replace('Coffee', 'Café'), 'latin1')
        with self.assertRaises(ImportValidationError):
            self.importer.load(FIXTURES / 'invalid_sales.csv', self.company)
        with self.assertRaises(TypeError):
            self.importer.load(FIXTURES / 'valid_sales.csv', None)
        with self.assertRaises(TypeError):
            self.importer.load(None, self.company)
        with self.assertRaises(TypeError):
            DataImporter()

    def test_dependency_isolation(self) -> None:
        """Import and descriptive analyses run with third-party site imports disabled."""
        code = ('from sales_data_analyzer.importing import CSVImporter; '
                'from sales_data_analyzer.analysis import FinancialAnalysis; '
                'from sales_data_analyzer.domain.company import Company; '
                f'd=CSVImporter().load({str(FIXTURES / "valid_sales.csv")!r},Company("Shop","Retail")); '
                'assert FinancialAnalysis().run(d).financial.sale_count == 2; '
                'import sys; assert "sklearn" not in sys.modules')
        subprocess.run([sys.executable, '-S', '-c', code], check=True)


class CompanyTests(unittest.TestCase):
    """Cover business identity and safe setter validation."""

    def test_identity_and_normalization(self) -> None:
        """Company IDs are distinct and text is normalized."""
        first, second = Company(' Shop ', ' Retail '), Company('Shop', 'Retail')
        self.assertNotEqual(first.id, second.id)
        self.assertEqual((first.name, first.sector), ('Shop', 'Retail'))

    def test_invalid_creation_and_setters(self) -> None:
        """Reject invalid business strings and preserve old values on failed setters."""
        company = Company('Shop', 'Retail')
        for field in ('name', 'sector'):
            for value in ('', '  ', None, 1):
                with self.subTest(field=field, value=value), self.assertRaises((TypeError, ValueError)):
                    setattr(company, field, value)
        self.assertEqual((company.name, company.sector), ('Shop', 'Retail'))
        for args in (('', 'Retail'), ('Shop', None)):
            with self.assertRaises((TypeError, ValueError)):
                Company(*args)
