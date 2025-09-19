"""
Google Document AI service implementation for document processing.
Optimized for images, complex layouts, and handwriting recognition.
"""
import json
import logging
from typing import Dict, Any, List
import time
from google.cloud import documentai
from google.api_core.client_options import ClientOptions

logger = logging.getLogger(__name__)

class GoogleDocumentAIService:
    """Google Document AI service for advanced OCR and document understanding."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._client = None
        self.project_id = config.get('project_id')
        self.location = config.get('location', 'us')  # us, eu
        self.processor_id = config.get('processor_id')

    def _get_client(self):
        """Lazy initialization of Document AI client."""
        if not self._client:
            # Client options for location
            opts = ClientOptions(api_endpoint=f"{self.location}-documentai.googleapis.com")

            self._client = documentai.DocumentProcessorServiceClient(
                client_options=opts
            )
        return self._client

    async def process_document(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Process document using Google Document AI.

        Args:
            content: Document content as bytes
            filename: Original filename

        Returns:
            Extracted text and structure data
        """
        try:
            client = self._get_client()

            # Determine MIME type
            file_ext = filename.lower().split('.')[-1] if '.' in filename else 'pdf'
            mime_type = self._get_mime_type(file_ext)

            # Create the resource name
            name = client.processor_path(self.project_id, self.location, self.processor_id)

            # Configure the process request
            request = documentai.ProcessRequest(
                name=name,
                raw_document=documentai.RawDocument(
                    content=content,
                    mime_type=mime_type
                )
            )

            # Process the document
            result = client.process_document(request=request)
            document = result.document

            # Extract structured data
            extracted_data = self._extract_documentai_data(document)

            return {
                "success": True,
                "service": "google_documentai",
                "data": extracted_data,
                "raw_response": self._document_to_dict(document)
            }

        except Exception as e:
            logger.error(f"Google Document AI processing failed: {str(e)}")
            raise

    def _get_mime_type(self, file_ext: str) -> str:
        """Get MIME type for file extension."""
        mime_types = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'tiff': 'image/tiff',
            'gif': 'image/gif'
        }
        return mime_types.get(file_ext, 'application/pdf')

    def _extract_documentai_data(self, document) -> Dict[str, Any]:
        """Extract structured data from Document AI response."""
        # Get all text
        full_text = document.text

        # Extract pages
        pages_data = []
        for page in document.pages:
            page_data = self._extract_page_data(page, full_text)
            pages_data.append(page_data)

        # Extract entities (if available)
        entities = self._extract_entities(document)

        # Extract tables
        tables = self._extract_tables(document, full_text)

        # Extract form fields
        form_fields = self._extract_form_fields(document, full_text)

        return {
            "extractedText": full_text,
            "pages": pages_data,
            "entities": entities,
            "tables": tables,
            "formFields": form_fields,
            "confidence": self._calculate_document_confidence(document),
            "pageCount": len(document.pages),
            "processingTime": time.time(),
            "metadata": {
                "textStyle": self._extract_text_styles(document),
                "documentStyle": self._extract_document_style(document)
            }
        }

    def _extract_page_data(self, page, full_text: str) -> Dict[str, Any]:
        """Extract data from a single page."""
        # Extract paragraphs
        paragraphs = []
        for paragraph in page.paragraphs:
            para_text = self._get_text_from_layout(paragraph.layout, full_text)
            paragraphs.append({
                "text": para_text,
                "confidence": paragraph.layout.confidence,
                "boundingBox": self._get_bounding_box(paragraph.layout.bounding_poly)
            })

        # Extract lines
        lines = []
        for line in page.lines:
            line_text = self._get_text_from_layout(line.layout, full_text)
            lines.append({
                "text": line_text,
                "confidence": line.layout.confidence,
                "boundingBox": self._get_bounding_box(line.layout.bounding_poly)
            })

        # Extract tokens (words)
        tokens = []
        for token in page.tokens:
            token_text = self._get_text_from_layout(token.layout, full_text)
            tokens.append({
                "text": token_text,
                "confidence": token.layout.confidence,
                "boundingBox": self._get_bounding_box(token.layout.bounding_poly),
                "detectedBreak": self._get_detected_break(token)
            })

        return {
            "pageNumber": page.page_number,
            "dimensions": {
                "width": page.dimension.width,
                "height": page.dimension.height,
                "unit": page.dimension.unit
            },
            "paragraphs": paragraphs,
            "lines": lines,
            "tokens": tokens,
            "blocks": self._extract_blocks(page, full_text)
        }

    def _extract_blocks(self, page, full_text: str) -> List[Dict[str, Any]]:
        """Extract blocks from page."""
        blocks = []
        for block in page.blocks:
            block_text = self._get_text_from_layout(block.layout, full_text)
            blocks.append({
                "text": block_text,
                "confidence": block.layout.confidence,
                "boundingBox": self._get_bounding_box(block.layout.bounding_poly)
            })
        return blocks

    def _extract_entities(self, document) -> List[Dict[str, Any]]:
        """Extract entities from document."""
        entities = []
        for entity in document.entities:
            entities.append({
                "type": entity.type_,
                "mentionText": entity.mention_text,
                "normalizedValue": self._get_normalized_value(entity),
                "confidence": entity.confidence,
                "pageReferences": [
                    {
                        "page": ref.page,
                        "boundingBox": self._get_bounding_box(ref.bounding_poly)
                    }
                    for ref in entity.page_anchor.page_refs
                ] if entity.page_anchor else []
            })
        return entities

    def _extract_tables(self, document, full_text: str) -> List[Dict[str, Any]]:
        """Extract tables from document."""
        tables = []
        for page in document.pages:
            for table in page.tables:
                table_data = {
                    "headerRows": [],
                    "bodyRows": [],
                    "confidence": 0.0
                }

                confidences = []

                # Process header rows
                for header_row in table.header_rows:
                    row_data = []
                    for cell in header_row.cells:
                        cell_text = self._get_text_from_layout(cell.layout, full_text)
                        cell_confidence = cell.layout.confidence
                        confidences.append(cell_confidence)

                        row_data.append({
                            "text": cell_text,
                            "confidence": cell_confidence,
                            "colSpan": cell.col_span,
                            "rowSpan": cell.row_span
                        })
                    table_data["headerRows"].append(row_data)

                # Process body rows
                for body_row in table.body_rows:
                    row_data = []
                    for cell in body_row.cells:
                        cell_text = self._get_text_from_layout(cell.layout, full_text)
                        cell_confidence = cell.layout.confidence
                        confidences.append(cell_confidence)

                        row_data.append({
                            "text": cell_text,
                            "confidence": cell_confidence,
                            "colSpan": cell.col_span,
                            "rowSpan": cell.row_span
                        })
                    table_data["bodyRows"].append(row_data)

                # Calculate average confidence
                if confidences:
                    table_data["confidence"] = sum(confidences) / len(confidences)

                tables.append(table_data)

        return tables

    def _extract_form_fields(self, document, full_text: str) -> List[Dict[str, Any]]:
        """Extract form fields from document."""
        form_fields = []
        for page in document.pages:
            for form_field in page.form_fields:
                field_name = self._get_text_from_layout(form_field.field_name.layout, full_text)
                field_value = self._get_text_from_layout(form_field.field_value.layout, full_text)

                form_fields.append({
                    "fieldName": field_name,
                    "fieldValue": field_value,
                    "nameConfidence": form_field.field_name.layout.confidence,
                    "valueConfidence": form_field.field_value.layout.confidence,
                    "correctedKeyText": form_field.corrected_key_text,
                    "correctedValueText": form_field.corrected_value_text
                })

        return form_fields

    def _get_text_from_layout(self, layout, full_text: str) -> str:
        """Extract text using layout text anchor."""
        if not layout.text_anchor:
            return ""

        text_segments = []
        for segment in layout.text_anchor.text_segments:
            start_index = int(segment.start_index) if segment.start_index else 0
            end_index = int(segment.end_index) if segment.end_index else len(full_text)
            text_segments.append(full_text[start_index:end_index])

        return "".join(text_segments)

    def _get_bounding_box(self, bounding_poly) -> Dict[str, Any]:
        """Extract bounding box coordinates."""
        if not bounding_poly or not bounding_poly.vertices:
            return {}

        vertices = []
        for vertex in bounding_poly.vertices:
            vertices.append({
                "x": vertex.x,
                "y": vertex.y
            })

        return {"vertices": vertices}

    def _get_detected_break(self, token) -> Dict[str, Any]:
        """Extract detected break information from token."""
        if not token.detected_break:
            return {}

        return {
            "type": token.detected_break.type_.name,
            "isPrefix": token.detected_break.is_prefix
        }

    def _get_normalized_value(self, entity) -> Dict[str, Any]:
        """Extract normalized value from entity."""
        if not entity.normalized_value:
            return {}

        normalized = {}
        if entity.normalized_value.money_value:
            money = entity.normalized_value.money_value
            normalized["money"] = {
                "currencyCode": money.currency_code,
                "units": money.units,
                "nanos": money.nanos
            }

        if entity.normalized_value.date_value:
            date = entity.normalized_value.date_value
            normalized["date"] = {
                "year": date.year,
                "month": date.month,
                "day": date.day
            }

        if entity.normalized_value.datetime_value:
            datetime_val = entity.normalized_value.datetime_value
            normalized["datetime"] = {
                "year": datetime_val.year,
                "month": datetime_val.month,
                "day": datetime_val.day,
                "hours": datetime_val.hours,
                "minutes": datetime_val.minutes,
                "seconds": datetime_val.seconds,
                "nanos": datetime_val.nanos,
                "utcOffset": datetime_val.utc_offset.seconds if datetime_val.utc_offset else None,
                "timeZone": datetime_val.time_zone.id if datetime_val.time_zone else None
            }

        return normalized

    def _extract_text_styles(self, document) -> List[Dict[str, Any]]:
        """Extract text style information."""
        styles = []
        for style in document.text_styles:
            styles.append({
                "textAnchor": {
                    "textSegments": [
                        {
                            "startIndex": seg.start_index,
                            "endIndex": seg.end_index
                        }
                        for seg in style.text_anchor.text_segments
                    ]
                } if style.text_anchor else {},
                "color": {
                    "red": style.color.red,
                    "green": style.color.green,
                    "blue": style.color.blue,
                    "alpha": style.color.alpha
                } if style.color else {},
                "backgroundColor": {
                    "red": style.background_color.red,
                    "green": style.background_color.green,
                    "blue": style.background_color.blue,
                    "alpha": style.background_color.alpha
                } if style.background_color else {},
                "fontWeight": style.font_weight,
                "textStyle": style.text_style,
                "textDecoration": style.text_decoration,
                "fontSize": {
                    "size": style.font_size.size,
                    "unit": style.font_size.unit
                } if style.font_size else {}
            })
        return styles

    def _extract_document_style(self, document) -> Dict[str, Any]:
        """Extract document style information."""
        if not document.document_style:
            return {}

        return {
            "marginTop": {
                "magnitude": document.document_style.margin_top.magnitude,
                "unit": document.document_style.margin_top.unit
            } if document.document_style.margin_top else {},
            "marginRight": {
                "magnitude": document.document_style.margin_right.magnitude,
                "unit": document.document_style.margin_right.unit
            } if document.document_style.margin_right else {},
            "marginBottom": {
                "magnitude": document.document_style.margin_bottom.magnitude,
                "unit": document.document_style.margin_bottom.unit
            } if document.document_style.margin_bottom else {},
            "marginLeft": {
                "magnitude": document.document_style.margin_left.magnitude,
                "unit": document.document_style.margin_left.unit
            } if document.document_style.margin_left else {}
        }

    def _calculate_document_confidence(self, document) -> float:
        """Calculate overall document confidence."""
        confidences = []

        for page in document.pages:
            for paragraph in page.paragraphs:
                confidences.append(paragraph.layout.confidence)

        return sum(confidences) / len(confidences) if confidences else 0.0

    def _document_to_dict(self, document) -> Dict[str, Any]:
        """Convert Document AI response to dictionary for debugging."""
        return {
            "text": document.text,
            "pageCount": len(document.pages),
            "entityCount": len(document.entities),
            "hasTextStyles": len(document.text_styles) > 0,
            "hasDocumentStyle": document.document_style is not None
        }