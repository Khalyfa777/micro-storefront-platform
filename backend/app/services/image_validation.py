import io
import warnings

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_WIDTH = 6000
MAX_IMAGE_HEIGHT = 6000
MAX_IMAGE_PIXELS = 36_000_000

_ALLOWED_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


def validate_uploaded_image_safety(
    image_bytes: bytes,
    declared_content_type: str | None = None,
) -> str:
    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(
                io.BytesIO(image_bytes)
            ) as image:
                image_format = (
                    image.format or ""
                ).upper()
                width, height = image.size
                image.verify()
    except HTTPException:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Uploaded file is not a valid "
                "or safe image."
            ),
        ) from exc

    format_details = (
        _ALLOWED_IMAGE_FORMATS.get(
            image_format
        )
    )

    if format_details is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, PNG, and WEBP "
                "images are allowed."
            ),
        )

    actual_content_type, extension = (
        format_details
    )

    if (
        declared_content_type is not None
        and declared_content_type
        != actual_content_type
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Image content does not match "
                "the declared file type."
            ),
        )

    if width <= 0 or height <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Uploaded image has invalid "
                "dimensions."
            ),
        )

    if (
        width > MAX_IMAGE_WIDTH
        or height > MAX_IMAGE_HEIGHT
        or width * height
        > MAX_IMAGE_PIXELS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Image dimensions are too large. "
                "Maximum allowed size is "
                "6000x6000 pixels."
            ),
        )

    return extension
