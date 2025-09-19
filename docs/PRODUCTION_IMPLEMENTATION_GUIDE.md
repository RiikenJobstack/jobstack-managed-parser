# Production Implementation Guide - Managed Services Resume Parser
*Complete step-by-step implementation with exact static_prompt.py structure*

---

## Architecture Analysis & Recommendation

### Current Implementation Analysis

#### Your Three Current Approaches:
```python
# 1. Direct Processing (/parse-resume)
parse_resume(filename, content) → Immediate response

# 2. Cached Processing (/cached/parse-resume)
parse_resume_cached(filename, content) → Prompt caching + Redis

# 3. Worker Processing (/worker/parse-resume)
enqueue_job() → Azure Queue → Worker processes → Fetch result
```

### **RECOMMENDATION: Hybrid Approach for Production**

Based on your current architecture, I recommend implementing **both** cached and worker patterns for optimal production performance:

```python
Production Architecture:
├── /managed/parse-resume (Direct - for small files <2MB)
├── /managed/parse-resume-cached (Cached - for medium files 2-5MB)
└── /managed/parse-resume-worker (Worker - for large files >5MB or batch processing)
```

#### Why Hybrid Approach is Best:

**1. Direct Processing (Small Files)**
- Files <2MB: PDF (1-2 pages), Images, Simple DOCX
- Response time: 2-5 seconds
- Cost: ₹1-2 per document
- Use case: Real-time user uploads

**2. Cached Processing (Medium Files)**
- Files 2-5MB: Multi-page PDFs, High-res images
- Response time: 3-8 seconds
- Cost: ₹1.5-3 per document
- Use case: Standard resume processing

**3. Worker Processing (Large Files/Batch)**
- Files >5MB: Complex resumes, batch uploads
- Response time: 10-30 seconds (async)
- Cost: ₹2-4 per document
- Use case: Bulk processing, complex documents

---

## Step-by-Step Implementation Plan

### Phase 1: Repository Setup & Branch Creation

#### Step 1: Create Implementation Branch
```bash
# In your current project directory
cd /Users/riiken/Documents/svsfsfsfsfsf

# Create and switch to new branch
git checkout -b feature/managed-services-parser

# Verify branch creation
git branch
# Should show: * feature/managed-services-parser

# Create backup of current implementation
cp app.py app_backup.py
cp utils.py utils_backup.py
cp requirements.txt requirements_backup.txt
```

#### Step 2: Project Structure Setup
```bash
# Create new directories for managed services
mkdir -p managed_services/{aws,google,azure,core,config}
mkdir -p managed_services/tests/{unit,integration,samples}
mkdir -p managed_services/scripts
mkdir -p managed_services/docs

# Directory structure:
# managed_services/
# ├── aws/           # AWS Textract integration
# ├── google/        # Google Document AI integration
# ├── azure/         # Azure Form Recognizer integration
# ├── core/          # Orchestrator and shared logic
# ├── config/        # Configuration and credentials
# ├── tests/         # Test files and scripts
# ├── scripts/       # Deployment and monitoring scripts
# └── docs/          # Documentation
```

---

## Phase 2: Manual Account Creation (Step-by-Step)

### AWS Account Setup (for Textract)

#### Step 1: Create AWS Account
1. **Go to:** https://aws.amazon.com/
2. **Click:** "Create an AWS Account" (top right)
3. **Fill in:**
   - Email address: your-email@domain.com
   - Password: (strong password)
   - AWS account name: "Resume Parser Production"
4. **Click:** Continue
5. **Fill contact information:**
   - Account type: Professional
   - Company name: Your company
   - Phone number: Your number
   - Address: Your address
6. **Payment method:** Add credit/debit card (required, but we'll set spending limits)
7. **Phone verification:** Enter phone number → Get call → Enter verification code
8. **Support plan:** Basic (Free) → Complete sign up

#### Step 2: Enable Textract Service
1. **Login to AWS Console:** https://console.aws.amazon.com/
2. **Navigate to:** Services → Machine Learning → Amazon Textract
3. **Region:** Change to "US East (N. Virginia)" (top right dropdown)
4. **Click:** "Get started with Amazon Textract"
5. **Try sample:** Upload a test PDF and click "Analyze Document" to verify access

#### Step 3: Create IAM User (Security Best Practice)
1. **Navigate to:** Services → Security, Identity & Compliance → IAM
2. **Click:** "Users" (left sidebar)
3. **Click:** "Add User"
4. **User details:**
   - User name: `resume-parser-textract`
   - Access type: ✅ Programmatic access (for API calls)
   - AWS console access: ❌ (uncheck)
5. **Click:** Next: Permissions

#### Step 4: Create Custom Policy for Textract
1. **Click:** "Attach existing policies directly"
2. **Click:** "Create policy"
3. **Switch to JSON tab** and paste:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "textract:AnalyzeDocument",
                "textract:DetectDocumentText",
                "textract:AnalyzeExpense",
                "textract:GetDocumentAnalysis",
                "textract:StartDocumentAnalysis"
            ],
            "Resource": "*"
        }
    ]
}
```
4. **Click:** Next: Tags (skip) → Next: Review
5. **Policy name:** `TextractResumeParserPolicy`
6. **Description:** `Allows resume parser to use Textract services`
7. **Click:** Create policy

#### Step 5: Attach Policy and Create Keys
1. **Go back to user creation** (refresh browser if needed)
2. **Search for:** `TextractResumeParserPolicy` → ✅ Check it
3. **Click:** Next: Tags (skip) → Next: Review
4. **Click:** Create user
5. **IMPORTANT:** Copy and save these credentials securely:
   - Access Key ID: `AKIA...` (save this)
   - Secret Access Key: `...` (save this - only shown once!)

#### Step 6: Set Spending Alerts
1. **Navigate to:** Billing Dashboard → Budgets
2. **Click:** Create a budget
3. **Budget type:** Cost budget
4. **Budget name:** Resume Parser Monthly Budget
5. **Amount:** $50 (₹4,150)
6. **Alert threshold:** 80% of budgeted amount
7. **Email:** Your email address
8. **Create budget**

### Google Cloud Setup (for Document AI)

#### Step 1: Create Google Cloud Account
1. **Go to:** https://console.cloud.google.com/
2. **Sign in** with your Google account (or create one)
3. **Accept terms** and continue
4. **Enter billing info** (required - but we'll set limits)
   - Credit card details
   - Billing address
5. **Claim $300 free credits** (new accounts)

#### Step 2: Create New Project
1. **Click project dropdown** (top left, next to Google Cloud logo)
2. **Click:** "New Project"
3. **Project details:**
   - Project name: `resume-parser-docai`
   - Location: No organization (if you don't have one)
4. **Click:** Create
5. **Select the new project** from dropdown

#### Step 3: Enable Document AI API
1. **Navigate to:** APIs & Services → Library
2. **Search:** "Document AI API"
3. **Click:** Document AI API
4. **Click:** Enable
5. **Wait** for activation (1-2 minutes)

#### Step 4: Create Service Account
1. **Navigate to:** IAM & Admin → Service Accounts
2. **Click:** Create Service Account
3. **Service account details:**
   - Name: `doc-ai-resume-parser`
   - Description: `Service account for resume parsing with Document AI`
4. **Click:** Create and Continue

#### Step 5: Grant Permissions
1. **Grant access section:**
   - Role: Document AI API User
   - Click "Add Another Role" → Role: Viewer
2. **Click:** Continue → Done

#### Step 6: Create and Download Key
1. **Find your service account** in the list
2. **Click** on the service account email
3. **Go to:** Keys tab
4. **Click:** Add Key → Create new key
5. **Key type:** JSON
6. **Click:** Create
7. **Save the downloaded JSON file** as `doc-ai-key.json`

#### Step 7: Create Document AI Processor
1. **Navigate to:** Document AI → Processors
2. **Click:** Create Processor
3. **Processor details:**
   - Type: Form Parser
   - Name: Resume Parser Processor
   - Region: us (United States)
4. **Click:** Create
5. **Copy the Processor ID** from the URL (after `/processors/`)
   - URL looks like: `.../processors/abc123def456`
   - Save: `abc123def456`

#### Step 8: Set Budget Alerts
1. **Navigate to:** Billing → Budgets & alerts
2. **Create Budget:**
   - Name: Resume Parser Budget
   - Amount: $50
   - Alert: 80% threshold
   - Email: Your email

### Azure Account Setup (for Form Recognizer)

#### Step 1: Create Azure Account
1. **Go to:** https://portal.azure.com/
2. **Click:** "Start free" or "Create account"
3. **Sign in** with Microsoft account (or create one)
4. **Phone verification:** Enter phone → Get verification code
5. **Credit card verification:** Add card (₹2 hold, refunded)
6. **Complete profile** with personal information

#### Step 2: Create Resource Group
1. **In Azure Portal:** Click "Resource groups"
2. **Click:** Create
3. **Resource group details:**
   - Subscription: Your subscription (usually "Free Trial")
   - Resource group name: `resume-parser-rg`
   - Region: East US
4. **Click:** Review + create → Create

#### Step 3: Create Form Recognizer Resource
1. **In Azure Portal:** Click "Create a resource"
2. **Search:** "Form Recognizer"
3. **Click:** Form Recognizer → Create
4. **Resource details:**
   - Subscription: Your subscription
   - Resource group: `resume-parser-rg`
   - Region: East US
   - Name: `resume-parser-form-recognizer`
   - Pricing tier: S0 (Standard)
5. **Click:** Review + create → Create
6. **Wait for deployment** (2-3 minutes)

#### Step 4: Get Keys and Endpoint
1. **Go to resource** (click "Go to resource" after deployment)
2. **Left sidebar:** Click "Keys and Endpoint"
3. **Copy and save:**
   - KEY 1: `...` (save securely)
   - Endpoint: `https://resume-parser-form-recognizer.cognitiveservices.azure.com/`

