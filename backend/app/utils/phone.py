import re

_ALLOWED_PHONE_CHARACTERS = re.compile(r"^[0-9+()\s.-]+$")
_MULTIPLE_NUMBER_SEPARATORS = re.compile(r"[/,;&]")
_GHANA_MOBILE_NATIONAL_NUMBER = re.compile(r"^[25]\d{8}$")


def _invalid_phone_message(field_label: str) -> str:
    return (
        f"Enter one valid {field_label}, "
        "for example 0544494613."
    )


def normalize_ghana_phone_number(
    value: str,
    *,
    field_label: str = "Ghana mobile number",
) -> str | None:
    """Normalize one Ghana mobile number to canonical international digits.

    StorePlug accepts Ghana mobile ranges that begin with ``02`` or ``05``
    in local form, plus their ``233`` international equivalents. Carrier
    prefix allocations are intentionally not hard-coded beyond that stable
    numbering-plan boundary.
    """

    normalized = value.strip()

    if not normalized:
        return None

    invalid_message = _invalid_phone_message(
        field_label
    )

    if _MULTIPLE_NUMBER_SEPARATORS.search(normalized):
        raise ValueError(
            f"Enter one {field_label} only."
        )

    if not _ALLOWED_PHONE_CHARACTERS.fullmatch(normalized):
        raise ValueError(invalid_message)

    if normalized.count("+") > 1 or (
        "+" in normalized
        and not normalized.startswith("+")
    ):
        raise ValueError(invalid_message)

    digits = re.sub(r"\D", "", normalized)

    if re.fullmatch(r"0\d{9}", digits):
        national_number = digits[1:]
    elif re.fullmatch(r"233\d{9}", digits):
        national_number = digits[3:]
    else:
        raise ValueError(invalid_message)

    if not _GHANA_MOBILE_NATIONAL_NUMBER.fullmatch(
        national_number
    ):
        raise ValueError(invalid_message)

    return f"233{national_number}"


def normalize_ghana_whatsapp_number(
    value: str,
) -> str | None:
    """Normalize one Ghana mobile number for ``wa.me`` URLs."""

    return normalize_ghana_phone_number(
        value,
        field_label="Ghana WhatsApp number",
    )
