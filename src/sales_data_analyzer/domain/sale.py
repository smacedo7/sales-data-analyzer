from datetime import datetime
from decimal import Decimal

from .company import Company
from .product import Product
from .sale_item import SaleItem
from .validation import validate_non_empty_string


class Sale:
    """A transaction owning its items; identity and timestamp are read-only."""

    def __init__(self, id: str, company: Company, date_time: datetime) -> None:
        self._id = validate_non_empty_string(id, "id")
        if not isinstance(company, Company):
            raise TypeError("company must be a Company")
        if not isinstance(date_time, datetime):
            raise TypeError("date_time must be a datetime")
        self._company = company
        self._date_time = date_time
        self._items: list[SaleItem] = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def company(self) -> Company:
        return self._company

    @property
    def date_time(self) -> datetime:
        return self._date_time

    @property
    def items(self) -> tuple[SaleItem, ...]:
        return tuple(self._items)

    def add_item(
        self, product: Product, quantity: int,
        unit_price: Decimal, unit_cost: Decimal,
    ) -> None:
        if not isinstance(product, Product):
            raise TypeError("product must be a Product")
        if product.company is not self.company:
            raise ValueError("product must belong to the sale company")
        item = SaleItem(product, quantity, unit_price, unit_cost)
        self._items.append(item)

    def calculate_total(self) -> Decimal:
        return sum((item.calculate_subtotal() for item in self._items), Decimal("0"))

    def calculate_cost(self) -> Decimal:
        return sum((item.calculate_cost() for item in self._items), Decimal("0"))
