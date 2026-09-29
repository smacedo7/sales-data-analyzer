from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class Company:
    name: str
    sector: str
    id: int = field(init=False)

    _next_id: ClassVar[int] = 1

    def __post_init__(self) -> None:
        self.id = Company._next_id
        Company._next_id += 1
