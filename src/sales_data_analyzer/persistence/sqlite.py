"""SQLite storage through SQLAlchemy Core (no ORM).

The domain classes are rebuilt through their constructors when loading, so every
stored row passes the same validation as new data. Each write runs in one
`BEGIN IMMEDIATE` transaction and is rolled back completely on any failure.
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import sqlite3
import sys
from typing import Self

import sqlalchemy as sa
from sqlalchemy import event

from sales_data_analyzer.application.errors import ConcurrentChangeError, PersistenceError
from sales_data_analyzer.application.repository import SalesRepository, StoredCompany
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.domain.sales_dataset import SalesDataset

from . import schema

BUSY_TIMEOUT_SECONDS = 2.0
"""How long a write waits for another connection's lock before giving up."""

_MIN_SQLITE = (3, 37, 0)  # first version with STRICT tables


class DatabaseOpenError(Exception):
    """Raised when start-up cannot use a database file; the file is left unchanged.

    The message states the reason without the file path.
    """


class CorruptDataError(DatabaseOpenError):
    """Raised when stored rows violate domain rules; nothing is loaded."""

    def __init__(self, table: str, count: int) -> None:
        self.table = table
        self.count = count
        super().__init__(f"{count} invalid row(s) in {table}")


def default_database_path(
    *,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the per-user database file in the operating system's application data folder.

    macOS uses ~/Library/Application Support, Windows uses %LOCALAPPDATA% (or
    ~/AppData/Local) and other systems use $XDG_DATA_HOME (or ~/.local/share).
    Arguments exist for tests; by default the running system is inspected.
    """
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home
    if platform == "darwin":
        folder = home / "Library" / "Application Support" / "Sales Data Analyzer"
    elif platform.startswith("win"):
        local = environ.get("LOCALAPPDATA")
        folder = (Path(local) if local else home / "AppData" / "Local") / "Sales Data Analyzer"
    else:
        data_home = environ.get("XDG_DATA_HOME")
        base = Path(data_home) if data_home and Path(data_home).is_absolute() else None
        folder = (base or home / ".local" / "share") / "sales-data-analyzer"
    return folder / "sales.sqlite3"


def _amount_text(amount: Decimal) -> str:
    """Return the plain-decimal text stored for a validated non-negative amount."""
    return format(amount.copy_abs(), "f")  # copy_abs only turns -0 into 0


class SQLiteSalesRepository(SalesRepository):
    """Repository over one SQLite file; use `open()` to create instances."""

    def __init__(self, engine: sa.Engine, path: Path) -> None:
        """Wrap an engine already configured and checked by `open()`."""
        self._engine = engine
        self._path = path
        self._company_ids: dict[Company, int] = {}

    # -- opening ------------------------------------------------------------------

    @classmethod
    def open(cls, path: str | Path) -> Self:
        """Open or create the database at path and check that it belongs to this program.

        A missing parent folder is created. A new or empty file receives the schema.
        Raise DatabaseOpenError for files that are not databases, belong to another
        application, come from a newer version or cannot be read; such files are not
        modified. Loading happens separately in `load()`.
        """
        if sqlite3.sqlite_version_info < _MIN_SQLITE:
            raise DatabaseOpenError("the SQLite library is older than 3.37")
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise DatabaseOpenError("the database folder cannot be created") from None
        if path.is_dir():
            raise DatabaseOpenError("the database path is a folder")
        engine = sa.create_engine(
            sa.URL.create("sqlite", database=str(path)),
            connect_args={"timeout": BUSY_TIMEOUT_SECONDS},
        )
        event.listen(engine, "connect", _configure_connection)
        event.listen(engine, "begin", _begin_immediate)
        repository = cls(engine, path)
        try:
            repository._prepare()
        except sa.exc.DatabaseError as error:
            engine.dispose()
            reason = "the file is not a database" if _not_a_database(error) else "it cannot be read"
            raise DatabaseOpenError(reason) from None
        except BaseException:
            engine.dispose()  # never leave the file open (Windows could not delete it)
            raise
        return repository

    def _prepare(self) -> None:
        """Verify connection settings, then create the schema or check the existing one."""
        with self._engine.connect() as connection:
            if connection.exec_driver_sql("PRAGMA foreign_keys").scalar() != 1:
                raise DatabaseOpenError("foreign keys cannot be enabled")
            application_id = connection.exec_driver_sql("PRAGMA application_id").scalar()
            version = connection.exec_driver_sql("PRAGMA user_version").scalar()
            tables = connection.exec_driver_sql(
                "SELECT count(*) FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'"
            ).scalar()
        if application_id == 0 and version == 0 and tables == 0:
            with self._engine.begin() as connection:
                schema.metadata.create_all(connection)
                connection.exec_driver_sql(f"PRAGMA application_id = {schema.APPLICATION_ID}")
                connection.exec_driver_sql(f"PRAGMA user_version = {schema.SCHEMA_VERSION}")
            return
        if application_id != schema.APPLICATION_ID:
            raise DatabaseOpenError("it is not a Sales Data Analyzer database")
        if version > schema.SCHEMA_VERSION:
            raise DatabaseOpenError("it was created by a newer version of the program")
        if version < schema.SCHEMA_VERSION:
            raise DatabaseOpenError("its schema version is not supported")

    @property
    def location(self) -> str:
        """Return the database file path as given to `open()`."""
        return str(self._path)

    def close(self) -> None:
        """Close every pooled connection."""
        self._engine.dispose()

    # -- loading ------------------------------------------------------------------

    def load(self) -> tuple[StoredCompany, ...]:
        """Rebuild every company through domain constructors, in creation order.

        Sales keep insertion order (`sale.id`), items keep their position, and each
        product exists once per company so catalog and items share it. Raise
        CorruptDataError naming the first table with invalid rows; nothing is
        returned in that case.
        """
        with self._engine.begin() as connection:
            company_rows = connection.execute(
                sa.select(schema.company).order_by(schema.company.c.id)
            ).all()
            product_rows = connection.execute(
                sa.select(schema.product).order_by(
                    schema.product.c.company_id, schema.product.c.code
                )
            ).all()
            sale_rows = connection.execute(sa.select(schema.sale).order_by(schema.sale.c.id)).all()
            item_rows = connection.execute(
                sa.select(schema.sale_item).order_by(
                    schema.sale_item.c.sale_id, schema.sale_item.c.position
                )
            ).all()

        companies: dict[int, Company] = {}
        invalid = 0
        for row in company_rows:
            try:
                companies[row.id] = Company(row.name, row.sector)
            except TypeError, ValueError:
                invalid += 1
        _raise_if_invalid("company", invalid)

        products: dict[int, Product] = {}
        catalogs: dict[int, list[Product]] = {key: [] for key in companies}
        for row in product_rows:
            try:
                item = Product(row.code, companies[row.company_id], row.name, row.category)
            except TypeError, ValueError, KeyError:
                invalid += 1
                continue
            products[row.id] = item
            catalogs[row.company_id].append(item)
        _raise_if_invalid("product", invalid)

        sales: dict[int, Sale] = {}
        for row in sale_rows:
            try:
                sales[row.id] = Sale(
                    row.code, companies[row.company_id], datetime.fromisoformat(row.occurred_at)
                )
            except TypeError, ValueError, KeyError:
                invalid += 1
        _raise_if_invalid("sale", invalid)

        for row in item_rows:
            try:
                sales[row.sale_id].add_item(
                    products[row.product_id],
                    row.quantity,
                    Decimal(row.unit_price),
                    Decimal(row.unit_cost),
                )
            except TypeError, ValueError, KeyError, InvalidOperation:
                invalid += 1
        _raise_if_invalid("sale_item", invalid)

        datasets = {key: SalesDataset(company) for key, company in companies.items()}
        for row in sale_rows:
            try:
                datasets[row.company_id].add_sale(sales[row.id])
            except TypeError, ValueError:
                invalid += 1
        _raise_if_invalid("sale", invalid)

        self._company_ids = {company: key for key, company in companies.items()}
        return tuple(
            StoredCompany(company, tuple(catalogs[key]), datasets[key])
            for key, company in companies.items()
        )

    # -- writing ------------------------------------------------------------------

    def add_company(self, company: Company) -> None:
        """Insert a company; it is registered for later writes only after COMMIT."""
        with self._transaction() as connection:
            result = connection.execute(
                schema.company.insert().values(
                    name=company.name, name_key=company.name.casefold(), sector=company.sector
                )
            )
            (row_id,) = result.inserted_primary_key
        self._company_ids[company] = row_id

    def update_company(self, company: Company, name: str, sector: str) -> None:
        """Rewrite the name, its case-insensitive key and the sector of a registered company."""
        company_id = self._company_id(company)
        with self._transaction() as connection:
            result = connection.execute(
                schema.company.update()
                .where(schema.company.c.id == company_id)
                .values(name=name, name_key=name.casefold(), sector=sector)
            )
            _require_one_row(result)

    def add_product(self, company: Company, product: Product) -> None:
        """Insert one catalog product of a registered company."""
        company_id = self._company_id(company)
        with self._transaction() as connection:
            connection.execute(schema.product.insert(), [_product_row(company_id, product)])

    def update_product(self, company: Company, product_id: str, name: str, category: str) -> None:
        """Rewrite the name and category of one catalog product."""
        company_id = self._company_id(company)
        with self._transaction() as connection:
            result = connection.execute(
                schema.product.update()
                .where(
                    schema.product.c.company_id == company_id,
                    schema.product.c.code == product_id,
                )
                .values(name=name, category=category)
            )
            _require_one_row(result)

    def delete_product(self, company: Company, product_id: str) -> None:
        """Delete one catalog product; the schema refuses it while items reference it."""
        company_id = self._company_id(company)
        with self._transaction() as connection:
            result = connection.execute(
                schema.product.delete().where(
                    schema.product.c.company_id == company_id,
                    schema.product.c.code == product_id,
                )
            )
            _require_one_row(result)

    def add_sales(
        self, company: Company, new_products: Sequence[Product], sales: Sequence[Sale]
    ) -> None:
        """Insert new products, then sales and their items, all in one transaction."""
        company_id = self._company_id(company)
        with self._transaction() as connection:
            if new_products:
                connection.execute(
                    schema.product.insert(),
                    [_product_row(company_id, product) for product in new_products],
                )
            product_ids = {
                row.code: row.id
                for row in connection.execute(
                    sa.select(schema.product.c.code, schema.product.c.id).where(
                        schema.product.c.company_id == company_id
                    )
                )
            }
            for sale in sales:
                result = connection.execute(
                    schema.sale.insert().values(
                        company_id=company_id,
                        code=sale.id,
                        occurred_at=sale.date_time.isoformat(),
                    )
                )
                (sale_id,) = result.inserted_primary_key
                self._insert_items(connection, company_id, sale_id, sale, product_ids)

    def delete_sale(self, company: Company, sale_id: str) -> None:
        """Delete one sale; its items go with it (ON DELETE CASCADE)."""
        company_id = self._company_id(company)
        with self._transaction() as connection:
            result = connection.execute(
                schema.sale.delete().where(
                    schema.sale.c.company_id == company_id, schema.sale.c.code == sale_id
                )
            )
            _require_one_row(result)

    def _insert_items(
        self,
        connection: sa.Connection,
        company_id: int,
        sale_id: int,
        sale: Sale,
        product_ids: Mapping[str, int],
    ) -> None:
        """Insert the items of one stored sale (a seam for failure-injection tests)."""
        connection.execute(
            schema.sale_item.insert(),
            [
                {
                    "sale_id": sale_id,
                    "position": position,
                    "company_id": company_id,
                    "product_id": product_ids[item.product.id],
                    "quantity": item.quantity,
                    "unit_price": _amount_text(item.unit_price),
                    "unit_cost": _amount_text(item.unit_cost),
                }
                for position, item in enumerate(sale.items, start=1)
            ],
        )

    def _company_id(self, company: Company) -> int:
        """Return the row id of a loaded or added company (LookupError otherwise)."""
        try:
            return self._company_ids[company]
        except KeyError:
            raise LookupError("the company is not stored in this repository") from None

    @contextmanager
    def _transaction(self) -> Iterator[sa.Connection]:
        """Run a block in one write transaction, translating storage failures.

        Integrity violations mean the stored data no longer matches the session
        (another running copy); other database or range failures become
        PersistenceError. Errors raised by the caller's own code pass unchanged.
        """
        try:
            with self._engine.begin() as connection:
                yield connection
        except sa.exc.IntegrityError, sqlite3.IntegrityError:
            raise ConcurrentChangeError() from None
        except sa.exc.OperationalError as error:
            if "locked" in str(error.orig) or "busy" in str(error.orig):
                raise PersistenceError(
                    "the database is busy; another copy of the program may be using it"
                ) from None
            raise PersistenceError() from None
        except sa.exc.SQLAlchemyError, sqlite3.Error, OverflowError:
            raise PersistenceError() from None


def _product_row(company_id: int, product: Product) -> dict[str, object]:
    """Return the column values of one product row."""
    return {
        "company_id": company_id,
        "code": product.id,
        "name": product.name,
        "category": product.category,
    }


def _require_one_row(result: sa.CursorResult) -> None:
    """Fail the transaction when an update or delete did not match exactly one row.

    The session only edits rows it loaded, so a missing row means another running
    copy changed the file.
    """
    if result.rowcount != 1:
        raise ConcurrentChangeError()


def _raise_if_invalid(table: str, count: int) -> None:
    """Stop loading when the table just processed had invalid rows."""
    if count:
        raise CorruptDataError(table, count)


def _not_a_database(error: sa.exc.DatabaseError) -> bool:
    """Return True when SQLite reports a file that is not a database."""
    return "not a database" in str(error.orig)


def _configure_connection(dbapi_connection: sqlite3.Connection, _record: object) -> None:
    """Let SQLAlchemy own transactions and enable foreign keys on every connection.

    With the driver's implicit transactions (`isolation_level` not None) a
    transaction is already open and `PRAGMA foreign_keys` would be ignored.
    """
    dbapi_connection.isolation_level = None
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


def _begin_immediate(connection: sa.Connection) -> None:
    """Start every transaction with the write lock so a second writer fails up front."""
    connection.exec_driver_sql("BEGIN IMMEDIATE")
