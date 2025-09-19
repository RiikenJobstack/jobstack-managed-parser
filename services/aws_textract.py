"""
AWS Textract service implementation for document processing.
Optimized for PDFs and structured documents.
"""
import boto3
import json
import logging
from typing import Dict, Any, List
import time

logger = logging.getLogger(__name__)

class AWSTextractService:
    """AWS Textract service for extracting text and data from documents."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._client = None

    def _get_client(self):
        """Lazy initialization of AWS Textract client."""
        if not self._client:
            self._client = boto3.client(
                'textract',
                region_name=self.config.get('region', 'us-east-1'),
                aws_access_key_id=self.config.get('access_key_id'),
                aws_secret_access_key=self.config.get('secret_access_key')
            )
        return self._client

    async def process_document(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Process document using AWS Textract.

        Args:
            content: Document content as bytes
            filename: Original filename

        Returns:
            Extracted text and structure data
        """
        try:
            client = self._get_client()

            # Determine document type
            file_ext = filename.lower().split('.')[-1] if '.' in filename else 'pdf'

            # Start document analysis
            if file_ext == 'pdf':
                response = client.analyze_document(
                    Document={'Bytes': content},
                    FeatureTypes=['TABLES', 'FORMS']
                )
            else:
                # For images
                response = client.detect_document_text(
                    Document={'Bytes': content}
                )

            # Extract text and structure
            extracted_data = self._extract_textract_data(response)

            return {
                "success": True,
                "service": "aws_textract",
                "data": extracted_data,
                "raw_response": response  # Keep raw response for debugging
            }

        except Exception as e:
            logger.error(f"AWS Textract processing failed: {str(e)}")
            raise

    def _extract_textract_data(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data from Textract response."""
        blocks = response.get('Blocks', [])

        # Separate different types of blocks
        text_blocks = []
        table_blocks = []
        form_blocks = []

        for block in blocks:
            block_type = block.get('BlockType')
            if block_type == 'LINE':
                text_blocks.append(block)
            elif block_type == 'TABLE':
                table_blocks.append(block)
            elif block_type == 'KEY_VALUE_SET':
                form_blocks.append(block)

        # Extract plain text
        full_text = self._extract_plain_text(text_blocks)

        # Extract tables
        tables = self._extract_tables(blocks)

        # Extract key-value pairs
        key_values = self._extract_key_values(blocks)

        return {
            "extractedText": full_text,
            "tables": tables,
            "keyValuePairs": key_values,
            "confidence": self._calculate_average_confidence(blocks),
            "pageCount": len(set(block.get('Page', 1) for block in blocks)),
            "processingTime": time.time(),
            "metadata": {
                "totalBlocks": len(blocks),
                "textBlocks": len(text_blocks),
                "tableBlocks": len(table_blocks),
                "formBlocks": len(form_blocks)
            }
        }

    def _extract_plain_text(self, text_blocks: List[Dict]) -> str:
        """Extract plain text from text blocks."""
        lines = []
        for block in text_blocks:
            if 'Text' in block:
                lines.append(block['Text'])

        return '\n'.join(lines)

    def _extract_tables(self, blocks: List[Dict]) -> List[Dict[str, Any]]:
        """Extract table data from blocks."""
        tables = []

        # Build relationships
        block_map = {block['Id']: block for block in blocks}

        # Find table blocks
        for block in blocks:
            if block.get('BlockType') == 'TABLE':
                table = self._extract_single_table(block, block_map)
                if table:
                    tables.append(table)

        return tables

    def _extract_single_table(self, table_block: Dict, block_map: Dict) -> Dict[str, Any]:
        """Extract a single table from table block."""
        rows = []

        # Get relationships
        relationships = table_block.get('Relationships', [])
        cell_ids = []

        for relationship in relationships:
            if relationship.get('Type') == 'CHILD':
                cell_ids.extend(relationship.get('Ids', []))

        # Group cells by row
        cells_by_row = {}
        for cell_id in cell_ids:
            cell = block_map.get(cell_id)
            if cell and cell.get('BlockType') == 'CELL':
                row_index = cell.get('RowIndex', 1) - 1
                col_index = cell.get('ColumnIndex', 1) - 1

                if row_index not in cells_by_row:
                    cells_by_row[row_index] = {}

                # Get cell text
                cell_text = self._get_cell_text(cell, block_map)
                cells_by_row[row_index][col_index] = cell_text

        # Convert to ordered rows
        for row_idx in sorted(cells_by_row.keys()):
            row = cells_by_row[row_idx]
            row_data = [row.get(col_idx, '') for col_idx in sorted(row.keys())]
            rows.append(row_data)

        return {
            "rows": rows,
            "rowCount": len(rows),
            "columnCount": max(len(row) for row in rows) if rows else 0,
            "confidence": table_block.get('Confidence', 0)
        }

    def _get_cell_text(self, cell_block: Dict, block_map: Dict) -> str:
        """Extract text from a table cell."""
        text_parts = []

        relationships = cell_block.get('Relationships', [])
        for relationship in relationships:
            if relationship.get('Type') == 'CHILD':
                for word_id in relationship.get('Ids', []):
                    word_block = block_map.get(word_id)
                    if word_block and word_block.get('BlockType') == 'WORD':
                        text_parts.append(word_block.get('Text', ''))

        return ' '.join(text_parts)

    def _extract_key_values(self, blocks: List[Dict]) -> List[Dict[str, Any]]:
        """Extract key-value pairs from form blocks."""
        key_values = []
        block_map = {block['Id']: block for block in blocks}

        # Find key blocks
        for block in blocks:
            if (block.get('BlockType') == 'KEY_VALUE_SET' and
                block.get('EntityTypes') and 'KEY' in block['EntityTypes']):

                key_text = self._get_text_from_relationships(block, block_map)

                # Find corresponding value
                value_text = ""
                relationships = block.get('Relationships', [])
                for relationship in relationships:
                    if relationship.get('Type') == 'VALUE':
                        for value_id in relationship.get('Ids', []):
                            value_block = block_map.get(value_id)
                            if value_block:
                                value_text = self._get_text_from_relationships(value_block, block_map)

                if key_text:
                    key_values.append({
                        "key": key_text.strip(),
                        "value": value_text.strip(),
                        "confidence": block.get('Confidence', 0)
                    })

        return key_values

    def _get_text_from_relationships(self, block: Dict, block_map: Dict) -> str:
        """Extract text from block relationships."""
        text_parts = []

        relationships = block.get('Relationships', [])
        for relationship in relationships:
            if relationship.get('Type') == 'CHILD':
                for child_id in relationship.get('Ids', []):
                    child_block = block_map.get(child_id)
                    if child_block and child_block.get('BlockType') == 'WORD':
                        text_parts.append(child_block.get('Text', ''))

        return ' '.join(text_parts)

    def _calculate_average_confidence(self, blocks: List[Dict]) -> float:
        """Calculate average confidence score across all blocks."""
        confidences = [block.get('Confidence', 0) for block in blocks if 'Confidence' in block]
        return sum(confidences) / len(confidences) if confidences else 0.0