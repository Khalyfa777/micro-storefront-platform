import io

from fastapi import HTTPException
from PIL import Image


MAX_IMAGE_WIDTH = 6000
MAX_IMAGE_HEIGHT = 6000
MAX_IMAGE_PIXELS = 36_000_000


def validate_uploaded_image_safety(image_bytes: bytes) -> None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            width, height = image.size
            image.verify()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is not a valid image.",
        )

    if width <= 0 or height <= 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image has invalid dimensions.",
        )

    if (
        width > MAX_IMAGE_WIDTH
        or height > MAX_IMAGE_HEIGHT
        or (width * height) > MAX_IMAGE_PIXELS
    ):
        raise HTTPException(
            status_code=400,
            detail="Image dimensions are too large. Maximum allowed size is 6000x6000 pixels.",
        )