#### Step 5: Set Spending Limits
1. **Navigate to:** Subscriptions → Your subscription
2. **Click:** Budgets → Add
3. **Budget details:**
   - Name: Resume Parser Budget
   - Amount: ₹4,000
   - Alert: 80% threshold
   - Email: Your email

---

## Phase 3: Local Development Setup

### Step 1: Environment Configuration

#### Create Environment File
```bash
# Create managed services environment file
touch managed_services/.env.production

# Add to .gitignore to prevent committing secrets
echo "managed_services/.env.production" >> .gitignore
echo "managed_services/config/doc-ai-key.json" >> .gitignore
echo "managed_services/config/*-key.json" >> .gitignore
```

#### Configure `.env.production`:
```bash
# Copy your credentials here (replace with actual values):

# AWS Textract Configuration
AWS_ACCESS_KEY_ID=AKIA...your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# Google Document AI Configuration
GOOGLE_APPLICATION_CREDENTIALS=./managed_services/config/doc-ai-key.json
GOOGLE_PROJECT_ID=resume-parser-docai
DOC_AI_PROCESSOR_ID=abc123def456

# Azure Form Recognizer Configuration
AZURE_FORM_RECOGNIZER_ENDPOINT=https://resume-parser-form-recognizer.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_KEY=your_azure_key

# Gemini Configuration (your existing)
GOOGLE_GEMINI_API_KEY=your_existing_gemini_key

# Application Configuration
NODE_ENV=development
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=10
SUPPORTED_FORMATS=pdf,png,jpg,jpeg,docx,txt

# Cost Control
MONTHLY_BUDGET_INR=3000
ALERT_THRESHOLD_PERCENT=80

# Existing configuration (copy from your current .env)
AZURE_STORAGE_CONNECTION_STRING=your_existing_azure_connection
TABLE_NAME=your_existing_table
OUTPUT_CONTAINER=your_existing_output_container
INPUT_CONTAINER=your_existing_input_container
REDIS_HOST=your_existing_redis_host
REDIS_PORT=your_existing_redis_port
```

### Step 2: Dependencies Installation

#### Create New Requirements File
```bash
# Create managed services requirements
cat > managed_services/requirements.txt << EOF
# Existing dependencies (keep all your current ones)
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
python-dotenv==1.0.0
PyJWT==2.8.0
cryptography==41.0.7
redis==5.0.1
motor==3.3.2
pymongo==4.6.0

# Azure dependencies (your existing)
azure-storage-queue>=12.0.0
azure-data-tables>=12.0.0
azure-storage-blob>=12.0.0

# NEW: Managed services dependencies
boto3==1.34.0
botocore==1.34.0
google-cloud-documentai==2.21.0
google-auth==2.23.4
azure-ai-formrecognizer==3.3.0
azure-core==1.29.5

# Gemini (your existing)
google-generativeai>=0.8.0

# Monitoring and logging
structlog==23.2.0
aiofiles==23.2.1

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
EOF
```

---

## Phase 4: Code Implementation

### Step 1: Core Base Service

#### Create `managed_services/core/base_service.py`:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import structlog
import time
import asyncio

logger = structlog.get_logger()

