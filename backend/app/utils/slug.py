import re

RESERVED_SLUGS = {"admin", "api", "www", "app", "dashboard", "login", "signup", "settings", "static", "assets", "help", "support"}

def normalize_slug(value: str) -> str:
    slug = value.lower().strip()
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not re.match(r"^[a-z0-9-]{3,50}$", slug or ""):
        raise ValueError("Slug must be 3-50 characters and contain only letters, numbers, and hyphens")
    if slug in RESERVED_SLUGS:
        raise ValueError("This slug is reserved")
    return slug
