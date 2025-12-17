"""
Image processing utilities for document pipeline.

Provides functions for resizing images, preparing them for Bedrock API,
applying preprocessing for improved OCR accuracy, and validating image uploads.
"""

import io
import logging
from enum import Enum
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter

from ragstack_common.constants import (
    MAX_IMAGE_SIZE_BYTES,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_IMAGE_TYPES,
)

logger = logging.getLogger(__name__)


class ImageStatus(str, Enum):
    """Image processing status (matches GraphQL ImageStatus enum)."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


def validate_image_type(content_type: str | None, filename: str | None) -> tuple[bool, str]:
    """
    Validate that an image has a supported content type and file extension.

    Args:
        content_type: MIME type of the image (e.g., "image/png")
        filename: Original filename with extension

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    if not filename:
        return False, "Filename is required"

    # Get file extension
    ext = Path(filename.lower()).suffix
    if not ext:
        return False, f"Filename must have an extension: {filename}"

    # Check extension is supported
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS))
        return False, f"Unsupported image extension '{ext}'. Supported: {supported}"

    # If content_type is provided, validate it matches extension
    if content_type:
        if content_type not in SUPPORTED_IMAGE_TYPES:
            supported = ", ".join(sorted(SUPPORTED_IMAGE_TYPES.keys()))
            return False, f"Unsupported content type '{content_type}'. Supported: {supported}"

        # Check that content type matches extension
        expected_ext = SUPPORTED_IMAGE_TYPES[content_type]
        # Handle .jpg vs .jpeg
        if ext == ".jpeg" and expected_ext == ".jpg":
            pass  # Allow .jpeg for image/jpeg
        elif ext != expected_ext and not (ext == ".jpg" and expected_ext == ".jpg"):
            return (
                False,
                f"Content type '{content_type}' does not match extension '{ext}'",
            )

    return True, ""