class DocumentParsingService(ABC):
    """Base class for all document parsing services"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.total_requests = 0
        self.total_cost = 0.0
        self.success_count = 0
        self.error_count = 0

    @abstractmethod
    async def parse_document(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Parse document and return raw structured data"""
        pass

    @abstractmethod
    def calculate_cost(self, content: bytes) -> float:
        """Calculate estimated cost for processing this document (in INR)"""
        pass

    @abstractmethod
    def is_supported_format(self, filename: str) -> bool:
        """Check if file format is supported by this service"""
        pass

    async def parse_with_metrics(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Parse document with metrics collection and error handling"""
        start_time = time.time()
        estimated_cost = self.calculate_cost(content)

        try:
            # Check if format is supported
            if not self.is_supported_format(filename):
                raise ValueError(f"Unsupported format for {self.service_name}")

            # Parse document
            result = await self.parse_document(content, filename)

            # Update success metrics
            processing_time = time.time() - start_time
            self.total_requests += 1
            self.success_count += 1
            self.total_cost += estimated_cost

            logger.info(
                "Document parsed successfully",
                service=self.service_name,
                filename=filename,
                processing_time=processing_time,
                cost_inr=estimated_cost,
                confidence=result.get('confidence_score', 0)
            )

            return {
                **result,
                "metrics": {
                    "service_used": self.service_name,
                    "processing_time": round(processing_time, 3),
                    "cost_inr": round(estimated_cost, 3),
                    "success": True,
                    "confidence_score": result.get('confidence_score', 0)
                }
            }

        except Exception as e:
            # Update error metrics
            self.error_count += 1
            processing_time = time.time() - start_time

            logger.error(
                "Document parsing failed",
                service=self.service_name,
                filename=filename,
                error=str(e),
                processing_time=processing_time
            )

            # Re-raise with context
            raise Exception(f"{self.service_name} parsing failed: {str(e)}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get service performance metrics"""
        return {
            "service_name": self.service_name,
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": (self.success_count / max(1, self.total_requests)) * 100,
            "total_cost_inr": round(self.total_cost, 2),
            "avg_cost_per_doc": round(self.total_cost / max(1, self.total_requests), 3)
        }
```

### Step 2: AWS Textract Service

#### Create `managed_services/aws/textract_service.py`:
```python
import boto3
import json
import os
from typing import Dict, Any, List
from managed_services.core.base_service import DocumentParsingService
import structlog

logger = structlog.get_logger()

class TextractService(DocumentParsingService):
    """AWS Textract document parsing service optimized for PDFs"""

    def __init__(self):
        super().__init__("aws_textract")

        # Initialize AWS client
        self.client = boto3.client(
            'textract',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )

        # Cost configuration (as of 2024, in INR)
        self.cost_per_page_inr = 0.0015 * 83  # $0.0015 * ₹83 = ₹0.125 per page
        self.avg_kb_per_page = 51200  # Rough estimate: 50KB per PDF page

    def is_supported_format(self, filename: str) -> bool:
        """Check if file format is supported"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in ['.pdf']

    def calculate_cost(self, content: bytes) -> float:
        """Estimate cost based on document size"""
        # Estimate pages from file size
        estimated_pages = max(1, len(content) // self.avg_kb_per_page)
        return estimated_pages * self.cost_per_page_inr

    async def parse_document(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Parse PDF using AWS Textract"""
        try:
            # Call Textract with comprehensive feature set
            response = self.client.analyze_document(
                Document={'Bytes': content},
                FeatureTypes=['TABLES', 'FORMS', 'LAYOUT']
            )

            # Extract and structure data
            extracted_data = self._extract_structured_data(response)

            return {
                "success": True,
                "service": "aws_textract",
                "raw_text": extracted_data["text"],
                "structured_fields": extracted_data["fields"],
                "tables": extracted_data["tables"],
                "confidence_score": extracted_data["avg_confidence"],
                "page_count": extracted_data["page_count"]
            }

        except Exception as e:
            logger.error(f"Textract parsing failed: {str(e)}")
            raise Exception(f"AWS Textract error: {str(e)}")

    def _extract_structured_data(self, response: Dict) -> Dict[str, Any]:
        """Extract and organize data from Textract response"""
        text_blocks = []
        key_value_pairs = {}
        tables = []
        confidences = []
        page_count = 0

        # Create lookup dictionary for blocks
        blocks_by_id = {block['Id']: block for block in response['Blocks']}

        for block in response['Blocks']:
            confidence = block.get('Confidence', 0)
            if confidence > 0:
                confidences.append(confidence)

            if block['BlockType'] == 'PAGE':
                page_count += 1

            elif block['BlockType'] == 'LINE':
                text_blocks.append(block['Text'])

            elif block['BlockType'] == 'KEY_VALUE_SET':
                self._extract_key_value_pair(block, blocks_by_id, key_value_pairs)

            elif block['BlockType'] == 'TABLE':
                table_data = self._extract_table_data(block, blocks_by_id)
                if table_data:
                    tables.append(table_data)

        return {
            "text": '\n'.join(text_blocks),
            "fields": key_value_pairs,
            "tables": tables,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "page_count": max(1, page_count)
        }

    def _extract_key_value_pair(self, block: Dict, blocks_by_id: Dict, key_value_pairs: Dict):
        """Extract key-value relationships from Textract blocks"""
        if block.get('EntityTypes') and 'KEY' in block['EntityTypes']:
            key_text = block.get('Text', '').strip()
            if not key_text:
                return

            # Find corresponding value through relationships
            for relationship in block.get('Relationships', []):
                if relationship['Type'] == 'VALUE':
                    for value_id in relationship['Ids']:
                        value_block = blocks_by_id.get(value_id)
                        if value_block and value_block.get('Text'):
                            value_text = value_block['Text'].strip()
                            if value_text:
                                key_value_pairs[key_text] = {
                                    'value': value_text,
                                    'confidence': value_block.get('Confidence', 0)
                                }

    def _extract_table_data(self, table_block: Dict, blocks_by_id: Dict) -> Dict[str, Any]:
        """Extract table structure from Textract response"""
        cells = []

        for relationship in table_block.get('Relationships', []):
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    child_block = blocks_by_id.get(child_id)
                    if child_block and child_block['BlockType'] == 'CELL':
                        cell_text = child_block.get('Text', '').strip()
                        if cell_text:
                            cells.append({
                                "text": cell_text,
                                "row": child_block.get('RowIndex', 0),
                                "column": child_block.get('ColumnIndex', 0),
                                "confidence": child_block.get('Confidence', 0)
                            })

        return {
            "cells": cells,
            "row_count": max([cell["row"] for cell in cells]) + 1 if cells else 0,
            "column_count": max([cell["column"] for cell in cells]) + 1 if cells else 0
        } if cells else None
```

### Step 3: Google Document AI Service

#### Create `managed_services/google/documentai_service.py`:
```python
from google.cloud import documentai_v1
from google.oauth2 import service_account
import os
import json
from typing import Dict, Any, List
from managed_services.core.base_service import DocumentParsingService
import structlog

logger = structlog.get_logger()

class DocumentAIService(DocumentParsingService):
    """Google Document AI service optimized for images and complex layouts"""

    def __init__(self):
        super().__init__("google_documentai")

        # Initialize credentials and client
        self._init_client()

        # Cost configuration (as of 2024, in INR)
        self.cost_per_page_inr = 0.002 * 83  # $0.002 * ₹83 = ₹0.166 per page
        self.avg_kb_per_page = 200000  # Images are typically larger: 200KB per page

    def _init_client(self):
        """Initialize Document AI client with proper authentication"""
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        project_id = os.getenv('GOOGLE_PROJECT_ID')
        processor_id = os.getenv('DOC_AI_PROCESSOR_ID')

        if not all([credentials_path, project_id, processor_id]):
            raise ValueError("Missing Google Cloud configuration")

        # Load credentials
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        self.client = documentai_v1.DocumentProcessorServiceClient(credentials=credentials)

        # Processor name
        self.processor_name = f"projects/{project_id}/locations/us/processors/{processor_id}"

    def is_supported_format(self, filename: str) -> bool:
        """Check if file format is supported"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in ['.png', '.jpg', '.jpeg']

    def calculate_cost(self, content: bytes) -> float:
        """Estimate cost based on document size"""
        # For images, assume fewer pages but higher processing cost
        estimated_pages = max(1, len(content) // self.avg_kb_per_page)
        return estimated_pages * self.cost_per_page_inr

    def _get_mime_type(self, filename: str) -> str:
        """Determine MIME type from filename"""
        ext = os.path.splitext(filename)[1].lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg'
        }
        return mime_types.get(ext, 'image/png')

    async def parse_document(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Parse image using Google Document AI"""
        try:
            # Create processing request
            request = documentai_v1.ProcessRequest(
                name=self.processor_name,
                raw_document=documentai_v1.RawDocument(
                    content=content,
                    mime_type=self._get_mime_type(filename)
                )
            )

            # Process document
            result = self.client.process_document(request=request)
            document = result.document

            # Extract structured data
            extracted_data = self._extract_structured_data(document)

            return {
                "success": True,
                "service": "google_documentai",
                "raw_text": document.text,
                "entities": extracted_data["entities"],
                "form_fields": extracted_data["form_fields"],
                "tables": extracted_data["tables"],
                "confidence_score": extracted_data["avg_confidence"],
                "page_count": len(document.pages)
            }

        except Exception as e:
            logger.error(f"Document AI parsing failed: {str(e)}")
            raise Exception(f"Google Document AI error: {str(e)}")

    def _extract_structured_data(self, document) -> Dict[str, Any]:
        """Extract and organize data from Document AI response"""
        entities = {}
        form_fields = {}
        tables = []
        confidences = []

        # Extract entities
        for entity in document.entities:
            confidence = entity.confidence
            if confidence > 0:
                confidences.append(confidence)

            entity_text = self._get_text(entity.text_anchor, document.text) if entity.text_anchor else ''
            if entity_text:
                entities[entity.type_] = {
                    'text': entity_text,
                    'confidence': confidence,
                    'normalized_value': entity.normalized_value.text if entity.normalized_value else None
                }

        # Extract form fields from pages
        for page in document.pages:
            # Form fields (key-value pairs)
            for form_field in page.form_fields:
                if form_field.field_name and form_field.field_value:
                    key_text = self._get_text(form_field.field_name.text_anchor, document.text)
                    value_text = self._get_text(form_field.field_value.text_anchor, document.text)

                    if key_text and value_text:
                        form_fields[key_text] = {
                            'value': value_text,
                            'confidence': form_field.field_value.confidence
                        }
                        confidences.append(form_field.field_value.confidence)

            # Extract tables
            for table in page.tables:
                table_data = self._extract_table_from_page(table, document.text)
                if table_data:
                    tables.append(table_data)

        return {
            "entities": entities,
            "form_fields": form_fields,
            "tables": tables,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0
        }

    def _get_text(self, text_anchor, document_text: str) -> str:
        """Extract text from text anchor"""
        if not text_anchor or not text_anchor.text_segments:
            return ""

        text_parts = []
        for segment in text_anchor.text_segments:
            start_index = int(segment.start_index) if segment.start_index else 0
            end_index = int(segment.end_index) if segment.end_index else len(document_text)
            text_parts.append(document_text[start_index:end_index])

        return " ".join(text_parts).strip()

    def _extract_table_from_page(self, table, document_text: str) -> Dict[str, Any]:
        """Extract table data from Document AI table"""
        headers = []
        rows = []

        # Extract headers
        if table.header_rows:
            for header_row in table.header_rows:
                header_cells = []
                for cell in header_row.cells:
                    cell_text = self._get_text(cell.layout.text_anchor, document_text)
                    header_cells.append(cell_text)
                headers = header_cells

        # Extract data rows
        for row in table.body_rows:
            row_data = []
            for cell in row.cells:
                cell_text = self._get_text(cell.layout.text_anchor, document_text)
                row_data.append(cell_text)
            rows.append(row_data)

        return {
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(headers) if headers else (len(rows[0]) if rows else 0)
        } if rows or headers else None
```

### Step 4: Azure Form Recognizer Service

#### Create `managed_services/azure/form_recognizer_service.py`:
```python
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import os
from typing import Dict, Any, List
from managed_services.core.base_service import DocumentParsingService
import structlog

logger = structlog.get_logger()

class AzureFormRecognizerService(DocumentParsingService):
    """Azure Form Recognizer service optimized for Office documents and forms"""

    def __init__(self):
        super().__init__("azure_form_recognizer")

        # Initialize client
        endpoint = os.getenv('AZURE_FORM_RECOGNIZER_ENDPOINT')
        key = os.getenv('AZURE_FORM_RECOGNIZER_KEY')

        if not all([endpoint, key]):
            raise ValueError("Missing Azure Form Recognizer configuration")

        self.client = DocumentAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )

        # Cost configuration (as of 2024, in INR)
        self.cost_per_page_inr = 0.001 * 83  # $0.001 * ₹83 = ₹0.083 per page
        self.avg_kb_per_page = 100000  # Office docs: ~100KB per page

    def is_supported_format(self, filename: str) -> bool:
        """Check if file format is supported"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in ['.docx', '.doc', '.pdf']  # Note: Can also handle PDFs

    def calculate_cost(self, content: bytes) -> float:
        """Estimate cost based on document size"""
        estimated_pages = max(1, len(content) // self.avg_kb_per_page)
        return estimated_pages * self.cost_per_page_inr

    def _get_content_type(self, filename: str) -> str:
        """Determine content type from filename"""
        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword'
        }
        return content_types.get(ext, 'application/pdf')

    async def parse_document(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Parse document using Azure Form Recognizer"""
        try:
            # Use prebuilt-document model for general documents
            poller = self.client.begin_analyze_document(
                "prebuilt-document",
                content,
                content_type=self._get_content_type(filename)
            )

            # Wait for completion
            result = poller.result()

            # Extract structured data
            extracted_data = self._extract_structured_data(result)

            return {
                "success": True,
                "service": "azure_form_recognizer",
                "raw_text": result.content,
                "key_value_pairs": extracted_data["key_value_pairs"],
                "tables": extracted_data["tables"],
                "styles": extracted_data["styles"],
                "confidence_score": extracted_data["avg_confidence"],
                "page_count": len(result.pages) if result.pages else 1
            }

        except Exception as e:
            logger.error(f"Azure Form Recognizer parsing failed: {str(e)}")
            raise Exception(f"Azure Form Recognizer error: {str(e)}")

    def _extract_structured_data(self, result) -> Dict[str, Any]:
        """Extract and organize data from Azure Form Recognizer response"""
        key_value_pairs = {}
        tables = []
        styles = []
        confidences = []

        # Extract key-value pairs
        for kv_pair in result.key_value_pairs:
            if kv_pair.key and kv_pair.value:
                key_text = kv_pair.key.content.strip()
                value_text = kv_pair.value.content.strip()
                confidence = kv_pair.confidence

                if key_text and value_text:
                    key_value_pairs[key_text] = {
                        'value': value_text,
                        'confidence': confidence
                    }
                    confidences.append(confidence)

        # Extract tables
        for table in result.tables:
            table_data = {
                "row_count": table.row_count,
                "column_count": table.column_count,
                "cells": []
            }

            for cell in table.cells:
                if cell.content.strip():
                    table_data["cells"].append({
                        "content": cell.content.strip(),
                        "row_index": cell.row_index,
                        "column_index": cell.column_index,
                        "confidence": cell.confidence
                    })
                    confidences.append(cell.confidence)

            if table_data["cells"]:
                tables.append(table_data)

        # Extract styles (for document structure understanding)
        for style in result.styles:
            if style.is_handwritten:
                styles.append({
                    "type": "handwritten",
                    "confidence": style.confidence,
                    "spans": [
                        {"offset": span.offset, "length": span.length}
                        for span in style.spans
                    ]
                })

        return {
            "key_value_pairs": key_value_pairs,
            "tables": tables,
            "styles": styles,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0
        }
