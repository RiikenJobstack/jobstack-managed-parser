"""
Azure Form Recognizer service implementation for document processing.
Optimized for forms, invoices, and Office documents.
"""
import json
import logging
from typing import Dict, Any, List
import time
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)

class AzureFormRecognizerService:
    """Azure Form Recognizer service for document analysis and data extraction."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._client = None
        self.endpoint = config.get('endpoint')
        self.api_key = config.get('api_key')

    def _get_client(self):
        """Lazy initialization of Azure Form Recognizer client."""
        if not self._client:
            self._client = DocumentAnalysisClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.api_key)
            )
        return self._client

    async def process_document(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Process document using Azure Form Recognizer.

        Args:
            content: Document content as bytes
            filename: Original filename

        Returns:
            Extracted text and structure data
        """
        try:
            client = self._get_client()

            # Determine model to use based on document type
            file_ext = filename.lower().split('.')[-1] if '.' in filename else 'pdf'
            model_id = self._get_model_id(file_ext)

            # Analyze document
            poller = client.begin_analyze_document(model_id, content)
            result = poller.result()

            # Extract structured data
            extracted_data = self._extract_azure_data(result)

            return {
                "success": True,
                "service": "azure_form_recognizer",
                "data": extracted_data,
                "raw_response": self._result_to_dict(result)
            }

        except Exception as e:
            logger.error(f"Azure Form Recognizer processing failed: {str(e)}")
            raise

    def _get_model_id(self, file_ext: str) -> str:
        """Get appropriate model ID based on file extension."""
        # Use prebuilt models for better accuracy
        if file_ext in ['pdf', 'png', 'jpg', 'jpeg']:
            return "prebuilt-document"  # General document model
        elif file_ext == 'docx':
            return "prebuilt-document"  # Also works for Word docs
        else:
            return "prebuilt-read"  # Fallback for OCR-only

    def _extract_azure_data(self, result) -> Dict[str, Any]:
        """Extract structured data from Azure Form Recognizer response."""
        # Get full content
        full_content = result.content

        # Extract pages
        pages_data = []
        for page in result.pages:
            page_data = self._extract_page_data(page)
            pages_data.append(page_data)

        # Extract tables
        tables = self._extract_tables(result.tables)

        # Extract key-value pairs
        key_value_pairs = self._extract_key_value_pairs(result.key_value_pairs)

        # Extract entities
        entities = self._extract_entities(result.entities) if hasattr(result, 'entities') else []

        # Extract paragraphs
        paragraphs = self._extract_paragraphs(result.paragraphs)

        # Extract styles
        styles = self._extract_styles(result.styles) if hasattr(result, 'styles') else []

        return {
            "extractedText": full_content,
            "pages": pages_data,
            "tables": tables,
            "keyValuePairs": key_value_pairs,
            "entities": entities,
            "paragraphs": paragraphs,
            "styles": styles,
            "confidence": self._calculate_average_confidence(result),
            "pageCount": len(result.pages),
            "processingTime": time.time(),
            "metadata": {
                "modelId": result.model_id,
                "apiVersion": result.api_version,
                "tablesCount": len(result.tables),
                "keyValuePairsCount": len(result.key_value_pairs),
                "entitiesCount": len(result.entities) if hasattr(result, 'entities') else 0
            }
        }

    def _extract_page_data(self, page) -> Dict[str, Any]:
        """Extract data from a single page."""
        # Extract lines
        lines = []
        for line in page.lines:
            lines.append({
                "content": line.content,
                "polygon": [{"x": point.x, "y": point.y} for point in line.polygon],
                "spans": [{"offset": span.offset, "length": span.length} for span in line.spans]
            })

        # Extract words
        words = []
        for word in page.words:
            words.append({
                "content": word.content,
                "confidence": word.confidence,
                "polygon": [{"x": point.x, "y": point.y} for point in word.polygon],
                "span": {"offset": word.span.offset, "length": word.span.length}
            })

        # Extract selection marks (checkboxes, radio buttons)
        selection_marks = []
        for selection_mark in page.selection_marks:
            selection_marks.append({
                "state": selection_mark.state,
                "confidence": selection_mark.confidence,
                "polygon": [{"x": point.x, "y": point.y} for point in selection_mark.polygon],
                "span": {"offset": selection_mark.span.offset, "length": selection_mark.span.length}
            })

        return {
            "pageNumber": page.page_number,
            "angle": page.angle,
            "width": page.width,
            "height": page.height,
            "unit": page.unit,
            "lines": lines,
            "words": words,
            "selectionMarks": selection_marks
        }

    def _extract_tables(self, tables) -> List[Dict[str, Any]]:
        """Extract table data."""
        tables_data = []

        for table in tables:
            # Extract cells
            cells = []
            for cell in table.cells:
                cells.append({
                    "rowIndex": cell.row_index,
                    "columnIndex": cell.column_index,
                    "rowSpan": cell.row_span,
                    "columnSpan": cell.column_span,
                    "content": cell.content,
                    "kind": cell.kind,
                    "confidence": cell.confidence,
                    "polygon": [{"x": point.x, "y": point.y} for point in cell.polygon],
                    "spans": [{"offset": span.offset, "length": span.length} for span in cell.spans]
                })

            # Organize cells into rows
            rows_dict = {}
            for cell in cells:
                row_idx = cell["rowIndex"]
                if row_idx not in rows_dict:
                    rows_dict[row_idx] = []
                rows_dict[row_idx].append(cell)

            # Sort cells within each row by column index
            sorted_rows = []
            for row_idx in sorted(rows_dict.keys()):
                sorted_cells = sorted(rows_dict[row_idx], key=lambda c: c["columnIndex"])
                sorted_rows.append(sorted_cells)

            tables_data.append({
                "rowCount": table.row_count,
                "columnCount": table.column_count,
                "cells": cells,
                "rows": sorted_rows,
                "polygon": [{"x": point.x, "y": point.y} for point in table.polygon],
                "spans": [{"offset": span.offset, "length": span.length} for span in table.spans]
            })

        return tables_data

    def _extract_key_value_pairs(self, key_value_pairs) -> List[Dict[str, Any]]:
        """Extract key-value pairs."""
        pairs = []

        for kv_pair in key_value_pairs:
            pair_data = {
                "confidence": kv_pair.confidence
            }

            # Extract key
            if kv_pair.key:
                pair_data["key"] = {
                    "content": kv_pair.key.content,
                    "polygon": [{"x": point.x, "y": point.y} for point in kv_pair.key.polygon],
                    "spans": [{"offset": span.offset, "length": span.length} for span in kv_pair.key.spans]
                }

            # Extract value
            if kv_pair.value:
                pair_data["value"] = {
                    "content": kv_pair.value.content,
                    "polygon": [{"x": point.x, "y": point.y} for point in kv_pair.value.polygon],
                    "spans": [{"offset": span.offset, "length": span.length} for span in kv_pair.value.spans]
                }

            pairs.append(pair_data)

        return pairs

    def _extract_entities(self, entities) -> List[Dict[str, Any]]:
        """Extract entities (if available)."""
        entities_data = []

        for entity in entities:
            entity_data = {
                "category": entity.category,
                "subCategory": entity.sub_category,
                "content": entity.content,
                "confidence": entity.confidence,
                "polygon": [{"x": point.x, "y": point.y} for point in entity.polygon],
                "spans": [{"offset": span.offset, "length": span.length} for span in entity.spans]
            }

            entities_data.append(entity_data)

        return entities_data

    def _extract_paragraphs(self, paragraphs) -> List[Dict[str, Any]]:
        """Extract paragraph information."""
        paragraphs_data = []

        for paragraph in paragraphs:
            paragraph_data = {
                "content": paragraph.content,
                "polygon": [{"x": point.x, "y": point.y} for point in paragraph.polygon],
                "spans": [{"offset": span.offset, "length": span.length} for span in paragraph.spans],
                "role": paragraph.role
            }

            paragraphs_data.append(paragraph_data)

        return paragraphs_data

    def _extract_styles(self, styles) -> List[Dict[str, Any]]:
        """Extract style information."""
        styles_data = []

        for style in styles:
            style_data = {
                "isHandwritten": style.is_handwritten,
                "confidence": style.confidence,
                "spans": [{"offset": span.offset, "length": span.length} for span in style.spans]
            }

            styles_data.append(style_data)

        return styles_data

    def _calculate_average_confidence(self, result) -> float:
        """Calculate average confidence across all elements."""
        confidences = []

        # Collect confidences from different elements
        for page in result.pages:
            for word in page.words:
                if hasattr(word, 'confidence') and word.confidence:
                    confidences.append(word.confidence)

        for table in result.tables:
            for cell in table.cells:
                if hasattr(cell, 'confidence') and cell.confidence:
                    confidences.append(cell.confidence)

        for kv_pair in result.key_value_pairs:
            if hasattr(kv_pair, 'confidence') and kv_pair.confidence:
                confidences.append(kv_pair.confidence)

        return sum(confidences) / len(confidences) if confidences else 0.0

    def _result_to_dict(self, result) -> Dict[str, Any]:
        """Convert Azure result to dictionary for debugging."""
        return {
            "modelId": result.model_id,
            "apiVersion": result.api_version,
            "content": result.content[:500] + "..." if len(result.content) > 500 else result.content,
            "pageCount": len(result.pages),
            "tablesCount": len(result.tables),
            "keyValuePairsCount": len(result.key_value_pairs),
            "hasEntities": hasattr(result, 'entities') and len(result.entities) > 0,
            "hasStyles": hasattr(result, 'styles') and len(result.styles) > 0
        }