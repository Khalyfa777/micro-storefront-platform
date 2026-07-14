import re

_ALLOWED_PHONE_CHARACTERS = re.compile(r"^[0-9+()\s.-]+$")
_MULTIPLE_NUMBER_SEPARATORS = re.compile(r"[/,;&]")


def normalize_ghana_whatsapp_number(
    value: str,
) -> str | None:
    """Normalize one Ghana phone number for use with WhatsApp.

    Accepted examples include ``0544494613``, ``233544494613`` and
    ``+233 54 449 4613``. The stored value always uses the canonical
    international digits-only form required by ``wa.me``.
    """

    normalized = value.strip()

    if not normalized:
        return None

    if _MULTIPLE_NUMBER_SEPARATORS.search(normalized):
        raise ValueError(
            "Enter one Ghana WhatsApp number only."
        )

    if not _ALLOWED_PHONE_CHARACTERS.fullmatch(normalized):
        raise ValueError(
            "Enter one valid Ghana WhatsApp number, for example 0544494613."
        )

    if normalized.count("+") > 1 or (
        "+" in normalized
        and not normalized.startswith("+")
    ):
        raise ValueError(
            "Enter one valid Ghana WhatsApp number, for example 0544494613."
        )

    digits = re.sub(r"\D", "", normalized)

    if re.fullmatch(r"0\d{9}", digits):
        return f"233{digits[1:]}"

    if re.fullmatch(r"233\d{9}", digits):
        return digits

    raise ValueError(
        "Enter one valid Ghana WhatsApp number, for example 0544494613."
    )
