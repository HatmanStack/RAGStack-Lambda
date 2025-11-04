import io

from PIL import Image

from ragstack_common.image import prepare_bedrock_image_attachment, resize_image


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


if __name__ == "__main__":
    test_resize_image()
    test_bedrock_format()
    print("Image processing tests passed!")
