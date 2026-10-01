from .company import Company
from .validation import validate_non_empty_string


class Product:
    """A catalog product belonging to one company."""

    def __init__(self, id: str, company: Company, name: str, category: str) -> None:
        self._id = validate_non_empty_string(id, "id")
        if not isinstance(company, Company):
            raise TypeError("company must be a Company")
        self._company = company
        self.name = name
        self.category = category

    @property
    def id(self) -> str:
        return self._id

    @property
    def company(self) -> Company:
        return self._company

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = validate_non_empty_string(value, "name")

    @property
    def category(self) -> str:
        return self._category

    @category.setter
    def category(self, value: str) -> None:
        self._category = validate_non_empty_string(value, "category")

    def __repr__(self) -> str:
        return (
            f"Product(id={self.id!r}, name={self.name!r}, "
            f"category={self.category!r}, company_id={self.company.id!r})"
        )