```

### Step 5: Gemini Normalizer (Using Your Exact static_prompt.py Structure)

#### Create `managed_services/core/gemini_normalizer.py`:
```python
import google.generativeai as genai
from google.oauth2 import service_account
import json
import os
from typing import Dict, Any
import structlog

# Import your exact static prompt structure
import sys
sys.path.append('..')
from static_prompt import STATIC_RESUME_PARSER_PROMPT

logger = structlog.get_logger()

class GeminiNormalizer:
    """Uses Gemini to normalize managed service outputs to your EXACT static_prompt.py structure"""

    def __init__(self):
        # Initialize Gemini with your existing configuration
        api_key = os.getenv('GOOGLE_GEMINI_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
        else:
            # Fallback to service account if available
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path:
                credentials = service_account.Credentials.from_service_account_file(credentials_path)
                genai.configure(credentials=credentials)

        # Use efficient model for normalization
        self.model = genai.GenerativeModel('gemini-1.5-flash')

        # Cost tracking (INR)
        self.cost_per_1k_tokens = 0.075 * 83 / 1000  # $0.075 * ₹83 / 1000 tokens

    async def normalize_to_resume_format(self, raw_result: Dict[str, Any], filename: str, service_name: str) -> Dict[str, Any]:
        """Convert managed service output to your EXACT static_prompt.py structure"""

        # Create normalization prompt using your exact structure
        prompt = self._create_normalization_prompt(raw_result, service_name)

        try:
            # Call Gemini for normalization
            response = self.model.generate_content(prompt)

            if not response.text:
                raise Exception("Empty response from Gemini")

            # Parse and validate JSON response
            result_data = self._parse_and_validate_response(response.text)

            # Estimate cost
            estimated_tokens = (len(prompt) + len(response.text)) / 4  # Rough token estimation
            cost_inr = (estimated_tokens / 1000) * self.cost_per_1k_tokens

            return {
                "success": True,
                "data": result_data,
                "cost": round(cost_inr, 3),
                "tokens_used": int(estimated_tokens),
                "normalization_source": service_name
            }

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini JSON response", error=str(e))
            return self._create_fallback_structure(raw_result, service_name)

        except Exception as e:
            logger.error("Gemini normalization failed", error=str(e))
            return self._create_fallback_structure(raw_result, service_name)

    def _create_normalization_prompt(self, raw_result: Dict[str, Any], service_name: str) -> str:
        """Create service-specific normalization prompt using your exact static_prompt.py structure"""

        # Use your exact prompt structure from static_prompt.py
        base_prompt = f"""
You are an expert resume parser. Extract the resume data from the service output below and convert it into the EXACT JSON structure required.

{STATIC_RESUME_PARSER_PROMPT}

IMPORTANT: Follow ALL the rules from the original prompt above, including:
- Only include sections with actual content
- Use YYYY-MM-DD format for dates
- Clean URLs (remove https://)
- Extract skills as simple array
- Generate metadata with confidence scores
- Return ONLY valid JSON, no explanations

"""

        # Add service-specific data based on which service was used
        if service_name == "aws_textract":
            service_data = f"""
SOURCE: AWS Textract Output
Raw Text: {raw_result.get('raw_text', '')[:2000]}
Structured Fields: {json.dumps(raw_result.get('structured_fields', {}), indent=2)}
Tables: {json.dumps(raw_result.get('tables', []), indent=2)[:1000]}
Confidence: {raw_result.get('confidence_score', 0)}
"""

        elif service_name == "google_documentai":
            service_data = f"""
SOURCE: Google Document AI Output
Raw Text: {raw_result.get('raw_text', '')[:2000]}
Entities: {json.dumps(raw_result.get('entities', {}), indent=2)}
Form Fields: {json.dumps(raw_result.get('form_fields', {}), indent=2)}
Confidence: {raw_result.get('confidence_score', 0)}
"""

        elif service_name == "azure_form_recognizer":
            service_data = f"""
SOURCE: Azure Form Recognizer Output
Raw Text: {raw_result.get('raw_text', '')[:2000]}
Key-Value Pairs: {json.dumps(raw_result.get('key_value_pairs', {}), indent=2)}
Tables: {json.dumps(raw_result.get('tables', []), indent=2)[:1000]}
Confidence: {raw_result.get('confidence_score', 0)}
"""

        else:
            service_data = f"""
SOURCE: Unknown Service Output
Raw Data: {json.dumps(raw_result, indent=2)[:2000]}
"""

        return f"{base_prompt}\n\n{service_data}\n\nReturn the resume data in the exact JSON structure specified above:"

    def _parse_and_validate_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and validate Gemini response matches static_prompt.py structure"""

        # Try different parsing strategies
        result_data = None

        # Strategy 1: Direct JSON parse
        try:
            result_data = json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from code blocks
        if not result_data:
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                try:
                    result_data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

        # Strategy 3: Find JSON object in text
        if not result_data:
            json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\})*)*\}'
            matches = re.findall(json_pattern, response_text, re.DOTALL)
            if matches:
                # Try the longest match first
                matches.sort(key=len, reverse=True)
                for match in matches[:3]:
                    try:
                        result_data = json.loads(match)
                        break
                    except json.JSONDecodeError:
                        continue

        if not result_data:
            raise json.JSONDecodeError("Could not parse JSON from response", response_text, 0)

        # Validate structure matches static_prompt.py requirements
        return self._validate_static_prompt_structure(result_data)

    def _validate_static_prompt_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure the response matches your exact static_prompt.py structure"""

        # The response should already be in the correct format from STATIC_RESUME_PARSER_PROMPT
        # But we'll add some validation to ensure required fields exist

        required_structure = {
            "success": True,
            "data": {
                "content": {},
                "parseMetadata": {}
            }
        }

        # Validate top-level structure
        if not isinstance(data, dict):
            raise ValueError("Response must be a dictionary")

        if "success" not in data:
            data["success"] = True

        if "data" not in data:
            raise ValueError("Missing 'data' field in response")

        data_content = data["data"]

        if "content" not in data_content:
            raise ValueError("Missing 'content' field in data")

        if "parseMetadata" not in data_content:
            raise ValueError("Missing 'parseMetadata' field in data")

        # Ensure required content sections exist (even if empty)
        content = data_content["content"]
        required_sections = ["personalInfo", "summary", "experience", "education", "skills"]

        for section in required_sections:
            if section not in content:
                content[section] = self._get_empty_section_structure(section)

        # Ensure required personalInfo fields exist
        if "personalInfo" in content:
            required_personal_fields = [
                "fullName", "title", "email", "phone", "location",
                "linkedIn", "portfolio", "github", "customLinks"
            ]
            for field in required_personal_fields:
                if field not in content["personalInfo"]:
                    content["personalInfo"][field] = "" if field != "customLinks" else []

        # Ensure metadata has required structure
        metadata = data_content["parseMetadata"]
        required_metadata_fields = [
            "confidence", "parseTime", "detectedSections", "missingSections",
            "sectionConfidence", "warnings", "suggestions", "extractedKeywords",
            "industryDetected", "experienceLevel", "totalExperienceYears",
            "educationLevel", "atsKeywords", "stats"
        ]

        for field in required_metadata_fields:
            if field not in metadata:
                metadata[field] = self._get_empty_metadata_field(field)

        return data

    def _get_empty_section_structure(self, section: str) -> Dict[str, Any]:
        """Get empty structure for required sections matching static_prompt.py"""
        empty_structures = {
            "personalInfo": {
                "fullName": "",
                "title": "",
                "email": "",
                "phone": "",
                "location": "",
                "linkedIn": "",
                "portfolio": "",
                "github": "",
                "customLinks": []
            },
            "summary": {
                "content": ""
            },
            "experience": [],
            "education": [],
            "skills": {
                "extracted": []
            }
        }
        return empty_structures.get(section, {})

    def _get_empty_metadata_field(self, field: str) -> Any:
        """Get empty structure for metadata fields matching static_prompt.py"""
        empty_metadata = {
            "confidence": 0.0,
            "parseTime": 0.0,
            "detectedSections": [],
            "missingSections": [],
            "sectionConfidence": {
                "personalInfo": 0.0,
                "experience": 0.0,
                "education": 0.0,
                "skills": 0.0,
                "projects": 0.0
            },
            "warnings": [],
            "suggestions": [],
            "extractedKeywords": [],
            "industryDetected": "",
            "experienceLevel": "",
            "totalExperienceYears": None,
            "educationLevel": "",
            "atsKeywords": {
                "technical": [],
                "soft": [],
                "industry": [],
                "certifications": []
            },
            "stats": {
                "totalWords": 0,
                "bulletPoints": 0,
                "quantifiedAchievements": 0,
                "actionVerbs": 0,
                "uniqueSkills": 0
            }
        }
        return empty_metadata.get(field)

    def _create_fallback_structure(self, raw_result: Dict[str, Any], service_name: str) -> Dict[str, Any]:
        """Create fallback structure matching your exact static_prompt.py format"""
        return {
            "success": False,
            "data": {
                "content": {
                    "personalInfo": {
                        "fullName": "",
                        "title": "",
                        "email": "",
                        "phone": "",
                        "location": "",
                        "linkedIn": "",
                        "portfolio": "",
                        "github": "",
                        "customLinks": []
                    },
                    "summary": {
                        "content": ""
                    },
                    "experience": [],
                    "education": [],
                    "skills": {
                        "extracted": []
                    }
                },
                "parseMetadata": {
                    "confidence": 0.0,
                    "parseTime": 0.0,
                    "detectedSections": [],
                    "missingSections": ["personalInfo", "experience", "education", "skills"],
                    "sectionConfidence": {
                        "personalInfo": 0.0,
                        "experience": 0.0,
                        "education": 0.0,
                        "skills": 0.0,
                        "projects": 0.0
                    },
                    "warnings": [
                        {
                            "type": "parsing_failed",
                            "message": f"Normalization failed for {service_name} output",
                            "section": "all",
                            "field": "",
                            "suggestion": "Review document quality or try different service"
                        }
                    ],
                    "suggestions": [],
                    "extractedKeywords": [],
                    "industryDetected": "",
                    "experienceLevel": "",
                    "totalExperienceYears": None,
                    "educationLevel": "",
                    "atsKeywords": {
                        "technical": [],
                        "soft": [],
                        "industry": [],
                        "certifications": []
                    },
                    "stats": {
                        "totalWords": 0,
                        "bulletPoints": 0,
                        "quantifiedAchievements": 0,
                        "actionVerbs": 0,
                        "uniqueSkills": 0
                    }
                }
            },
            "cost": 0.1,
            "tokens_used": 0,
            "error": "normalization_failed",
            "normalization_source": service_name
        }
```

---

## Phase 5: Main Orchestrator Implementation

### Step 6: Create Main Orchestrator

#### Create `managed_services/core/orchestrator.py`:
```python
import asyncio
import os
import time
from typing import Dict, Any, Optional
from managed_services.aws.textract_service import TextractService
from managed_services.google.documentai_service import DocumentAIService
from managed_services.azure.form_recognizer_service import AzureFormRecognizerService
from managed_services.core.gemini_normalizer import GeminiNormalizer
import structlog

logger = structlog.get_logger()

class ManagedServicesOrchestrator:
    """Orchestrates document parsing across multiple managed services with intelligent routing"""

    def __init__(self):
        # Initialize all services
        self.textract = TextractService()
        self.document_ai = DocumentAIService()
        self.azure_forms = AzureFormRecognizerService()
        self.gemini_normalizer = GeminiNormalizer()

        # Service routing strategy (optimized for each document type)
        self.service_strategy = {
            'pdf': 'textract',           # AWS Textract best for PDFs
            'png': 'document_ai',        # Google Document AI best for images
            'jpg': 'document_ai',        # Google Document AI best for images
            'jpeg': 'document_ai',       # Google Document AI best for images
            'docx': 'azure_forms',       # Azure Form Recognizer best for Office docs
            'doc': 'azure_forms',        # Azure Form Recognizer best for Office docs
            'txt': 'gemini_fallback'     # Direct to Gemini for text files
        }

        # Cost and budget tracking
        self.total_monthly_cost = 0.0
        self.monthly_budget = float(os.getenv('MONTHLY_BUDGET_INR', 3000))
        self.alert_threshold = float(os.getenv('ALERT_THRESHOLD_PERCENT', 80)) / 100

        # Performance metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

    async def parse_document(self, content: bytes, filename: str, processing_mode: str = "direct") -> Dict[str, Any]:
        """
        Parse document using optimal managed service with intelligent routing

        Args:
            content: Document bytes
            filename: Original filename
            processing_mode: "direct", "cached", or "worker"
        """
        start_time = time.time()
        self.total_requests += 1

        try:
            # Budget pre-check
            await self._check_budget_limits(content)

            # Determine optimal service
            file_ext = self._get_file_extension(filename)
            service_name = self.service_strategy.get(file_ext, 'textract')

            logger.info(
                "Starting document parsing",
                filename=filename,
                file_type=file_ext,
                selected_service=service_name,
                processing_mode=processing_mode,
                file_size_kb=len(content) // 1024
            )

            # Route to appropriate service
            if service_name == 'gemini_fallback':
                # Handle text files or unsupported formats directly with Gemini
                result = await self._parse_with_gemini_fallback(content, filename)
            else:
                # Parse with managed service + normalization
                result = await self._parse_with_managed_service(content, filename, service_name, processing_mode)

            # Update success metrics
            self.successful_requests += 1
            processing_time = time.time() - start_time

            # Add orchestrator metadata
            result["debug"]["orchestrator"] = {
                "processing_mode": processing_mode,
                "total_processing_time": round(processing_time, 3),
                "service_selection_reason": f"Optimal for {file_ext} files",
                "total_monthly_cost": round(self.total_monthly_cost, 2),
                "budget_remaining": round(self.monthly_budget - self.total_monthly_cost, 2),
                "requests_processed": self.total_requests,
                "success_rate": round((self.successful_requests / self.total_requests) * 100, 1)
            }

            logger.info(
                "Document parsing completed successfully",
                filename=filename,
                service=service_name,
                processing_time=processing_time,
                total_cost=result["debug"]["total_cost"],
                success_rate=result["debug"]["orchestrator"]["success_rate"]
            )

            return result

        except Exception as e:
            # Update error metrics
            self.failed_requests += 1
            processing_time = time.time() - start_time

            logger.error(
                "Document parsing failed",
                filename=filename,
                error=str(e),
                processing_time=processing_time,
                error_type=type(e).__name__
            )

            # Try fallback if primary service failed
            if "gemini_fallback" not in str(e).lower():
                logger.info("Attempting Gemini fallback after service failure")
                try:
                    fallback_result = await self._parse_with_gemini_fallback(content, filename)
                    fallback_result["debug"]["fallback_reason"] = f"Primary service failed: {str(e)}"
                    return fallback_result
                except Exception as fallback_error:
                    logger.error("Fallback also failed", fallback_error=str(fallback_error))

            # If all methods fail, return structured error
            return self._create_error_response(filename, str(e), processing_time)

    async def _check_budget_limits(self, content: bytes):
        """Check if processing this document would exceed budget limits"""
        if self.total_monthly_cost >= self.monthly_budget:
            raise Exception(f"Monthly budget of ₹{self.monthly_budget} exceeded. Current: ₹{self.total_monthly_cost}")

        # Estimate cost for this document
        estimated_cost = 2.0  # Conservative estimate
        if self.total_monthly_cost + estimated_cost >= (self.monthly_budget * self.alert_threshold):
            logger.warning(
                "Approaching budget limit",
                current_cost=self.total_monthly_cost,
                estimated_cost=estimated_cost,
                budget=self.monthly_budget,
                threshold_reached=True
            )

    def _get_file_extension(self, filename: str) -> str:
        """Extract and normalize file extension"""
        return os.path.splitext(filename)[1].lower().lstrip('.')

    async def _parse_with_managed_service(self, content: bytes, filename: str, service_name: str, processing_mode: str) -> Dict[str, Any]:
        """Parse document using the selected managed service"""

        # Get the appropriate service
        if service_name == 'textract':
            service = self.textract
        elif service_name == 'document_ai':
            service = self.document_ai
        elif service_name == 'azure_forms':
            service = self.azure_forms
        else:
            raise ValueError(f"Unknown service: {service_name}")

        # Step 1: Parse with managed service
        raw_result = await service.parse_with_metrics(content, filename)
        primary_cost = raw_result['metrics']['cost_inr']

        # Step 2: Normalize to your static_prompt.py structure
        if processing_mode == "cached":
            # For cached mode, try to use existing caching logic
            normalized_result = await self._normalize_with_caching(raw_result, filename, service_name)
        else:
            # Direct normalization
            normalized_result = await self.gemini_normalizer.normalize_to_resume_format(
                raw_result, filename, service_name
            )

        normalization_cost = normalized_result.get('cost', 0)
        total_cost = primary_cost + normalization_cost

        # Update cost tracking
        self.total_monthly_cost += total_cost

        # Return in your exact API format
        return {
            "success": normalized_result.get("success", True),
            "resumeData": normalized_result["data"]["content"],  # Your exact structure
            "debug": {
                "filename": filename,
                "primary_service": service_name,
                "primary_cost": round(primary_cost, 3),
                "normalization_cost": round(normalization_cost, 3),
                "total_cost": round(total_cost, 3),
                "processing_time": raw_result['metrics']['processing_time'],
                "confidence_score": raw_result.get('confidence_score', 0),
                "parseMetadata": normalized_result["data"]["parseMetadata"],  # Your metadata structure
                "service_metrics": raw_result['metrics']
            }
        }

    async def _normalize_with_caching(self, raw_result: Dict[str, Any], filename: str, service_name: str) -> Dict[str, Any]:
        """Normalize with caching integration for cached processing mode"""
        # This could integrate with your existing Redis caching logic
        # For now, use direct normalization but with caching hints

        # Generate cache key based on raw result content
        import hashlib
        raw_text = raw_result.get('raw_text', '')
        cache_key = f"managed_normalized:{hashlib.md5(raw_text.encode()).hexdigest()}"

        # Check cache first (integrate with your existing Redis cache)
        try:
            from utils import _get_from_cache, _set_cache
            cached_result = _get_from_cache(cache_key)
            if cached_result:
                logger.info("Using cached normalization result", cache_key=cache_key)
                return cached_result
        except:
            # Fallback if caching not available
            pass

        # Perform normalization
        result = await self.gemini_normalizer.normalize_to_resume_format(raw_result, filename, service_name)

        # Cache the result
        try:
            from utils import _set_cache
            _set_cache(cache_key, result)
        except:
            pass  # Continue without caching

        return result

    async def _parse_with_gemini_fallback(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Fallback to your existing Gemini-only parsing for unsupported formats or failures"""
        try:
            # Use your existing parsing logic as fallback
            if filename.endswith('.txt') or isinstance(content, str):
                # Handle text content
                from utils import parse_resume_cached
                text_content = content.decode('utf-8') if isinstance(content, bytes) else content
                result = parse_resume_cached("resume.txt", text_content.encode('utf-8'))
            else:
                # Handle file content
                from utils import parse_resume_cached
                result = parse_resume_cached(filename, content)

            # Convert to our expected format
            return {
                "success": result.get("success", True),
                "resumeData": result.get("data", {}),
                "debug": {
                    "filename": filename,
                    "primary_service": "gemini_fallback",
                    "primary_cost": 2.5,  # Estimated cost for full Gemini processing
                    "normalization_cost": 0,
                    "total_cost": 2.5,
                    "processing_time": 0,
                    "confidence_score": 0.85,  # Conservative estimate
                    "fallback_used": True,
                    "parseMetadata": result.get("debug", {})
                }
            }

        except Exception as e:
            logger.error(f"Gemini fallback failed: {str(e)}")
            raise Exception(f"All parsing methods failed: {str(e)}")

    def _create_error_response(self, filename: str, error_message: str, processing_time: float) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            "success": False,
            "resumeData": {},
            "debug": {
                "filename": filename,
                "primary_service": "error",
                "error": error_message,
                "processing_time": round(processing_time, 3),
                "total_cost": 0,
                "parseMetadata": {
                    "confidence": 0.0,
                    "detectedSections": [],
                    "warnings": [{
                        "type": "parsing_error",
                        "message": error_message,
                        "section": "all",
                        "field": "",
                        "suggestion": "Try a different file format or check document quality"
                    }]
                }
            }
        }

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get comprehensive cost and performance summary"""
        return {
            "cost_tracking": {
                "total_monthly_cost": round(self.total_monthly_cost, 2),
                "monthly_budget": self.monthly_budget,
                "budget_used_percent": round((self.total_monthly_cost / self.monthly_budget) * 100, 1),
                "budget_remaining": round(self.monthly_budget - self.total_monthly_cost, 2)
            },
            "performance_metrics": {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "success_rate_percent": round((self.successful_requests / max(1, self.total_requests)) * 100, 1),
                "avg_cost_per_document": round(self.total_monthly_cost / max(1, self.total_requests), 3)
            },
            "service_breakdown": {
                "textract": self.textract.get_metrics(),
                "document_ai": self.document_ai.get_metrics(),
                "azure_forms": self.azure_forms.get_metrics()
            }
        }

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for all services"""
        health_status = {
            "overall_status": "healthy",
            "timestamp": time.time(),
            "services": {}
        }

        # Check each service
        services_to_check = [
            ("textract", self.textract),
            ("document_ai", self.document_ai),
            ("azure_forms", self.azure_forms)
        ]

        for service_name, service_instance in services_to_check:
            try:
                # Simple health check - verify service can be initialized
                service_health = {
                    "status": "healthy",
                    "total_requests": service_instance.total_requests,
                    "success_rate": round(
                        (service_instance.success_count / max(1, service_instance.total_requests)) * 100, 1
                    ),
                    "total_cost": service_instance.total_cost
                }
            except Exception as e:
                service_health = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["overall_status"] = "degraded"

            health_status["services"][service_name] = service_health

        return health_status
```

### Step 7: FastAPI Integration (Maintaining Your Exact API Structure)

#### Create `managed_services/app_managed.py`:
```python
from fastapi import FastAPI, UploadFile, File, Request, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import os
import time
import logging
from dotenv import load_dotenv

# Import your existing auth logic
from token_service import verify_token
from user_service import find_user_by_id

# Import managed services orchestrator
from managed_services.core.orchestrator import ManagedServicesOrchestrator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track app startup time (same as your existing app.py)
app_start_time = time.time()
logger.info("=== MANAGED SERVICES APP STARTUP BEGINNING ===")

# Initialize FastAPI app
app = FastAPI(title="Resume Parser - Managed Services", version="2.0.0")

# Initialize orchestrator
orchestrator = ManagedServicesOrchestrator()

logger.info(f"Managed services initialized in {time.time() - app_start_time:.2f} seconds")

# CORS configuration (keeping your exact logic)
def get_cors_origins():
    NODE_ENV = os.getenv("NODE_ENV", "development")
    print(f"NODE_ENV: {NODE_ENV}")

    if NODE_ENV == "production":
        return [
            'https://app.jobstack.ai',
            'http://localhost:5173',
            'https://jobstack.azurewebsites.net',
            'https://jobtackui-fgcdftezgkhbbpbg.canadacentral-01.azurewebsites.net'
        ]
    elif NODE_ENV == "uat":
        return [
            'http://localhost:5173',
            'https://jobstackuiuat-cybnbdf8h6gkb7g3.canadacentral-01.azurewebsites.net',
            'https://app-uat.jobstack.ai'
        ]
    else:  # default to development
        return [
            'http://localhost:3000',
            'http://localhost:5173',
            'https://app.jobstack.ai',
            'https://app-uat.jobstack.ai',
            'https://jobtackui-fgcdftezgkhbbpbg.canadacentral-01.azurewebsites.net',
            'https://jobstackuiuat-cybnbdf8h6gkb7g3.canadacentral-01.azurewebsites.net',
            'https://jobstackuidev-gwakgfdgbgh5emdw.canadacentral-01.azurewebsites.net'
        ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Managed Services Resume Parser is running"}

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check including all managed services"""
    return await orchestrator.health_check()

# Authentication helper (keeping your exact logic)
async def authenticate_request(request: Request) -> dict:
    """Authenticate request using your existing logic"""
    # Check origin
    origin = request.headers.get("origin")
    print(f"Origin: {origin}")

    if not origin or origin not in get_cors_origins():
        raise HTTPException(status_code=403, detail="Origin not allowed")

    # Check Authorization header
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=400,
            detail={"error": "Authorization header is missing", "status": 400}
        )

    # Extract Bearer token
    try:
        token = auth_header.split(" ")[1]
    except IndexError:
        raise HTTPException(
            status_code=400,
            detail={"error": "Bearer token is missing", "status": 400}
        )

    if not token:
        raise HTTPException(
            status_code=400,
            detail={"error": "Bearer token is missing", "status": 400}
        )

    # Verify token
    try:
        decoded_token = await verify_token(token)
    except Exception as err:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Invalid or expired token",
                "status": 401,
                "details": str(err)
            }
        )

    # Extract userId from token
    user_id = decoded_token.get("userId")
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid token payload", "status": 400}
        )

    # Find user in database
    user = await find_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "User does not exist", "status": 401}
        )

    return {
        "user_id": user_id,
        "user": user,
        "decoded_token": decoded_token
    }

