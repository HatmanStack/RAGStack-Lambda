import io

import pytest
from PIL import Image

from ragstack_common.constants import MAX_IMAGE_SIZE_BYTES
from ragstack_common.image import (
    ImageStatus,
    is_supported_image,
    prepare_bedrock_image_attachment,
    resize_image,
    validate_image_size,
    validate_image_type,
)


def test_resize_image():
    # Create a test image
    test_image = Image.new("RGB", (2000, 3000), color="red")
    img_bytes = io.BytesIO()
    test_image.save(img_bytes, format="JPEG")

    # Test resize
    resized = resize_image(img_bytes.getvalue(), target_width=1024, target_height=1024)

    # Verify resize worked
    resized_image = Image.open(io.BytesIO(resized))
    assert resized_image.width <= 1024
    assert resized_image.height <= 1024
    assert resized_image.width == 683 or resized_image.height == 1024  # Aspect ratio preserved

    print(f"✓ Image resize works: {test_image.size} -> {resized_image.size}")


def test_bedrock_format():
    # Create a test image
    test_image = Image.new("RGB", (100, 100), color="blue")
    img_bytes = io.BytesIO()
    test_image.save(img_bytes, format="JPEG")

    # Test Bedrock format
    attachment = prepare_bedrock_image_attachment(img_bytes.getvalue())

    assert "image" in attachment
    assert attachment["image"]["format"] == "jpeg"
    assert "bytes" in attachment["image"]["source"]

    print(f"✓ Bedrock attachment format works: {attachment['image']['format']}")


# =============================================================================
# ImageStatus Enum Tests
# =============================================================================


def test_image_status_enum_values():
    """Test that ImageStatus enum has correct values matching GraphQL schema."""
    assert ImageStatus.PENDING.value == "PENDING"
    assert ImageStatus.PROCESSING.value == "PROCESSING"
    assert ImageStatus.INDEXED.value == "INDEXED"
    assert ImageStatus.FAILED.value == "FAILED"


def test_image_status_is_string_enum():
    """Test that ImageStatus enum values are strings and can be used directly."""
    # Values are strings
    assert isinstance(ImageStatus.PENDING.value, str)
    assert isinstance(ImageStatus.INDEXED.value, str)
    # Can be compared with strings
    assert ImageStatus.PENDING == "PENDING"
    assert ImageStatus.INDEXED == "INDEXED"


# =============================================================================
# validate_image_type Tests
# =============================================================================


@pytest.mark.parametrize(
    "content_type,filename",
    [
        ("image/png", "test.png"),
        ("image/jpeg", "test.jpg"),
        ("image/jpeg", "test.jpeg"),
        ("image/gif", "test.gif"),
        ("image/webp", "test.webp"),
        (None, "test.png"),  # Content type is optional
        (None, "test.JPG"),  # Case insensitive extension
        (None, "test.JPEG"),
    ],
)
def test_validate_image_type_valid(content_type, filename):
    """Test validation passes for supported image types."""
    is_valid, error = validate_image_type(content_type, filename)
    assert is_valid is True
    assert error == ""


@pytest.mark.parametrize(
    "content_type,filename,expected_error_contains",
    [
        (None, None, "Filename is required"),
        (None, "", "Filename is required"),
        (None, "noextension", "must have an extension"),
        (None, "test.pdf", "Unsupported image extension"),
        (None, "test.txt", "Unsupported image extension"),
        (None, "test.exe", "Unsupported image extension"),
        ("application/pdf", "test.png", "Unsupported content type"),
        ("image/png", "test.jpg", "does not match extension"),
        ("image/jpeg", "test.png", "does not match extension"),
    ],
)
def test_validate_image_type_invalid(content_type, filename, expected_error_contains):
    """Test validation fails for unsupported image types."""
    is_valid, error = validate_image_type(content_type, filename)
    assert is_valid is False
    assert expected_error_contains in error


# =============================================================================
# validate_image_size Tests
# =============================================================================


@pytest.mark.parametrize(
    "size_bytes",
    [
        1,  # 1 byte
        1024,  # 1 KB
        1024 * 1024,  # 1 MB
        5 * 1024 * 1024,  # 5 MB
        MAX_IMAGE_SIZE_BYTES,  # Exactly at limit (10 MB)
    ],
)
def test_validate_image_size_valid(size_bytes):
    """Test validation passes for valid file sizes."""
    is_valid, error = validate_image_size(size_bytes)
    assert is_valid is True
    assert error == ""


@pytest.mark.parametrize(
    "size_bytes,expected_error_contains",
    [
        (None, "File size is required"),
        (0, "must be positive"),
        (-1, "must be positive"),
        (MAX_IMAGE_SIZE_BYTES + 1, "exceeds maximum"),
        (11 * 1024 * 1024, "exceeds maximum"),  # 11 MB
        (100 * 1024 * 1024, "exceeds maximum"),  # 100 MB
    ],
)
def test_validate_image_size_invalid(size_bytes, expected_error_contains):
    """Test validation fails for invalid file sizes."""
    is_valid, error = validate_image_size(size_bytes)
    assert is_valid is False
    assert expected_error_contains in error


# =============================================================================
# is_supported_image Tests
# =============================================================================


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("test.png", True),
        ("test.jpg", True),
        ("test.jpeg", True),
        ("test.gif", True),
        ("test.webp", True),
        ("TEST.PNG", True),  # Case insensitive
        ("image.JPG", True),
        ("path/to/image.png", True),
        ("test.pdf", False),
        ("test.txt", False),
        ("test.doc", False),
        ("noextension", False),
        ("", False),
        (None, False),
    ],
)
def test_is_supported_image(filename, expected):
    """Test is_supported_image correctly identifies image files."""
    assert is_supported_image(filename) == expected


if __name__ == "__main__":
    test_resize_image()
    test_bedrock_format()
    test_image_status_enum_values()
    test_image_status_is_string_enum()
    print("Image processing tests passed!")