def validate_image_size(size_bytes: int | None) -> tuple[bool, str]:
    """
    Validate that an image file size is within the allowed limit.

    Args:
        size_bytes: File size in bytes

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    if size_bytes is None:
        return False, "File size is required"

    if size_bytes <= 0:
        return False, "File size must be positive"

    if size_bytes > MAX_IMAGE_SIZE_BYTES:
        max_mb = MAX_IMAGE_SIZE_BYTES / (1024 * 1024)
        actual_mb = size_bytes / (1024 * 1024)
        return (
            False,
            f"File size {actual_mb:.1f}MB exceeds maximum {max_mb:.0f}MB",
        )

    return True, ""


def is_supported_image(filename: str | None) -> bool:
    """
    Check if a filename has a supported image extension.

    Args:
        filename: Filename to check

    Returns:
        True if the filename has a supported image extension, False otherwise.
    """
    if not filename:
        return False

    ext = Path(filename.lower()).suffix
    return ext in SUPPORTED_IMAGE_EXTENSIONS


def resize_image(
    image_data: bytes,
    target_width: int | None = None,
    target_height: int | None = None,
    allow_upscale: bool = False,
) -> bytes:
    """
    Resize an image to fit within target dimensions while preserving aspect ratio.

    Args:
        image_data: Raw image bytes
        target_width: Target width in pixels (None = no resize)
        target_height: Target height in pixels (None = no resize)
        allow_upscale: Whether to allow making the image larger

    Returns:
        Resized image bytes in original format (or JPEG if format cannot be preserved)
    """
    # If either dimension is None, return original image
    if target_width is None or target_height is None:
        logger.info("No resize requested, returning original image")
        return image_data

    # Open image
    image = Image.open(io.BytesIO(image_data))
    current_width, current_height = image.size
    original_format = image.format

    # Calculate scaling factor to fit within bounds while preserving aspect ratio
    width_ratio = target_width / current_width
    height_ratio = target_height / current_height
    scale_factor = min(width_ratio, height_ratio)

    # Determine if resizing is needed
    needs_resize = (scale_factor < 1.0) or (allow_upscale and scale_factor > 1.0)

    if needs_resize:
        new_width = int(current_width * scale_factor)
        new_height = int(current_height * scale_factor)
        logger.info(
            f"Resizing image from {current_width}x{current_height} to {new_width}x{new_height}"
        )

        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Save in original format if possible, otherwise JPEG
        img_byte_array = io.BytesIO()
        save_format = (
            original_format
            if original_format in ["JPEG", "PNG", "GIF", "BMP", "TIFF", "WEBP"]
            else "JPEG"
        )

        save_kwargs = {"format": save_format}
        if save_format in ["JPEG", "JPG"]:
            save_kwargs["quality"] = 95
            save_kwargs["optimize"] = True

        image.save(img_byte_array, **save_kwargs)
        return img_byte_array.getvalue()
    logger.info(
        f"Image {current_width}x{current_height} already fits within {target_width}x{target_height}"
    )
    return image_data


def prepare_image(
    image_source: str | bytes,
    target_width: int | None = None,
    target_height: int | None = None,
    allow_upscale: bool = False,
) -> bytes:
    """
    Prepare an image for model input from either S3 URI or raw bytes.

    Args:
        image_source: Either an S3 URI (s3://bucket/key) or raw image bytes
        target_width: Target width in pixels (None = no resize)
        target_height: Target height in pixels (None = no resize)
        allow_upscale: Whether to allow making the image larger

    Returns:
        Processed image bytes ready for model input
    """
    # Get the image data
    if isinstance(image_source, str) and image_source.startswith("s3://"):
        # Import here to avoid circular dependency
        from .storage import read_s3_binary

        image_data = read_s3_binary(image_source)
    elif isinstance(image_source, bytes):
        image_data = image_source
    else:
        raise ValueError(f"Invalid image source: {type(image_source)}. Must be S3 URI or bytes.")

    # Resize and process
    return resize_image(image_data, target_width, target_height, allow_upscale)


def apply_adaptive_binarization(image_data: bytes) -> bytes:
    """
    Apply adaptive binarization to improve OCR accuracy on documents with
    uneven lighting, low contrast, or background noise.

    Args:
        image_data: Raw image bytes

    Returns:
        Processed image as JPEG bytes with adaptive binarization applied
    """
    try:
        # Convert bytes to PIL Image
        pil_image = Image.open(io.BytesIO(image_data))

        # Convert to grayscale if not already
        if pil_image.mode != "L":
            pil_image = pil_image.convert("L")

        # Apply adaptive thresholding using Pillow operations
        block_size = 15
        threshold_offset = 10

        # Create a blurred version for local mean calculation
        radius = block_size // 2
        blurred = pil_image.filter(ImageFilter.BoxBlur(radius))

        # Apply adaptive threshold: original > (blurred - threshold_offset) ? 255 : 0
        width, height = pil_image.size
        original_pixels = list(pil_image.getdata())
        blurred_pixels = list(blurred.getdata())

        binary_pixels = []
        for orig, blur in zip(original_pixels, blurred_pixels, strict=True):
            threshold = blur - threshold_offset
            binary_pixels.append(255 if orig > threshold else 0)

        # Create binary image
        binary_image = Image.new("L", (width, height))
        binary_image.putdata(binary_pixels)

        # Convert to JPEG bytes
        img_byte_array = io.BytesIO()
        binary_image.save(img_byte_array, format="JPEG", quality=95)

        logger.debug("Applied adaptive binarization preprocessing")
        return img_byte_array.getvalue()

    except Exception:
        logger.exception("Error applying adaptive binarization")
        logger.warning("Falling back to original image")
        return image_data


def prepare_bedrock_image_attachment(image_data: bytes) -> dict[str, Any]:
    """
    Format an image for Bedrock API attachment.

    Args:
        image_data: Raw image bytes

    Returns:
        Formatted image attachment for Bedrock API
    """
    # Detect image format
    image = Image.open(io.BytesIO(image_data))
    format_mapping = {"JPEG": "jpeg", "PNG": "png", "GIF": "gif", "WEBP": "webp"}
    detected_format = format_mapping.get(image.format)
    if not detected_format:
        raise ValueError(f"Unsupported image format: {image.format}")

    logger.info(f"Detected image format: {detected_format}")
    return {"image": {"format": detected_format, "source": {"bytes": image_data}}}