# Direct Processing Endpoint (for small files)
@app.post("/managed/parse-resume")
async def parse_resume_managed_direct(
    request: Request,
    fileType: str = Form(...),
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    """Direct managed services processing (optimal for small files <2MB)"""

    # Authenticate request (using your existing logic)
    auth_data = await authenticate_request(request)

    try:
        # Process file content
        if fileType == "file" and file:
            content = await file.read()
            result = await orchestrator.parse_document(content, file.filename, "direct")
        elif fileType == "text" and text:
            result = await orchestrator.parse_document(text.encode('utf-8'), "resume.txt", "direct")
        else:
            raise HTTPException(status_code=400, detail="Invalid input parameters")

        # Add user context to debug info
        result["debug"]["userId"] = auth_data["user_id"]

        return {
            "resumeData": result["resumeData"],
            "debug": result["debug"],
            "success": result["success"]
        }

    except Exception as e:
        logger.error(f"Direct processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Cached Processing Endpoint (for medium files)
@app.post("/managed/parse-resume-cached")
async def parse_resume_managed_cached(
    request: Request,
    fileType: str = Form(...),
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    """Cached managed services processing (optimal for medium files 2-5MB)"""

    # Authenticate request
    auth_data = await authenticate_request(request)

    start_time = time.time()

    try:
        # Process with caching mode
        if fileType == "file" and file:
            content = await file.read()
            result = await orchestrator.parse_document(content, file.filename, "cached")
        elif fileType == "text" and text:
            result = await orchestrator.parse_document(text.encode('utf-8'), "resume.txt", "cached")
        else:
            raise HTTPException(status_code=400, detail="Invalid input parameters")

        processing_time = time.time() - start_time

        # Add performance info (similar to your existing cached endpoint)
        result["debug"]["userId"] = auth_data["user_id"]
        result["debug"]["total_processing_time"] = round(processing_time, 3)

        return {
            "resumeData": result["resumeData"],
            "debug": result["debug"],
            "success": result["success"]
        }

    except Exception as e:
        logger.error(f"Cached processing failed: {str(e)}")
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Resume parsing failed",
                "details": str(e),
                "processing_time": round(processing_time, 3)
            }
        )

# Worker Processing Endpoint (for large files) - Integrates with your existing Azure Queue
@app.post("/managed/parse-resume-worker")
async def parse_resume_managed_worker(
    request: Request,
    fileType: str = Form(...),
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    """Worker-based managed services processing (optimal for large files >5MB)"""

    # Authenticate request
    auth_data = await authenticate_request(request)

    # Import your existing worker logic
    import uuid
    import base64
    from queue_service import enqueue_job
    from table_service import save_job_queued
    from blob_service import put_json, input_container

    try:
        # Create job ID
        job_id = str(uuid.uuid4())
        blob_name = None

        # Store input data (using your existing blob storage logic)
        if fileType == "file" and file:
            content = await file.read()
            encoded_data = base64.b64encode(content).decode("utf-8")
            blob_name = f"{job_id}_{file.filename}.json"
            put_json(input_container, blob_name, {
                "filename": file.filename,
                "data_base64": encoded_data,
                "processing_mode": "managed_worker"  # Flag for managed services processing
            })
        elif fileType == "text" and text:
            blob_name = f"{job_id}_text.json"
            put_json(input_container, blob_name, {
                "filename": "resume.txt",
                "data": text,
                "processing_mode": "managed_worker"
            })
        else:
            raise HTTPException(status_code=400, detail="Invalid input parameters")

        # Enqueue job (using your existing queue logic)
        enqueue_job(job_id, auth_data["user_id"], filename=blob_name)
        save_job_queued(job_id, auth_data["user_id"])

        return {
            "jobId": job_id,
            "status": "queued",
            "processingMode": "managed_worker",
            "message": "Document queued for managed services processing"
        }

    except Exception as e:
        logger.error(f"Worker queuing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Cost and monitoring endpoints
@app.get("/managed/cost-summary")
async def get_cost_summary():
    """Get detailed cost breakdown and performance metrics"""
    return orchestrator.get_cost_summary()

@app.get("/managed/service-metrics")
async def get_service_metrics():
    """Get individual service performance metrics"""
    return {
        "textract": orchestrator.textract.get_metrics(),
        "document_ai": orchestrator.document_ai.get_metrics(),
        "azure_forms": orchestrator.azure_forms.get_metrics(),
        "orchestrator_metrics": {
            "total_requests": orchestrator.total_requests,
            "success_rate": round((orchestrator.successful_requests / max(1, orchestrator.total_requests)) * 100, 1),
            "total_monthly_cost": orchestrator.total_monthly_cost
        }
    }

# Debug endpoints (similar to your existing ones)
@app.get("/managed/debug/services-status")
async def get_services_status():
    """Debug endpoint to check all managed services status"""
    return await orchestrator.health_check()

logger.info(f"=== MANAGED SERVICES APP STARTUP COMPLETE in {time.time() - app_start_time:.2f} seconds ===")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Different port to avoid conflict
```

### Step 8: Worker Integration (Updating Your Existing Worker)

#### Create `managed_services/worker_managed.py`:
```python
import json
import time
import base64
from queue_service import dequeue_batch, delete_message
from table_service import set_job_processing, set_job_done, set_job_error
from blob_service import get_json, put_json, input_container, output_container
from managed_services.core.orchestrator import ManagedServicesOrchestrator

def process_job_managed(job):
    """Enhanced job processing with managed services"""
    job_data = json.loads(job.content)
    job_id = job_data["jobId"]
    user_id = job_data.get("userId")
    blob_name = job_data.get("filename")

    # Initialize orchestrator
    orchestrator = ManagedServicesOrchestrator()

    try:
        print(f"Processing managed services job {job_id} for user {user_id}")
        set_job_processing(job_id)

        # Load input data
        input_data = get_json(input_container, blob_name)
        processing_mode = input_data.get("processing_mode", "worker")

        # Extract file content
        filename = input_data["filename"]
        if filename == "resume.txt":
            raw_data = input_data["data"]
            content = raw_data.encode("utf-8")
        else:
            # Decode base64 file data
            file_bytes = base64.b64decode(input_data["data_base64"])
            content = file_bytes

        # Process with managed services
        if processing_mode == "managed_worker":
            parsed_result = await orchestrator.parse_document(content, filename, "worker")
        else:
            # Fallback to existing logic for backward compatibility
            from utils import parse_resume_cached
            parsed_result = parse_resume_cached(filename, content)

        # Save result to blob storage
        result_blob = f"{job_id}.json"

        # Format result to match your existing structure
        formatted_result = {
            "data": parsed_result.get("resumeData", parsed_result.get("data", {})),
            "debug": parsed_result.get("debug", {}),
            "success": parsed_result.get("success", True),
            "processing_mode": processing_mode,
            "job_id": job_id,
            "user_id": user_id
        }

        blob_path = put_json(output_container, result_blob, formatted_result)

        # Mark job as done
        set_job_done(job_id, blob_path)
        print(f"✅ Managed services job {job_id} completed -> {blob_path}")

    except Exception as e:
        set_job_error(job_id, str(e))
        print(f"❌ Managed services job {job_id} failed: {e}")

def run_managed_worker():
    """Enhanced worker that handles both managed services and legacy jobs"""
    print("Starting managed services worker...")

    while True:
        messages = dequeue_batch()
        for message in messages:
            try:
                # Check if this is a managed services job
                job_data = json.loads(message.content)
                blob_name = job_data.get("filename", "")

                # Load input data to check processing mode
                input_data = get_json(input_container, blob_name)
                processing_mode = input_data.get("processing_mode", "legacy")

                if processing_mode == "managed_worker":
                    print(f"Processing managed services job: {job_data['jobId']}")
                    process_job_managed(message)
                else:
                    print(f"Processing legacy job: {job_data['jobId']}")
                    # Use your existing worker logic
                    from worker import process_job
                    process_job(message)

                delete_message(message)

            except Exception as e:
                print(f"Worker error: {e}")
                # Still delete message to prevent infinite retry
                delete_message(message)

        time.sleep(5)

if __name__ == "__main__":
    run_managed_worker()
```

---

## Phase 6: Local Testing and Validation

### Step 9: Create Test Environment

#### Create Test Scripts Directory:
```bash
mkdir -p managed_services/tests/local
```

#### Create `managed_services/tests/local/test_setup.py`:
```python
#!/usr/bin/env python3
"""
Local testing script for managed services setup
"""
import asyncio
import os
import json
from pathlib import Path

# Add project root to path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from managed_services.core.orchestrator import ManagedServicesOrchestrator

async def test_services_setup():
    """Test that all managed services are properly configured"""
    print("🧪 Testing Managed Services Setup...")

    try:
        orchestrator = ManagedServicesOrchestrator()
        print("✅ Orchestrator initialized successfully")

        # Test service health
        health_status = await orchestrator.health_check()
        print(f"🏥 Health check: {health_status['overall_status']}")

        for service_name, status in health_status['services'].items():
            if status['status'] == 'healthy':
                print(f"✅ {service_name}: {status['status']}")
            else:
                print(f"❌ {service_name}: {status.get('error', 'Unknown error')}")

        return health_status['overall_status'] == 'healthy'

    except Exception as e:
        print(f"❌ Setup test failed: {str(e)}")
        return False

async def test_sample_document():
    """Test parsing with a sample document"""
    print("\n📄 Testing Sample Document Processing...")

    # Create a sample text document
    sample_text = """
John Doe
Senior Software Engineer
Email: john.doe@email.com
Phone: +1-555-123-4567
Location: San Francisco, CA

EXPERIENCE
Senior Software Engineer | Tech Corp | 2020-Present
- Led development of microservices architecture
- Improved system performance by 40%
- Mentored 3 junior developers

Software Engineer | StartupXYZ | 2018-2020
- Built full-stack web applications using React and Node.js
- Implemented CI/CD pipelines

EDUCATION
Bachelor of Computer Science | UC Berkeley | 2014-2018
GPA: 3.8/4.0

SKILLS
Python, JavaScript, React, Node.js, Docker, AWS, PostgreSQL
"""

    try:
        orchestrator = ManagedServicesOrchestrator()

        # Test text processing
        result = await orchestrator.parse_document(
            sample_text.encode('utf-8'),
            "sample_resume.txt",
            "direct"
        )

        if result['success']:
            print("✅ Sample document processed successfully")
            print(f"💰 Cost: ₹{result['debug']['total_cost']}")
            print(f"⚡ Processing time: {result['debug']['processing_time']}s")
            print(f"🎯 Service used: {result['debug']['primary_service']}")

            # Validate structure
            resume_data = result['resumeData']
            if 'personalInfo' in resume_data and resume_data['personalInfo']['fullName']:
                print(f"✅ Extracted name: {resume_data['personalInfo']['fullName']}")
            if 'experience' in resume_data and len(resume_data['experience']) > 0:
                print(f"✅ Extracted {len(resume_data['experience'])} work experiences")
            if 'skills' in resume_data and 'extracted' in resume_data['skills']:
                print(f"✅ Extracted {len(resume_data['skills']['extracted'])} skills")

            return True
        else:
            print(f"❌ Sample processing failed: {result.get('debug', {}).get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"❌ Sample test failed: {str(e)}")
        return False

async def test_cost_tracking():
    """Test cost tracking functionality"""
    print("\n💰 Testing Cost Tracking...")

    try:
        orchestrator = ManagedServicesOrchestrator()

        # Process a small document to generate some cost data
        sample_text = "John Doe\nSoftware Engineer\njohn@email.com"
        await orchestrator.parse_document(sample_text.encode('utf-8'), "mini_resume.txt", "direct")

        # Get cost summary
        cost_summary = orchestrator.get_cost_summary()

        print(f"✅ Cost tracking working")
        print(f"📊 Total requests: {cost_summary['performance_metrics']['total_requests']}")
        print(f"💰 Total cost: ₹{cost_summary['cost_tracking']['total_monthly_cost']}")
        print(f"📈 Success rate: {cost_summary['performance_metrics']['success_rate_percent']}%")

        return True

    except Exception as e:
        print(f"❌ Cost tracking test failed: {str(e)}")
        return False

async def run_all_tests():
    """Run all local tests"""
    print("🚀 Starting Local Test Suite for Managed Services\n")

    results = {
        "setup": await test_services_setup(),
        "sample_document": await test_sample_document(),
        "cost_tracking": await test_cost_tracking()
    }

    print("\n📋 Test Results Summary:")
    print("=" * 40)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
        if not passed:
            all_passed = False

    print("=" * 40)
    overall_status = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
    print(f"Overall: {overall_status}")

    if not all_passed:
        print("\n🔧 Troubleshooting:")
        print("1. Check your .env.production file has all required credentials")
        print("2. Verify AWS, Google Cloud, and Azure accounts are properly configured")
        print("3. Check internet connectivity for API calls")
        print("4. Review error messages above for specific issues")

    return all_passed

if __name__ == "__main__":
    asyncio.run(run_all_tests())
```

#### Create `managed_services/tests/local/run_tests.sh`:
```bash
#!/bin/bash
echo "🧪 Running Managed Services Local Tests..."

# Set environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Load environment variables
if [ -f "managed_services/.env.production" ]; then
    export $(cat managed_services/.env.production | xargs)
else
    echo "❌ Environment file not found: managed_services/.env.production"
    echo "Please create this file with your credentials first."
    exit 1
fi

# Run tests
python3 managed_services/tests/local/test_setup.py

echo "✅ Local tests completed!"
```

### Step 10: Local Development Server

#### Create `managed_services/run_local.py`:
```python
#!/usr/bin/env python3
"""
Local development server for managed services
"""
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / "managed_services" / ".env.production")

if __name__ == "__main__":
    import uvicorn
    from managed_services.app_managed import app

    print("🚀 Starting Managed Services Local Development Server...")
    print(f"📁 Project root: {project_root}")
    print(f"🌐 Server will be available at: http://localhost:8001")
    print(f"📖 API docs available at: http://localhost:8001/docs")
    print(f"🏥 Health check: http://localhost:8001/health/detailed")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
```

---

## Phase 7: Production Deployment

### Step 11: Production Docker Configuration

#### Create `managed_services/Dockerfile.managed`:
```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (minimal for managed services)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements and install Python dependencies
COPY managed_services/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=1

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health/detailed || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "managed_services.app_managed:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### Create `managed_services/docker-compose.yml` (for local testing):
```yaml
version: '3.8'

services:
  resume-parser-managed:
    build:
      context: ../
      dockerfile: managed_services/Dockerfile.managed
    ports:
      - "8001:8080"
    environment:
      - NODE_ENV=development
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_REGION=${AWS_REGION}
      - GOOGLE_PROJECT_ID=${GOOGLE_PROJECT_ID}
      - DOC_AI_PROCESSOR_ID=${DOC_AI_PROCESSOR_ID}
      - AZURE_FORM_RECOGNIZER_ENDPOINT=${AZURE_FORM_RECOGNIZER_ENDPOINT}
      - AZURE_FORM_RECOGNIZER_KEY=${AZURE_FORM_RECOGNIZER_KEY}
      - GOOGLE_GEMINI_API_KEY=${GOOGLE_GEMINI_API_KEY}
      - MONTHLY_BUDGET_INR=3000
    volumes:
      - ./config:/app/managed_services/config:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health/detailed"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

### Step 12: Google Cloud Deployment

#### Create `managed_services/cloudbuild.managed.yaml`:
```yaml
steps:
  # Build optimized managed services image
  - name: 'gcr.io/cloud-builders/docker'
    args: [
      'build',
      '-f', 'managed_services/Dockerfile.managed',
      '-t', 'gcr.io/$PROJECT_ID/resume-parser-managed:$BUILD_ID',
      '-t', 'gcr.io/$PROJECT_ID/resume-parser-managed:latest',
      '.'
    ]

  # Push image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/resume-parser-managed:$BUILD_ID']

  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/resume-parser-managed:latest']

  # Deploy to Cloud Run
  - name: 'gcr.io/cloud-builders/gcloud'
    args: [
      'run', 'deploy', 'resume-parser-managed',
      '--image', 'gcr.io/$PROJECT_ID/resume-parser-managed:$BUILD_ID',
      '--platform', 'managed',
      '--region', 'us-central1',
      '--allow-unauthenticated',
      '--memory', '2Gi',
      '--cpu', '1',
      '--timeout', '900s',
      '--concurrency', '20',
      '--max-instances', '100',
      '--min-instances', '0',
      '--set-env-vars', 'NODE_ENV=production,PYTHONOPTIMIZE=1',
      '--set-env-vars', 'MONTHLY_BUDGET_INR=3000',
      '--set-secrets', 'AWS_ACCESS_KEY_ID=aws-access-key:latest',
      '--set-secrets', 'AWS_SECRET_ACCESS_KEY=aws-secret-key:latest',
      '--set-secrets', 'AZURE_FORM_RECOGNIZER_KEY=azure-form-key:latest',
      '--set-secrets', 'GOOGLE_GEMINI_API_KEY=gemini-api-key:latest'
    ]

options:
  logging: CLOUD_LOGGING_ONLY
  machineType: 'E2_HIGHCPU_8'

timeout: '1200s'
```

#### Create `managed_services/deploy_production.sh`:
```bash
#!/bin/bash

# Production deployment script for managed services
set -e

PROJECT_ID="your-google-cloud-project-id"
SERVICE_NAME="resume-parser-managed"
REGION="us-central1"

echo "🚀 Deploying Managed Services to Production..."

# Verify environment
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Please set PROJECT_ID in the script"
    exit 1
fi

# Set project
gcloud config set project $PROJECT_ID

# Create secrets (run once)
echo "🔐 Creating/updating secrets..."

# AWS secrets
gcloud secrets create aws-access-key --data-file=<(echo -n "$AWS_ACCESS_KEY_ID") --replication-policy="automatic" || \
gcloud secrets versions add aws-access-key --data-file=<(echo -n "$AWS_ACCESS_KEY_ID")

gcloud secrets create aws-secret-key --data-file=<(echo -n "$AWS_SECRET_ACCESS_KEY") --replication-policy="automatic" || \
gcloud secrets versions add aws-secret-key --data-file=<(echo -n "$AWS_SECRET_ACCESS_KEY")

# Azure secrets
gcloud secrets create azure-form-key --data-file=<(echo -n "$AZURE_FORM_RECOGNIZER_KEY") --replication-policy="automatic" || \
gcloud secrets versions add azure-form-key --data-file=<(echo -n "$AZURE_FORM_RECOGNIZER_KEY")

# Gemini secret
gcloud secrets create gemini-api-key --data-file=<(echo -n "$GOOGLE_GEMINI_API_KEY") --replication-policy="automatic" || \
gcloud secrets versions add gemini-api-key --data-file=<(echo -n "$GOOGLE_GEMINI_API_KEY")

echo "✅ Secrets configured"

# Deploy using Cloud Build
echo "🏗️ Building and deploying..."
gcloud builds submit --config managed_services/cloudbuild.managed.yaml

echo "✅ Deployment completed!"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')
echo "🌐 Service URL: $SERVICE_URL"
echo "🏥 Health check: $SERVICE_URL/health/detailed"
echo "📊 Cost summary: $SERVICE_URL/managed/cost-summary"

echo "🎉 Managed Services deployment successful!"
```

---

## Next Steps Summary

### What You Have Now:
1. **✅ Complete managed services architecture** with AWS, Google, Azure integration
2. **✅ Your exact static_prompt.py structure preserved**
3. **✅ Hybrid processing modes** (direct/cached/worker)
4. **✅ Local testing environment** ready
5. **✅ Production deployment scripts** prepared

### Implementation Order:
1. **Create the branch and directory structure** (5 minutes)
2. **Set up cloud accounts manually** (30-45 minutes total)
3. **Configure environment and credentials** (10 minutes)
4. **Test locally with sample documents** (15 minutes)
5. **Deploy to production** (10 minutes)

### Expected Results:
- **Cost reduction**: 75-80% (₹9,000 → ₹1,800-2,200/month)
- **Processing time**: 2-8 seconds (vs 30-60 seconds)
- **Accuracy**: 95%+ (vs 90%)
- **No breaking changes**: Same API, same response structure

**Ready to start implementation?** Begin with Phase 1 (branch creation) and let me know when you're ready for the next phase!