from decimal import Decimal

from .product import Product


def _validate_amount(value: Decimal, name: str) -> Decimal:
    """Require finite Decimal amounts to avoid implicit float rounding."""
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal")
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


class SaleItem:
    """A product reference with read-only quantity and historical amounts.

    Sale will create and own these items through add_item(). Product catalog
    changes do not replace the historical price and cost stored here.
    """

    def __init__(
        self,
        product: Product,
        quantity: int,
        unit_price: Decimal,
        unit_cost: Decimal,
    ) -> None:
        if not isinstance(product, Product):
            raise TypeError("product must be a Product")
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise TypeError("quantity must be an integer")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        self._product = product
        self._quantity = quantity
        self._unit_price = _validate_amount(unit_price, "unit_price")
        self._unit_cost = _validate_amount(unit_cost, "unit_cost")

    @property
    def product(self) -> Product:
        return self._product

    @property
    def quantity(self) -> int:
        return self._quantity

    @property
    def unit_price(self) -> Decimal:
        return self._unit_price

    @property
    def unit_cost(self) -> Decimal:
        return self._unit_cost

    def calculate_subtotal(self) -> Decimal:
        return self.quantity * self.unit_price

    def calculate_cost(self) -> Decimal:
        return self.quantity * self.unit_cost

    def __repr__(self) -> str:
        return (
            f"SaleItem(product_id={self.product.id!r}, quantity={self.quantity!r}, "
            f"unit_price={self.unit_price!r}, unit_cost={self.unit_cost!r})"
        )
