import re

from fastapi import Response


PUBLIC_NO_STORE_HEADERS = {
    "Cache-Control": (
        "no-store, no-cache, "
        "must-revalidate, max-age=0"
    ),
    "Pragma": "no-cache",
    "Expires": "0",
}

_ORDER_NUMBER_PATTERN = re.compile(
    r"^[A-Z0-9-]+$"
)


def normalize_customer_phone(
    value: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Phone number must be text."
        )

    digits = re.sub(
        r"\D",
        "",
        value.strip(),
    )

    if digits.startswith("00"):
        digits = digits[2:]

    # Canonicalize Ghana local numbers:
    # 0241234567 -> 233241234567
    if (
        len(digits) == 10
        and digits.startswith("0")
    ):
        digits = "233" + digits[1:]

    if not 9 <= len(digits) <= 15:
        raise ValueError(
            "Enter a valid phone number."
        )

    return digits


def normalize_order_number(
    value: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Order number must be text."
        )

    normalized = value.strip().upper()

    if not 3 <= len(normalized) <= 30:
        raise ValueError(
            "Enter a valid order number."
        )

    if not _ORDER_NUMBER_PATTERN.fullmatch(
        normalized
    ):
        raise ValueError(
            "Enter a valid order number."
        )

    return normalized


def apply_public_no_store_headers(
    response: Response,
) -> None:
    for name, value in (
        PUBLIC_NO_STORE_HEADERS.items()
    ):
        response.headers[name] = value
