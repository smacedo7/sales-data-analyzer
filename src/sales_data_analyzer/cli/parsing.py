"""Convert typed terminal text into domain values without float conversion.

Accepted formats mirror the CSV import (`docs/csv-import.md`) so that a value
valid in a file is valid at the prompt and vice versa.
"""

import os
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?")
_AMOUNT = re.compile(r"[+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_OFFSET = re.compile(r"([+-])(\d{2}):(\d{2})")
_INTEGER = re.compile(r"[0-9]+")


class InputError(ValueError):
    """Typed text does not match the expected format; message says what is expected."""


def parse_text(text: str) -> str:
    """Return trimmed non-empty text or raise InputError."""
    value = text.strip()
    if not value:
        raise InputError("a non-empty value is required")
    return value


def parse_positive_int(text: str, *, maximum: int | None = None) -> int:
    """Return a positive integer (optionally at most maximum) from ASCII digits."""
    value = text.strip()
    limit = f" up to {maximum}" if maximum is not None else ""
    if not _INTEGER.fullmatch(value) or int(value) < 1:
        raise InputError(f"expected a positive whole number{limit}")
    number = int(value)
    if maximum is not None and number > maximum:
        raise InputError(f"expected a positive whole number{limit}")
    return number


def parse_amount(text: str) -> Decimal:
    """Return a finite non-negative Decimal written in plain notation, like 10.50."""
    value = text.strip()
    if not _AMOUNT.fullmatch(value):
        raise InputError("expected a non-negative decimal such as 10.50 (no separators)")
    try:
        return Decimal(value)
    except InvalidOperation:
        raise InputError("expected a non-negative decimal such as 10.50") from None


def parse_date(text: str) -> date:
    """Return a calendar date written as YYYY-MM-DD, up to 9999-12-30."""
    value = text.strip()
    if not _DATE.fullmatch(value):
        raise InputError("expected a date as YYYY-MM-DD")
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise InputError("expected a valid calendar date as YYYY-MM-DD") from None
    if day == date.max:
        raise InputError("dates must be on or before 9999-12-30")
    return day


def parse_datetime(text: str) -> datetime:
    """Return a datetime as YYYY-MM-DDTHH:MM:SS with optional fraction and offset.

    Offsets are kept; normalizing to UTC is the application's responsibility.
    """
    value = text.strip()
    expected = "expected YYYY-MM-DDTHH:MM:SS with optional fraction and Z or +HH:MM"
    if not _DATETIME.fullmatch(value):
        raise InputError(expected)
    try:
        if value[-6:-5] in ("+", "-") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
            raise ValueError
        return datetime.fromisoformat(value)
    except ValueError, OverflowError:
        raise InputError("invalid calendar date or UTC offset") from None


def parse_utc_offset(text: str) -> timedelta:
    """Return a fixed UTC offset written as +HH:MM or -HH:MM."""
    match = _OFFSET.fullmatch(text.strip())
    if not match or int(match[2]) > 23 or int(match[3]) > 59:
        raise InputError("expected a UTC offset such as -03:00 or +00:00")
    offset = timedelta(hours=int(match[2]), minutes=int(match[3]))
    return -offset if match[1] == "-" else offset


def parse_yes_no(text: str) -> bool:
    """Return True for y/yes, False for n/no or blank (case-insensitive)."""
    value = text.strip().lower()
    if value in ("y", "yes"):
        return True
    if value in ("", "n", "no"):
        return False
    raise InputError("answer y or n")


def parse_path(text: str, *, posix: bool | None = None) -> Path:
    """Return a path typed or dropped into the terminal.

    One pair of matching surrounding quotes is removed (Windows drag and drop).
    On POSIX systems, backslash-escaped spaces from macOS Terminal drag and drop
    are unescaped when the path is not quoted.
    """
    value = parse_text(text)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return Path(value[1:-1])
    if posix if posix is not None else os.name == "posix":
        value = value.replace("\\ ", " ")
    return Path(value)
