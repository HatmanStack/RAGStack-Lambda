"""Citation extraction and parsing for query_kb.

Parses Bedrock KB citations into structured source objects with
document URLs, media timestamps, and source attribution.
"""

import contextlib
import json
import logging
import os
from typing import Any
from urllib.parse import unquote

try:
    from ._clients import dynamodb, s3_client
    from .filters import extract_kb_scalar, get_config_manager
    from .media import (
        MEDIA_CONTENT_TYPES,
        extract_image_caption_from_content,
        extract_source_url_from_content,
        format_timestamp,
        generate_media_url,
    )
except ImportError:
    from _clients import dynamodb, s3_client  # type: ignore[import-not-found,no-redef]
    from filters import (  # type: ignore[import-not-found,no-redef]
        extract_kb_scalar,
        get_config_manager,
    )
    from media import (  # type: ignore[import-not-found,no-redef]
        MEDIA_CONTENT_TYPES,
        extract_image_caption_from_content,
        extract_source_url_from_content,
        format_timestamp,
        generate_media_url,
    )

from ragstack_common.storage import generate_presigned_url, parse_s3_uri
from ragstack_common.types import SourceInfo

logger = logging.getLogger()


def extract_sources(citations: list[Any]) -> list[SourceInfo]:
    """
    Parse Bedrock citations into structured sources.

    Args:
        citations (list): Bedrock citation objects from retrieve_and_generate

    Returns:
        list[dict]: Parsed sources with documentId, pageNumber, s3Uri, snippet

    Example citation structure:
        [{
            'retrievedReferences': [{
                'content': {'text': 'chunk text...'},
                'location': {
                    's3Location': {
                        'uri': 's3://bucket/doc-id/pages/page-1.json'
                    }
                },
                'metadata': {...}
            }]
        }]
    """
    sources: list[SourceInfo] = []
    seen: set[str] = set()  # Deduplicate sources

    logger.info(f"Processing {len(citations)} citations")
    for idx, citation in enumerate(citations):
        logger.debug(f"Processing citation {idx}")
        for ref in citation.get("retrievedReferences", []):
            # Extract S3 URI - handle both retrieve and retrieve_and_generate response formats
            location = ref.get("location") or {}
            s3_location = location.get("s3Location") or {}
            uri = s3_location.get("uri", "")
            # Extract relevance score from KB response (0-1 range)
            relevance_score = ref.get("score")

            if not uri:
                logger.debug(f"No URI found in reference. Location: {location}")
                continue

            logger.info(f"Processing source URI: {uri}")

            # Parse S3 URI to construct the original input document URI
            # All content now uses unified content/ prefix:
            # 1. PDF/document: s3://bucket/content/{docId}/extracted_text.txt
            #    Input: s3://bucket/input/{docId}/{filename}.pdf
            # 2. Scraped: s3://bucket/content/{docId}/full_text.txt
            #    Input: s3://bucket/input/{docId}/{docId}.scraped.md
            # 3. Images: s3://bucket/content/{imageId}/caption.txt
            #    Actual image: s3://bucket/content/{imageId}/{filename}.ext
            try:
                bucket, s3_key = parse_s3_uri(uri)
                parts = s3_key.split("/")
                logger.info(f"Parsing URI: {uri}, parts count: {len(parts)}")

                if len(parts) < 2:
                    logger.warning(f"Invalid S3 URI format (too few parts): {parts}")
                    continue

                document_id = None
                original_filename = None
                input_prefix = None
                is_scraped = False
                is_image = False

                # Detect structure based on path prefix
                if len(parts) > 1 and parts[0] == "content":
                    # Unified content structure: content/{docId}/...
                    document_id = unquote(parts[1])

                    # Determine content type from filename
                    last_part = parts[-1] if parts else ""
                    last_part_lower = last_part.lower()
                    if last_part == "caption.txt":
                        # Image caption (text embedding)
                        input_prefix = "content"
                        is_image = True
                        logger.info(f"Image caption detected: imageId={document_id}")
                    elif last_part_lower.endswith((".jpeg", ".jpg", ".png", ".gif", ".webp")):
                        # Image file directly (visual embedding)
                        input_prefix = "content"
                        is_image = True
                        logger.info(f"Image file detected: imageId={document_id}, file={last_part}")
                    elif last_part == "full_text.txt":
                        # Old format scraped content
                        input_prefix = "input"
                        original_filename = f"{document_id}.scraped.md"
                        is_scraped = True
                        logger.info(f"Scraped content detected (old format): docId={document_id}")
                    elif last_part_lower.endswith(".md"):
                        # Possible new format scraped content: content/{job_id}/{url_slug}.md
                        # Will confirm via tracking table lookup (doc_type == "scraped")
                        input_prefix = "content"
                        original_filename = last_part
                        # Don't set is_scraped here - wait for tracking table confirmation
                        logger.info(
                            f"Markdown in content/ detected: doc_id={document_id}, "
                            f"file={last_part} (will confirm type from tracking table)"
                        )
                    else:
                        # PDF or other document
                        input_prefix = "input"
                        logger.info(f"Document content detected: docId={document_id}")

                elif len(parts) > 2 and parts[0] == "input":
                    # Input structure: input/{docId}/{filename}
                    document_id = unquote(parts[1])
                    original_filename = unquote(parts[2]) if len(parts) > 2 else None
                    input_prefix = "input"
                    # Check if scraped based on filename
                    if original_filename and original_filename.endswith(".md"):
                        is_scraped = True
                    logger.info(f"Input structure: docId={document_id}, file={original_filename}")

                else:
                    # Fallback: try to parse as generic structure
                    document_id = unquote(parts[0]) if len(parts) > 0 else None
                    original_filename = unquote(parts[1]) if len(parts) > 1 else None
                    logger.info(f"Generic structure detected: docId={document_id}")

                logger.info(f"Parsed: bucket={bucket}, doc={document_id}, file={original_filename}")

                # Validate extracted values
                if not document_id or len(document_id) < 5:
                    logger.warning(f"Invalid document_id: {document_id}")
                    continue

                # Extract content text early - needed for filename extraction
                content_text = ref.get("content", {}).get("text", "")

                # ============================================================
                # SOURCE URI RESOLUTION - Comprehensive logging for debugging
                # ============================================================
                logger.debug(f"[SOURCE] ===== Processing source: {document_id} =====")
                logger.debug(f"[SOURCE] KB citation URI: {uri}")
                logger.debug(f"[SOURCE] is_scraped={is_scraped}, is_image={is_image}")
                logger.debug(f"[SOURCE] Parsed - bucket: {bucket}, input_prefix: {input_prefix}")

                # Look up input_s3_uri, filename, and source_url from tracking table
                # This gives us the actual source document URI (PDF, image, scraped web page)
                tracking_input_uri = None
                tracking_source_url = None
                tracking_item = None
                tracking_table_name = os.environ.get("TRACKING_TABLE")
                logger.debug(f"[SOURCE] Tracking table: {tracking_table_name}")
                if tracking_table_name:
                    try:
                        tracking_table = dynamodb.Table(tracking_table_name)
                        response = tracking_table.get_item(Key={"document_id": document_id})
                        tracking_item = response.get("Item")
                        if tracking_item:
                            tracking_input_uri = str(tracking_item.get("input_s3_uri", "")) or None
                            tracking_source_url = str(tracking_item.get("source_url", "")) or None
                            original_filename = str(tracking_item.get("filename", "")) or None
                            # Get document type for media detection (normalize scrape -> scraped)
                            doc_type = str(tracking_item.get("type", "")) or "document"
                            if doc_type == "scrape":
                                doc_type = "scraped"
                            logger.info(
                                f"[SOURCE] Tracking lookup SUCCESS: "
                                f"input_s3_uri={tracking_input_uri}, "
                                f"filename={original_filename}, "
                                f"source_url={tracking_source_url}, "
                                f"status={str(tracking_item.get('status', ''))}, "
                                f"type={str(tracking_item.get('type', ''))}"
                            )
                        else:
                            doc_type = "document"  # Default when no tracking item
                            logger.warning(
                                f"[SOURCE] Tracking lookup EMPTY: "
                                f"No item found for document_id={document_id}"
                            )
                    except Exception as e:
                        doc_type = "document"  # Default on error
                        logger.error(f"[SOURCE] Tracking lookup FAILED: {e}", exc_info=True)
                else:
                    doc_type = "document"  # Default when no tracking table
                    logger.warning("[SOURCE] TRACKING_TABLE env var not set!")

                # Confirm is_scraped from tracking table doc_type (authoritative)
                # This handles new format scraped content: content/{job_id}/{slug}.md
                if doc_type == "scraped":
                    is_scraped = True
                    logger.info("[SOURCE] Confirmed scraped content from tracking table")

                # Construct document URI
                # For scraped content, use output URI (input may be deleted after processing)
                # For other content, prefer input_s3_uri from tracking table
                if is_scraped:
                    # Scraped content: use the output full_text.txt or the KB citation URI
                    document_s3_uri = uri  # KB citation already points to output
                    logger.debug(f"[SOURCE] Scraped content, using KB URI: {document_s3_uri}")
                elif tracking_input_uri:
                    document_s3_uri = tracking_input_uri
                    logger.debug(f"[SOURCE] Using tracking input_s3_uri: {document_s3_uri}")
                elif original_filename and len(original_filename) > 0:
                    if input_prefix:
                        document_s3_uri = (
                            f"s3://{bucket}/{input_prefix}/{document_id}/{original_filename}"
                        )
                    else:
                        document_s3_uri = f"s3://{bucket}/{document_id}/{original_filename}"
                    logger.info(
                        f"[SOURCE] Constructed URI from filename: {document_s3_uri} "
                        f"(input_prefix={input_prefix}, filename={original_filename})"
                    )
                else:
                    # Fallback if filename missing
                    document_s3_uri = uri
                    logger.warning(
                        f"[SOURCE] FALLBACK to KB URI (no input_s3_uri or filename): "
                        f"{document_s3_uri}"
                    )

                logger.debug(f"[SOURCE] Final document_s3_uri: {document_s3_uri}")

                # Extract page number if available (from metadata or filename)
                page_num = None
                if "pages" in parts and len(parts) > 3:
                    page_file = parts[-1]  # e.g., "page-3.json"
                    try:
                        page_num = int(page_file.split("-")[1].split(".")[0])
                    except (IndexError, ValueError):
                        logger.debug(f"Could not extract page number from: {page_file}")

                # Extract snippet (content_text already extracted above)
                snippet = content_text[:200] if content_text else ""

                # For scraped content, get source URL from metadata sidecar, tracking table,
                # or frontmatter
                source_url = None
                if is_scraped:
                    # For new format, read source_url from metadata sidecar file
                    # URI: s3://bucket/content/{job_id}/{slug}.md
                    # Metadata: {slug}.md.metadata.json
                    if uri.endswith(".md"):
                        metadata_uri = f"{uri}.metadata.json"
                        try:
                            meta_bucket, meta_key = parse_s3_uri(metadata_uri)
                            if meta_bucket and meta_key:
                                meta_response = s3_client.get_object(
                                    Bucket=meta_bucket, Key=meta_key
                                )
                                meta_body = meta_response["Body"].read().decode("utf-8")
                                meta_content = json.loads(meta_body)
                                source_url = meta_content.get("metadataAttributes", {}).get(
                                    "source_url"
                                )
                                # Handle case where source_url is stored as a list
                                if isinstance(source_url, list):
                                    source_url = source_url[0] if source_url else None
                                if source_url:
                                    logger.info(
                                        f"[SOURCE] Got source_url from metadata: {source_url}"
                                    )
                        except Exception as e:
                            logger.debug(f"[SOURCE] Could not read metadata sidecar: {e}")

                    # Fallback: try tracking table (old format has source_url per-page)
                    if not source_url and tracking_source_url:
                        source_url = tracking_source_url
                        logger.debug(f"[SOURCE] Using source_url from tracking: {source_url}")

                    # Last fallback: try to extract from content frontmatter
                    if not source_url:
                        source_url = extract_source_url_from_content(content_text)
                        logger.debug(f"[SOURCE] Extracted source_url from content: {source_url}")

                # For image content, extract caption from frontmatter
                image_caption = None
                if is_image:
                    image_caption = extract_image_caption_from_content(content_text)
                    preview = image_caption[:50] if image_caption else None
                    logger.debug(f"Image content detected, caption: {preview}...")

                # Extract KB chunk timestamps early (needed for deduplication)
                # These are in milliseconds for visual embeddings from native KB chunking
                kb_metadata = ref.get("metadata", {})
                kb_chunk_start_ms = extract_kb_scalar(
                    kb_metadata.get("x-amz-bedrock-kb-chunk-start-time-in-millis")
                )

                # Deduplicate sources:
                # - Video/media segments: use URI + timestamp (each chunk is unique)
                # - PDF pages: use document_id:page_num
                # - Scraped pages: use source_url (each page has a unique URL)
                # - Other content: use document_id
                is_segment = doc_type == "media" or "segment-" in uri or uri.endswith(".mp4")
                if is_segment:
                    # Each video segment is a unique source (include timestamp for KB chunks)
                    if kb_chunk_start_ms is not None:
                        source_key = f"{uri}:{kb_chunk_start_ms}"
                    else:
                        source_key = uri
                elif page_num is not None:
                    source_key = f"{document_id}:{page_num}"
                elif is_scraped and source_url:
                    # Each scraped page has a unique source URL
                    source_key = source_url
                else:
                    source_key = document_id

                if source_key not in seen:
                    # Check if document access is allowed
                    allow_document_access = get_config_manager().get_parameter(
                        "chat_allow_document_access", default=False
                    )
                    logger.debug(f"[SOURCE] Document access allowed: {allow_document_access}")

                    # Generate presigned URL if access is enabled
                    document_url = None
                    if (
                        allow_document_access
                        and document_s3_uri
                        and document_s3_uri.startswith("s3://")
                    ):
                        # Parse S3 URI to get bucket and key
                        doc_bucket, doc_key = parse_s3_uri(document_s3_uri)
                        if doc_bucket and doc_key:
                            # Validate key looks reasonable (has document ID and filename)
                            if "/" in doc_key and len(doc_key) > 10:
                                logger.info(
                                    f"[SOURCE] Generating presigned URL: bucket={doc_bucket}, key={doc_key}"
                                )
                                document_url = generate_presigned_url(doc_bucket, doc_key)
                                if document_url:
                                    logger.info(
                                        f"[SOURCE] Presigned URL generated: {document_url[:80]}..."
                                    )
                                else:
                                    logger.warning("[SOURCE] Presigned URL returned None")
                            else:
                                logger.warning(f"[SOURCE] Skipping malformed key: {doc_key}")
                        else:
                            logger.warning(f"[SOURCE] Could not parse S3 URI: {document_s3_uri}")
                    else:
                        logger.info(
                            f"[SOURCE] Skipping presigned URL: access={allow_document_access}, "
                            f"uri={document_s3_uri[:50] if document_s3_uri else 'None'}..."
                        )

                    # For images, use the same presigned URL as document_url
                    # (document_s3_uri now points to actual image, not caption.txt)
                    thumbnail_url = None
                    if is_image and allow_document_access and document_url:
                        thumbnail_url = document_url
                        logger.info("[SOURCE] Image thumbnail URL set from document_url")

                    # For scraped content, use the original web URL as documentUrl
                    # so users can click through to the source website
                    if is_scraped and source_url:
                        document_url = source_url
                        logger.debug(f"[SOURCE] Scraped content - using source URL: {source_url}")

                    # Check for media sources (video/audio content types or tracking type)
                    # KB metadata comes as lists with quoted strings, extract scalars
                    metadata = ref.get("metadata", {})
                    content_type = extract_kb_scalar(metadata.get("content_type"))
                    is_media = content_type in MEDIA_CONTENT_TYPES or doc_type == "media"
                    # Get media_type from metadata or derive from content_type
                    if is_media:
                        media_type_raw = extract_kb_scalar(metadata.get("media_type"))
                        if media_type_raw in ("video", "audio"):
                            media_type = media_type_raw
                        elif content_type in ("video", "audio"):
                            media_type = content_type
                        else:
                            media_type = None
                    else:
                        media_type = None

                    # Extract timestamp fields (convert to int for URL generation)
                    timestamp_start = None
                    timestamp_end = None
                    if is_media:
                        # Check custom metadata first (transcripts use seconds)
                        # Note: values may be floats, need int(float()) to convert
                        ts_start_str = extract_kb_scalar(metadata.get("timestamp_start"))
                        ts_end_str = extract_kb_scalar(metadata.get("timestamp_end"))
                        if ts_start_str is not None:
                            with contextlib.suppress(ValueError, TypeError):
                                timestamp_start = int(float(ts_start_str))
                        if ts_end_str is not None:
                            with contextlib.suppress(ValueError, TypeError):
                                timestamp_end = int(float(ts_end_str))
                        # Fall back to native KB keys for visual embeddings (milliseconds)
                        # Note: KB returns floats like 30000.0, need int(float()) to convert
                        if timestamp_start is None:
                            ts_millis = extract_kb_scalar(
                                metadata.get("x-amz-bedrock-kb-chunk-start-time-in-millis")
                            )
                            if ts_millis is not None:
                                with contextlib.suppress(ValueError, TypeError):
                                    timestamp_start = int(float(ts_millis)) // 1000
                        if timestamp_end is None:
                            ts_millis = extract_kb_scalar(
                                metadata.get("x-amz-bedrock-kb-chunk-end-time-in-millis")
                            )
                            if ts_millis is not None:
                                with contextlib.suppress(ValueError, TypeError):
                                    timestamp_end = int(float(ts_millis)) // 1000

                    speaker = extract_kb_scalar(metadata.get("speaker")) if is_media else None
                    segment_index = None
                    if is_media:
                        seg_idx_str = extract_kb_scalar(metadata.get("segment_index"))
                        if seg_idx_str is not None:
                            with contextlib.suppress(ValueError, TypeError):
                                segment_index = int(seg_idx_str)

                    # For media sources, generate both full URL and segment URL with timestamp
                    segment_url = None
                    if is_media and allow_document_access and document_s3_uri:
                        media_bucket, media_key = parse_s3_uri(document_s3_uri)
                        if media_bucket and media_key:
                            # Full video URL (no timestamp)
                            document_url = generate_presigned_url(media_bucket, media_key)
                            # Segment URL with timestamp fragment for deep linking
                            if document_url and timestamp_start is not None:
                                segment_url = generate_media_url(
                                    media_bucket, media_key, timestamp_start, timestamp_end
                                )
                                logger.info(
                                    f"[SOURCE] Media URLs: full={document_url[:50]}..., "
                                    f"segment=#t={timestamp_start},{timestamp_end}"
                                )

                    # Format timestamp display for media sources
                    timestamp_display = None
                    if is_media and timestamp_start is not None:
                        start_fmt = format_timestamp(timestamp_start)
                        end_fmt = format_timestamp(timestamp_end) if timestamp_end else ""
                        timestamp_display = f"{start_fmt}-{end_fmt}" if end_fmt else start_fmt

                    source_obj: SourceInfo = {
                        "documentId": document_id,
                        "pageNumber": page_num,
                        "s3Uri": document_s3_uri,  # Use input bucket URI, not output
                        "snippet": snippet,
                        "documentUrl": document_url,
                        "documentAccessAllowed": allow_document_access,
                        "score": relevance_score,  # KB relevance score (0-1)
                        "filename": original_filename,  # Original filename
                        "isScraped": is_scraped,
                        "sourceUrl": source_url,  # Original web URL for scraped content
                        # Image-specific fields
                        "isImage": is_image,
                        "thumbnailUrl": thumbnail_url,
                        "caption": image_caption,
                        # Media-specific fields (matches search_kb structure)
                        "isMedia": is_media if is_media else None,
                        "isSegment": is_segment,
                        "segmentUrl": segment_url,  # URL with #t=start,end for deep linking
                        "mediaType": media_type,
                        "contentType": content_type if is_media else None,
                        "timestampStart": timestamp_start,
                        "timestampEnd": timestamp_end,
                        "timestampDisplay": timestamp_display,
                        "speaker": speaker,
                        "segmentIndex": segment_index,
                    }
                    # Log the complete source object for debugging
                    doc_url_preview = (
                        document_url[:60] + "..."
                        if document_url and len(document_url) > 60
                        else document_url
                    )
                    logger.debug(f"[SOURCE] FINAL: docId={document_id}, s3Uri={document_s3_uri}")
                    logger.info(
                        f"[SOURCE] FINAL: documentUrl={doc_url_preview}, "
                        f"isScraped={is_scraped}, isImage={is_image}"
                    )
                    logger.debug(f"[SOURCE] ===== End source {document_id} =====")
                    sources.append(source_obj)
                    seen.add(source_key)
                else:
                    logger.debug(f"Skipping duplicate source: {source_key}")

            except Exception as e:
                logger.error(f"Failed to parse source: {e}")
                continue

    logger.info(f"Extracted {len(sources)} unique sources from {len(citations)} citations")
    return sources
