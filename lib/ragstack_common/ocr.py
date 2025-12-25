"""
OCR module for document pipeline.

Provides OCR capabilities using:
- AWS Textract for traditional OCR
- Amazon Bedrock for LLM-based text extraction
- PyMuPDF for text-native PDF detection and direct text extraction
"""

import logging

import boto3
import fitz  # PyMuPDF

from .bedrock import BedrockClient
from .image import prepare_bedrock_image_attachment
from .models import Document, OcrBackend, Page, Status
from .storage import parse_s3_uri, read_s3_binary, write_s3_text

logger = logging.getLogger(__name__)

# Threshold for determining if a PDF is text-native
MIN_EXTRACTABLE_CHARS_PER_PAGE = 50


class OcrService:
    """
    OCR service with intelligent routing between Textract, Bedrock, and direct text extraction.
    """

    def __init__(
        self,
        region: str | None = None,
        backend: str = "textract",
        bedrock_model_id: str | None = None,
    ):
        """
        Initialize OCR service.

        Args:
            region: AWS region
            backend: OCR backend to use ('textract' or 'bedrock')
            bedrock_model_id: Bedrock model ID for OCR (if backend='bedrock')
        """
        self.region = region
        self.backend = backend
        self.bedrock_model_id = bedrock_model_id or "anthropic.claude-3-5-haiku-20241022-v1:0"

        # Lazy-load clients
        self._textract_client = None
        self._bedrock_client = None

    @property
    def textract_client(self):
        """Lazy-loaded Textract client."""
        if self._textract_client is None:
            self._textract_client = boto3.client("textract", region_name=self.region)
        return self._textract_client

    @property
    def bedrock_client(self):
        """Lazy-loaded Bedrock client."""
        if self._bedrock_client is None:
            self._bedrock_client = BedrockClient(region=self.region)
        return self._bedrock_client

    def process_document(self, document: Document) -> Document:
        """
        Process a document with OCR.

        Intelligently routes to:
        1. Direct text extraction for text-native PDFs
        2. Textract or Bedrock for scanned documents

        Args:
            document: Document object with input_s3_uri set

        Returns:
            Updated Document object with pages populated
        """
        logger.info(f"Processing document: {document.document_id}")

        # Download document from S3
        document_bytes = read_s3_binary(document.input_s3_uri)

        # Determine document type
        if document.filename.lower().endswith(".pdf"):
            # Check if PDF is text-native
            is_text_native = self._is_text_native_pdf(document_bytes)
            document.is_text_native = is_text_native

            if is_text_native:
                logger.info("PDF is text-native, using direct text extraction")
                return self._extract_text_native_pdf(document, document_bytes)
            logger.info(f"PDF is scanned, using {self.backend} OCR")
            return self._process_with_ocr(document, document_bytes)
        # Image file - use OCR
        logger.info(f"Image file, using {self.backend} OCR")
        return self._process_with_ocr(document, document_bytes)

    def _is_text_native_pdf(self, pdf_bytes: bytes) -> bool:
        """
        Check if a PDF contains extractable text.

        Args:
            pdf_bytes: PDF file bytes

        Returns:
            True if PDF has sufficient extractable text
        """
        try:
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            # Check first 3 pages for text content
            pages_to_check = min(3, len(pdf_doc))
            total_chars = 0

            for page_num in range(pages_to_check):
                page = pdf_doc[page_num]
                text = page.get_text()
                total_chars += len(text.strip())

            pdf_doc.close()

            # Calculate average chars per page
            avg_chars = total_chars / pages_to_check
            is_text_native = avg_chars >= MIN_EXTRACTABLE_CHARS_PER_PAGE

            logger.info(
                f"PDF text check: {avg_chars:.0f} chars/page "
                f"(threshold: {MIN_EXTRACTABLE_CHARS_PER_PAGE})"
            )
            return is_text_native

        except Exception:
            logger.exception("Error checking PDF text content")
            return False

    def _extract_text_native_pdf(self, document: Document, pdf_bytes: bytes) -> Document:
        """
        Extract text directly from a text-native PDF using PyMuPDF.

        Args:
            document: Document object (may include page_start/page_end for batch mode)
            pdf_bytes: PDF file bytes

        Returns:
            Updated Document object
        """
        try:
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(pdf_doc)
            document.total_pages = total_pages

            # Determine page range (convert 1-indexed to 0-indexed for PyMuPDF)
            start_idx = (document.page_start - 1) if document.page_start else 0
            end_idx = document.page_end if document.page_end else total_pages

            pages = []
            full_text_parts = []

            for page_num in range(start_idx, end_idx):
                page = pdf_doc[page_num]

                # Extract text
                text = page.get_text()
                full_text_parts.append(f"--- Page {page_num + 1} ---\n{text}\n")

                # Create Page object
                page_obj = Page(
                    page_number=page_num + 1,
                    text=text,
                    ocr_backend=OcrBackend.TEXT_EXTRACTION.value,
                    confidence=100.0,  # Direct text extraction is 100% accurate
                )
                pages.append(page_obj)

            pdf_doc.close()

            # Save text to S3
            full_text = "\n".join(full_text_parts)

            # Determine if this is batch mode (partial page range)
            is_batch_mode = document.page_start is not None and document.page_end is not None

            # Parse output_s3_uri to get bucket, then construct proper key
            if document.output_s3_uri:
                bucket, base_key = parse_s3_uri(document.output_s3_uri)
                # If base_key ends with /, use it as prefix, otherwise use as-is
                if base_key and not base_key.endswith("/"):
                    base_key += "/"
                # In batch mode, use pages_XXX-YYY.txt naming
                if is_batch_mode:
                    output_key = (
                        f"{base_key}pages_{document.page_start:03d}-{document.page_end:03d}.txt"
                    )
                else:
                    output_key = f"{base_key}extracted_text.txt"
            else:
                # Fallback: use input bucket
                bucket, _ = parse_s3_uri(document.input_s3_uri)
                if is_batch_mode:
                    output_key = (
                        f"output/{document.document_id}/"
                        f"pages_{document.page_start:03d}-{document.page_end:03d}.txt"
                    )
                else:
                    output_key = f"output/{document.document_id}/extracted_text.txt"

            output_uri = f"s3://{bucket}/{output_key}"
            write_s3_text(output_uri, full_text)

            document.pages = pages
            document.output_s3_uri = output_uri
            document.status = Status.OCR_COMPLETE

            pages_processed = len(pages)
            if is_batch_mode:
                logger.info(
                    f"Extracted text from pages {document.page_start}-{document.page_end} "
                    f"({pages_processed} pages, text-native PDF)"
                )
            else:
                logger.info(f"Extracted text from {total_pages} pages (text-native PDF)")
            return document

        except Exception as e:
            logger.exception("Error extracting text from PDF")
            document.status = Status.FAILED
            document.error_message = str(e)
            return document

    def _process_with_ocr(self, document: Document, document_bytes: bytes) -> Document:
        """
        Process document with OCR backend (Textract or Bedrock).

        Args:
            document: Document object
            document_bytes: Document file bytes

        Returns:
            Updated Document object
        """
        if self.backend == "textract":
            return self._process_with_textract(document, document_bytes)
        if self.backend == "bedrock":
            return self._process_with_bedrock(document, document_bytes)
        raise ValueError(f"Unsupported OCR backend: {self.backend}")

    def _process_with_textract(self, document: Document, document_bytes: bytes) -> Document:
        """
        Process document with AWS Textract.
        """
        try:
            logger.info(f"Processing with Textract: {document.document_id}")

            # Call Textract DetectDocumentText
            response = self.textract_client.detect_document_text(Document={"Bytes": document_bytes})

            # Extract text and confidence, grouped by page
            blocks = response.get("Blocks", [])
            lines = [b for b in blocks if b["BlockType"] == "LINE"]

            # Group lines by page number
            pages_dict = {}
            for line in lines:
                page_num = line.get("Page", 1)
                if page_num not in pages_dict:
                    pages_dict[page_num] = {"lines": [], "confidence_sum": 0}

                pages_dict[page_num]["lines"].append(line.get("Text", ""))
                pages_dict[page_num]["confidence_sum"] += line.get("Confidence", 0)

            # Create Page objects for each page
            document.pages = []
            all_text_parts = []

            for page_num in sorted(pages_dict.keys()):
                page_data = pages_dict[page_num]
                text = "\n".join(page_data["lines"])
                avg_confidence = (
                    page_data["confidence_sum"] / len(page_data["lines"])
                    if page_data["lines"]
                    else 0
                )

                page = Page(
                    page_number=page_num,
                    text=text,
                    ocr_backend=OcrBackend.TEXTRACT.value,
                    confidence=avg_confidence,
                )
                document.pages.append(page)
                all_text_parts.append(text)

            document.total_pages = len(document.pages)

            # Combine all pages for S3 output
            full_text = "\n\n".join(all_text_parts)

            # Save extracted text to S3
            if document.output_s3_uri:
                bucket, base_key = parse_s3_uri(document.output_s3_uri)
                if base_key and not base_key.endswith("/"):
                    base_key += "/"
                # base_key already includes document_id/ from caller
                output_key = f"{base_key}extracted_text.txt"
            else:
                bucket, _ = parse_s3_uri(document.input_s3_uri)
                output_key = f"output/{document.document_id}/extracted_text.txt"

            output_uri = f"s3://{bucket}/{output_key}"
            write_s3_text(output_uri, full_text)

            document.output_s3_uri = output_uri
            document.status = Status.OCR_COMPLETE

            logger.info(
                f"Textract OCR complete: {document.total_pages} pages, {len(full_text)} chars"
            )
            return document

        except Exception as e:
            logger.exception("Error processing with Textract")
            document.status = Status.FAILED
            document.error_message = str(e)
            return document

    def _render_page_to_image(self, pdf_page, max_size_bytes: int = 5 * 1024 * 1024) -> bytes:
        """
        Render PDF page to image, reducing quality if needed to stay under size limit.

        Args:
            pdf_page: PyMuPDF page object
            max_size_bytes: Maximum image size (default 5MB for Bedrock)

        Returns:
            Image bytes (PNG or JPEG)
        """
        from io import BytesIO

        from PIL import Image

        # Try different DPI levels until image is under size limit
        for dpi in [150, 120, 100, 72, 50]:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = pdf_page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")

            if len(img_bytes) <= max_size_bytes:
                logger.info(f"Page rendered at {dpi} DPI: {len(img_bytes) / 1024:.0f} KB")
                return img_bytes

            # Try JPEG compression if PNG is too large
            img_bytes = pix.tobytes("jpeg")
            if len(img_bytes) <= max_size_bytes:
                logger.info(f"Page rendered at {dpi} DPI (JPEG): {len(img_bytes) / 1024:.0f} KB")
                return img_bytes

        # Still too large - use Pillow for aggressive JPEG compression
        size_kb = len(img_bytes) / 1024
        logger.warning(f"Page still large at 50 DPI: {size_kb:.0f} KB, applying compression")
        pil_image = Image.open(BytesIO(img_bytes))

        # Try progressively lower quality until under limit
        for quality in [70, 50, 30, 20]:
            buffer = BytesIO()
            pil_image.save(buffer, format="JPEG", quality=quality, optimize=True)
            img_bytes = buffer.getvalue()
            if len(img_bytes) <= max_size_bytes:
                size_kb = len(img_bytes) / 1024
                logger.info(f"Page compressed to JPEG quality {quality}: {size_kb:.0f} KB")
                return img_bytes

        # Last resort: resize the image
        logger.warning(f"Resizing image to fit under {max_size_bytes / 1024 / 1024:.1f} MB")
        for scale in [0.75, 0.5, 0.25]:
            new_size = (int(pil_image.width * scale), int(pil_image.height * scale))
            resized = pil_image.resize(new_size, Image.Resampling.LANCZOS)
            buffer = BytesIO()
            resized.save(buffer, format="JPEG", quality=50, optimize=True)
            img_bytes = buffer.getvalue()
            if len(img_bytes) <= max_size_bytes:
                logger.info(f"Page resized to {scale*100:.0f}%: {len(img_bytes) / 1024:.0f} KB")
                return img_bytes

        logger.error(f"Could not reduce image below {max_size_bytes / 1024 / 1024:.1f} MB")
        return img_bytes

    def _process_pdf_with_bedrock(
        self,
        pdf_bytes: bytes,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> tuple[list[Page], list[str]]:
        """
        Convert PDF pages to images and process each with Bedrock OCR.

        Args:
            pdf_bytes: PDF file bytes
            page_start: Starting page (1-indexed, inclusive). None = first page.
            page_end: Ending page (1-indexed, inclusive). None = last page.

        Returns:
            Tuple of (list of Page objects, list of text strings)
        """
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(pdf_doc)
        pages = []
        all_text_parts = []

        # Determine page range (convert 1-indexed to 0-indexed for PyMuPDF)
        start_idx = (page_start - 1) if page_start else 0
        end_idx = page_end if page_end else total_pages

        for page_num in range(start_idx, end_idx):
            logger.info(f"Processing PDF page {page_num + 1}/{total_pages} with Bedrock")
            pdf_page = pdf_doc[page_num]

            # Render page to image, auto-reducing quality if needed
            img_bytes = self._render_page_to_image(pdf_page)

            # Process image with Bedrock
            image_attachment = prepare_bedrock_image_attachment(img_bytes)

            system_prompt = "You are an OCR system. Extract all text from the image."
            content = [
                image_attachment,
                {"text": "Extract all text from this image. Preserve the layout and structure."},
            ]

            response = self.bedrock_client.invoke_model(
                model_id=self.bedrock_model_id,
                system_prompt=system_prompt,
                content=content,
                context="OCR",
            )

            text = self.bedrock_client.extract_text_from_response(response)
            all_text_parts.append(f"--- Page {page_num + 1} ---\n{text}")

            page = Page(
                page_number=page_num + 1,
                text=text,
                ocr_backend=OcrBackend.BEDROCK.value,
                confidence=None,
            )
            pages.append(page)

        pdf_doc.close()
        return pages, all_text_parts

    def _process_with_bedrock(self, document: Document, document_bytes: bytes) -> Document:
        """
        Process document with Amazon Bedrock.

        For PDFs, converts each page to an image first using PyMuPDF.
        Supports batch mode via document.page_start and document.page_end.
        """
        try:
            logger.info(f"Processing with Bedrock: {document.document_id}")

            # Check if this is a PDF - need to convert pages to images
            is_pdf = document.filename.lower().endswith(".pdf")

            # Determine if this is batch mode
            is_batch_mode = document.page_start is not None and document.page_end is not None

            if is_pdf:
                # Get total page count first (needed for batch mode tracking)
                pdf_doc = fitz.open(stream=document_bytes, filetype="pdf")
                document.total_pages = len(pdf_doc)
                pdf_doc.close()

                # Convert PDF pages to images and process each (with page range)
                pages, all_text_parts = self._process_pdf_with_bedrock(
                    document_bytes,
                    page_start=document.page_start,
                    page_end=document.page_end,
                )
                document.pages = pages
                text = "\n\n".join(all_text_parts)
            else:
                # Single image - process directly
                image_attachment = prepare_bedrock_image_attachment(document_bytes)

                system_prompt = "You are an OCR system. Extract all text from the image."
                content = [
                    image_attachment,
                    {"text": "Extract all text from this image. Preserve layout and structure."},
                ]

                response = self.bedrock_client.invoke_model(
                    model_id=self.bedrock_model_id,
                    system_prompt=system_prompt,
                    content=content,
                    context="OCR",
                )

                text = self.bedrock_client.extract_text_from_response(response)

                page = Page(
                    page_number=1, text=text, ocr_backend=OcrBackend.BEDROCK.value, confidence=None
                )
                document.pages = [page]
                document.total_pages = 1

            # Save extracted text to S3
            if document.output_s3_uri:
                bucket, base_key = parse_s3_uri(document.output_s3_uri)
                if base_key and not base_key.endswith("/"):
                    base_key += "/"
                # In batch mode, use pages_XXX-YYY.txt naming
                if is_batch_mode:
                    output_key = (
                        f"{base_key}pages_{document.page_start:03d}-{document.page_end:03d}.txt"
                    )
                else:
                    output_key = f"{base_key}extracted_text.txt"
            else:
                bucket, _ = parse_s3_uri(document.input_s3_uri)
                if is_batch_mode:
                    output_key = (
                        f"output/{document.document_id}/"
                        f"pages_{document.page_start:03d}-{document.page_end:03d}.txt"
                    )
                else:
                    output_key = f"output/{document.document_id}/extracted_text.txt"

            output_uri = f"s3://{bucket}/{output_key}"
            write_s3_text(output_uri, text)

            document.output_s3_uri = output_uri
            document.status = Status.OCR_COMPLETE

            if is_batch_mode:
                logger.info(
                    f"Bedrock OCR complete for pages {document.page_start}-{document.page_end}: "
                    f"{len(text)} chars"
                )
            else:
                logger.info(f"Bedrock OCR complete: {len(text)} chars")

            # Add metering data to document metadata
            metering = self.bedrock_client.get_metering_data()
            document.metadata["metering"] = metering

            return document

        except Exception as e:
            logger.exception("Error processing with Bedrock")
            document.status = Status.FAILED
            document.error_message = str(e)
            return document
