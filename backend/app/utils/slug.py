import re


STORE_NAME_MAX_LENGTH = 255
SLUG_MIN_LENGTH = 3
SLUG_MAX_LENGTH = 50

RESERVED_SLUGS = frozenset(
    {
        "admin",
        "api",
        "app",
        "assets",
        "dashboard",
        "help",
        "login",
        "payment",
        "settings",
        "signup",
        "static",
        "support",
        "track",
        "www",
    }
)

_SLUG_PATTERN = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
)

_CONTROL_CHARACTER_PATTERN = re.compile(
    r"[\x00-\x1f\x7f]"
)


def normalize_slug(
    value: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Slug must be text."
        )

    slug = value.lower().strip()

    slug = re.sub(
        r"[^a-z0-9-]+",
        "-",
        slug,
    )

    slug = re.sub(
        r"-+",
        "-",
        slug,
    ).strip("-")

    if not (
        SLUG_MIN_LENGTH
        <= len(slug)
        <= SLUG_MAX_LENGTH
    ):
        raise ValueError(
            "Slug must be 3-50 characters."
        )

    if not _SLUG_PATTERN.fullmatch(slug):
        raise ValueError(
            "Slug may contain only lowercase "
            "letters, numbers, and single "
            "hyphens."
        )

    if slug in RESERVED_SLUGS:
        raise ValueError(
            "This slug is reserved."
        )

    return slug


def validate_canonical_slug(
    value: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Slug must be text."
        )

    normalized = normalize_slug(value)

    if value != normalized:
        raise ValueError(
            "Slug must already be canonical: "
            "use lowercase letters, numbers, "
            "and single hyphens only."
        )

    return normalized


def validate_store_name(
    value: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Store name must be text."
        )

    name = value.strip()

    if not name:
        raise ValueError(
            "Store name is required."
        )

    if len(name) > STORE_NAME_MAX_LENGTH:
        raise ValueError(
            "Store name must not exceed "
            "255 characters."
        )

    if _CONTROL_CHARACTER_PATTERN.search(
        name
    ):
        raise ValueError(
            "Store name contains invalid "
            "control characters."
        )

    return name
