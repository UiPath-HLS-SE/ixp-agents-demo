from __future__ import annotations

import datetime
import re
from typing import Any

DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%Y%m%d",
    "%b %d, %Y",
    "%B %d, %Y",
]


def validate_date(text: str) -> bool:
    return date_normalize(text) is not None


def date_normalize(text: str) -> str | None:
    if not text:
        return None

    candidate = text.strip()
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.datetime.strptime(candidate, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    digits = re.sub(r"\D", "", candidate)
    if re.fullmatch(r"\d{8}", digits):
        try:
            parsed = datetime.datetime.strptime(digits, "%Y%m%d")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def validate_npi(text: str) -> bool:
    return bool(re.fullmatch(r"\d{10}", digits_only(text)))


def validate_icd(text: str) -> bool:
    if not text:
        return False
    return bool(re.fullmatch(r"[A-TV-Z][0-9]{2}(?:\.[A-Z0-9]{1,4})?", text.strip(), re.IGNORECASE))


def coerce_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def within_numeric_tolerance(expected: Any, actual: Any, tolerance: float = 0.0) -> bool:
    expected_number = coerce_number(expected)
    actual_number = coerce_number(actual)
    if expected_number is None or actual_number is None:
        return False
    return abs(expected_number - actual_number) <= float(tolerance)
