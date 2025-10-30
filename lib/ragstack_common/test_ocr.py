import fitz  # PyMuPDF

from .ocr import OcrService


def test_is_text_native_pdf():
    """Test PDF text detection with a generated PDF."""
    # Create a simple PDF with text
    pdf_doc = fitz.open()
    page = pdf_doc.new_page()
    page.insert_text((100, 100), "This is a test document with text content.")
    page.insert_text((100, 150), "It has multiple lines to simulate a real document.")

    # Convert to bytes
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    # Test OCR service
    ocr_service = OcrService(region="us-east-1", backend="textract")
    is_text_native = ocr_service._is_text_native_pdf(pdf_bytes)

    assert is_text_native
    print(f"✓ Text-native PDF detection works: {is_text_native}")


def test_ocr_service_initialization():
    """Test OCR service initialization."""
    # Test with textract backend
    ocr1 = OcrService(region="us-east-1", backend="textract")
    assert ocr1.backend == "textract"
    assert ocr1.region == "us-east-1"

    # Test with bedrock backend
    ocr2 = OcrService(region="us-west-2", backend="bedrock", bedrock_model_id="test-model")
    assert ocr2.backend == "bedrock"
    assert ocr2.bedrock_model_id == "test-model"

    print("✓ OCR service initialization works")


if __name__ == "__main__":
    test_is_text_native_pdf()
    test_ocr_service_initialization()
    print("OCR module tests passed!")
