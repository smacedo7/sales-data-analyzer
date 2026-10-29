"""SQLite schema version 1 as SQLAlchemy Core metadata.

Tables are STRICT, so every column needs a SQLite type name such as TEXT or
INTEGER (`sa.Text`, never `sa.String`, which compiles to VARCHAR). Amounts are
TEXT in plain decimal notation: SQLite has no exact decimal type, and
`sa.Numeric` reads values back through floating point. Surrogate `id` columns
exist only for foreign keys and insertion order; users never see them.
"""

import sqlalchemy as sa

SCHEMA_VERSION = 1
"""Value of `PRAGMA user_version` for databases created by this program."""

APPLICATION_ID = 0x53414441
"""Value of `PRAGMA application_id` (ASCII "SADA") identifying our database files."""


def _not_blank(column: str) -> sa.CheckConstraint:
    """Require a non-empty value after trimming spaces."""
    return sa.CheckConstraint(f"length(trim({column})) > 0", name=f"{column}_not_blank")


def _plain_decimal(column: str) -> sa.CheckConstraint:
    """Require digits with at most one inner dot, as written by `format(amount, "f")`."""
    return sa.CheckConstraint(
        f"{column} GLOB '[0-9]*' AND {column} NOT GLOB '*[^0-9.]*' "
        f"AND {column} NOT GLOB '*.*.*' AND {column} NOT GLOB '*.'",
        name=f"{column}_plain_decimal",
    )


metadata = sa.MetaData()

company = sa.Table(
    "company",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("name_key", sa.Text, nullable=False, unique=True),
    sa.Column("sector", sa.Text, nullable=False),
    _not_blank("name"),
    _not_blank("sector"),
    sqlite_strict=True,
)

product = sa.Table(
    "product",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column(
        "company_id", sa.Integer, sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column("code", sa.Text, nullable=False),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("category", sa.Text, nullable=False),
    _not_blank("code"),
    _not_blank("name"),
    _not_blank("category"),
    sa.UniqueConstraint("company_id", "code"),
    sa.UniqueConstraint("id", "company_id"),
    sqlite_strict=True,
)

sale = sa.Table(
    "sale",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column(
        "company_id", sa.Integer, sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column("code", sa.Text, nullable=False),
    sa.Column("occurred_at", sa.Text, nullable=False),
    _not_blank("code"),
    sa.CheckConstraint("length(occurred_at) >= 19", name="occurred_at_iso"),
    sa.UniqueConstraint("company_id", "code"),
    sa.UniqueConstraint("id", "company_id"),
    sqlite_strict=True,
)

sale_item = sa.Table(
    "sale_item",
    metadata,
    sa.Column("sale_id", sa.Integer, nullable=False),
    sa.Column("position", sa.Integer, nullable=False),
    sa.Column("company_id", sa.Integer, nullable=False),
    sa.Column("product_id", sa.Integer, nullable=False),
    sa.Column("quantity", sa.Integer, nullable=False),
    sa.Column("unit_price", sa.Text, nullable=False),
    sa.Column("unit_cost", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("sale_id", "position"),
    sa.CheckConstraint("position >= 1", name="position_positive"),
    sa.CheckConstraint("quantity > 0", name="quantity_positive"),
    _plain_decimal("unit_price"),
    _plain_decimal("unit_cost"),
    # Composite keys make an item's sale and product belong to the same company.
    sa.ForeignKeyConstraint(
        ["sale_id", "company_id"], ["sale.id", "sale.company_id"], ondelete="CASCADE"
    ),
    sa.ForeignKeyConstraint(
        ["product_id", "company_id"], ["product.id", "product.company_id"], ondelete="RESTRICT"
    ),
    sa.Index("sale_item_product", "product_id", "company_id"),
    sqlite_strict=True,
)
