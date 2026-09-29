from typing import ClassVar
from .validation import validate_non_empty_string


class Company:
    _next_id: ClassVar[int] = 1

    def __init__(self, name: str, sector: str) -> None:
        self.name = name
        self.sector = sector

        self._id = Company._next_id
        Company._next_id += 1

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = validate_non_empty_string(name, "name")

    @property
    def sector(self):
        return self._sector

    @sector.setter
    def sector(self, sector):
        self._sector = validate_non_empty_string(sector, "sector")

    @property
    def id(self):
        return self._id

    def __repr__(self):
        return f'Name: {self._name}, Sector: {self._sector}'
