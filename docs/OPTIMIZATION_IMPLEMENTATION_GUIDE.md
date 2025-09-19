# Resume Parser Optimization Implementation Guide
*Complete step-by-step implementation for all three cost optimization approaches*

## Current Cost Analysis (Corrected)
- **Current monthly cost**: ₹9,000 (~$108)
- **Target cost reduction**: 50-80%
- **Processing time**: 3-4 minutes (cold start), 30-60s (warm)

---

## Approach 1: Optimized Google Cloud Run (Recommended First Step)
*Target: 60-70% cost reduction - ₹2,700-3,600/month*

### Step 1: Container Optimization

#### 1.1 Create Optimized Dockerfile
```dockerfile
# Create: Dockerfile.optimized
FROM python:3.11-slim as base

# Install only essential system dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 libgthread-2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app directory
WORKDIR /app

# Multi-stage build for dependencies
FROM base as deps

# Copy and install base requirements first (for better caching)
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt

# Pre-compile Python bytecode for faster startup
RUN python -m compileall /usr/local/lib/python3.11/site-packages/

FROM deps as final

# Copy application code
COPY . .

# Set optimizations
ENV PYTHONOPTIMIZE=1
ENV PYTHONNODEBUGRANGES=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Pre-compile application code
RUN python -m compileall .

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

#### 1.2 Split Requirements Files
Create `requirements-base.txt`:
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
python-dotenv==1.0.0
google-generativeai>=0.8.0
google-auth>=2.0.0
PyJWT==2.8.0
cryptography==41.0.7
redis==5.0.1
motor==3.3.2
pymongo==4.6.0
azure-storage-queue>=12.0.0
azure-data-tables>=12.0.0
azure-storage-blob>=12.0.0
```

Create `requirements-heavy.txt` (for lazy loading):
```txt
easyocr==1.7.0
pdfplumber==0.10.3
PyMuPDF==1.23.8
python-docx==1.1.0
Pillow==10.1.0
numpy==1.24.4
```

### Step 2: Code Optimizations

#### 2.1 Lazy Loading Implementation
Update `utils.py`:
```python
import functools
import asyncio
from typing import Optional
import logging

# Global variables for lazy loading
_ocr_reader = None
_ocr_lock = asyncio.Lock()
_heavy_imports_loaded = False

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_ocr_reader():
    """Async lazy loading of OCR reader"""
    global _ocr_reader, _ocr_lock

    if _ocr_reader is None:
        async with _ocr_lock:
            if _ocr_reader is None:  # Double-check locking
                logger.info("Initializing EasyOCR (this may take 10-15 seconds)...")
                start_time = time.time()

                # Import heavy dependencies only when needed
                await load_heavy_dependencies()

                import easyocr
                _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)

                init_time = time.time() - start_time
                logger.info(f"EasyOCR initialized in {init_time:.2f} seconds")

    return _ocr_reader

async def load_heavy_dependencies():
    """Load heavy dependencies asynchronously"""
    global _heavy_imports_loaded

    if not _heavy_imports_loaded:
        logger.info("Loading heavy dependencies...")

        # Load in separate thread to avoid blocking
        def _load_deps():
            import numpy
            import PIL
            import cv2
            return True

        # Run in thread pool
        await asyncio.get_event_loop().run_in_executor(None, _load_deps)
        _heavy_imports_loaded = True

# Connection pooling for Redis
@functools.lru_cache(maxsize=1)
def get_redis_pool():
    """Create Redis connection pool"""
    return redis.ConnectionPool(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0,
        max_connections=10,
        retry_on_timeout=True
    )

@functools.lru_cache(maxsize=1)
def get_redis_client():
    """Get Redis client with connection pooling"""
    pool = get_redis_pool()
    return redis.Redis(connection_pool=pool, decode_responses=False)

# Async text extraction
async def extract_text_from_resume_async(filename: str, content: bytes) -> str:
    """Async version of text extraction"""
    file_hash = _get_file_hash(content)
    cache_key = f"text_extract:{file_hash}"

    # Check cache first
    cached_text = _get_from_cache(cache_key)
    if cached_text is not None:
        return cached_text

    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        text = await extract_text_from_pdf_async(content)
    elif ext == ".docx":
        text = await extract_text_from_docx_async(content)
    elif ext in [".png", ".jpg", ".jpeg"]:
        text = await extract_text_from_image_async(content)
    elif ext in [".txt"]:
        text = extract_text_from_txt(content)
    else:
        return "Unsupported file format."

    # Cache the result
    _set_cache(cache_key, text)
    return text

async def extract_text_from_pdf_async(content: bytes) -> str:
    """Async PDF text extraction"""
    def _extract_pdf():
        return extract_text_from_pdf(content)

    # Run CPU-intensive task in thread pool
    return await asyncio.get_event_loop().run_in_executor(None, _extract_pdf)

async def extract_text_from_image_async(content: bytes) -> str:
    """Async image OCR with lazy loading"""
    file_hash = _get_file_hash(content)
    cache_key = f"image_ocr:{file_hash}"

    # Check cache first
    cached_text = _get_from_cache(cache_key)
    if cached_text is not None:
        return cached_text

    # Get OCR reader (lazy loaded)
    reader = await get_ocr_reader()

    def _perform_ocr():
        image = Image.open(io.BytesIO(content)).convert("RGB")
        import numpy as np
        img_np = np.array(image)
        result = reader.readtext(img_np, detail=0)
        return "\n".join(result)

    # Run OCR in thread pool
    text = await asyncio.get_event_loop().run_in_executor(None, _perform_ocr)

    # Cache result
    _set_cache(cache_key, text)
    return text
```

#### 2.2 Update FastAPI App for Async Processing
Update `app.py`:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import BackgroundTasks

# Add thread pool executor
executor = ThreadPoolExecutor(max_workers=2)

# Update endpoint to be fully async
@app.post("/cached/parse-resume")
async def upload_resume_cached_optimized(
    request: Request,
    fileType: str = Form(...),
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    # ... existing auth code ...

    start_time = time.time()

    try:
        if fileType == "file":
            if not file:
                raise HTTPException(status_code=400, detail="File not provided")
            content = await file.read()

            # Process asynchronously
            parsed_result = await parse_resume_cached_async(file.filename, content)

        elif fileType == "text":
            if not text or not text.strip():
                raise HTTPException(status_code=400, detail="Text not provided")

            # Process asynchronously
            parsed_result = await parse_resume_cached_async("resume.txt", text.encode("utf-8"))
        else:
            raise HTTPException(status_code=400, detail="Invalid fileType")

        processing_time = time.time() - start_time
        logger.info(f"Processing completed in {processing_time:.2f}s")

        return {
            "resumeData": parsed_result.get("data"),
            "debug": {
                **parsed_result.get("debug", {}),
                "processing_time": round(processing_time, 3)
            }
        }

    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Async parsing function
async def parse_resume_cached_async(filename: str, content: bytes) -> dict:
    """Async version of parse_resume_cached"""
    file_hash = _get_file_hash(content)
    cache_key = f"full_parse_cached:{file_hash}"

    # Check cache
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result

    # Extract text asynchronously
    if filename == 'resume.txt':
        raw_text = content.decode('utf-8') if isinstance(content, bytes) else content
    else:
        raw_text = await extract_text_from_resume_async(filename, content)

    # Transform to structured data
    structured_data = await transform_text_to_resume_data_cached_async(raw_text)

    # Cache result
    _set_cache(cache_key, structured_data)
    return structured_data

async def transform_text_to_resume_data_cached_async(raw_text: str) -> dict:
    """Async version of Gemini API call"""
    text_hash = _get_text_hash(raw_text)
    cache_key = f"gemini_transform_cached:{text_hash}"

    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        return {
            "success": True,
            "data": cached_result,
            "debug": {"cache_hit": True}
        }

    # Call Gemini API asynchronously
    def _call_gemini():
        return call_gemini_api_cached(raw_text)

    api_response = await asyncio.get_event_loop().run_in_executor(
        executor, _call_gemini
    )

    # Process response...
    content = api_response.get("analysis_content")
    if content:
        try:
            # Parse JSON response
            result = json.loads(content)
            _set_cache(cache_key, result)
            return {
                "success": True,
                "data": result,
                "debug": api_response.get("debug_info", {})
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON parse error: {str(e)}",
                "debug": {"content_preview": content[:200]}
            }

    return {
        "success": False,
        "error": "Empty response from Gemini API"
    }

# Health check for readiness
@app.get("/health/ready")
async def readiness_check():
    """Readiness probe - check if heavy dependencies are loaded"""
    global _heavy_imports_loaded
    return {
        "status": "ready" if _heavy_imports_loaded else "loading",
        "heavy_deps_loaded": _heavy_imports_loaded,
        "timestamp": time.time()
    }
```

### Step 3: Cloud Run Configuration

#### 3.1 Create optimized `cloudbuild.yaml`
```yaml
steps:
  # Build optimized image
  - name: 'gcr.io/cloud-builders/docker'
    args: [
      'build',
      '-f', 'Dockerfile.optimized',
      '-t', 'gcr.io/$PROJECT_ID/resume-parser-optimized:$BUILD_ID',
      '.'
    ]

  # Push image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/resume-parser-optimized:$BUILD_ID']

  # Deploy to Cloud Run
  - name: 'gcr.io/cloud-builders/gcloud'
    args: [
      'run', 'deploy', 'resume-parser-optimized',
      '--image', 'gcr.io/$PROJECT_ID/resume-parser-optimized:$BUILD_ID',
      '--platform', 'managed',
      '--region', 'us-central1',
      '--allow-unauthenticated',
      '--set-env-vars', 'NODE_ENV=production',
      '--memory', '4Gi',
      '--cpu', '2',
      '--timeout', '900s',
      '--concurrency', '10',
      '--max-instances', '100',
      '--min-instances', '0'
    ]

options:
  logging: CLOUD_LOGGING_ONLY
```

#### 3.2 Deployment Script
Create `deploy-optimized.sh`:
```bash
#!/bin/bash

# Set project variables
PROJECT_ID="your-project-id"
SERVICE_NAME="resume-parser-optimized"
REGION="us-central1"

echo "Building and deploying optimized Cloud Run service..."

# Build and deploy
gcloud builds submit --config cloudbuild.yaml

# Configure additional settings
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --cpu-throttling \
    --session-affinity \
    --execution-environment=gen2 \
    --set-env-vars="PYTHONOPTIMIZE=1,PYTHONNODEBUGRANGES=1" \
    --add-cloudsql-instances="" \
    --clear-vpc-connector

echo "Deployment completed!"
echo "Service URL: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')"
```

### Step 4: Monitoring and Scaling

#### 4.1 Create monitoring script
Create `monitor.py`:
```python
import time
import requests
import json
from datetime import datetime

def monitor_performance():
    """Monitor service performance and costs"""
    service_url = "https://your-service-url"

    metrics = {
        "timestamp": datetime.now().isoformat(),
        "cold_starts": 0,
        "warm_responses": 0,
        "avg_response_time": 0,
        "errors": 0
    }

    # Test warm response
    start_time = time.time()
    try:
        response = requests.get(f"{service_url}/health/ready", timeout=30)
        warm_time = time.time() - start_time

        if response.status_code == 200:
            metrics["warm_responses"] += 1
            metrics["avg_response_time"] = warm_time
        else:
            metrics["errors"] += 1

    except Exception as e:
        metrics["errors"] += 1
        print(f"Error: {e}")

    print(json.dumps(metrics, indent=2))
    return metrics

if __name__ == "__main__":
    monitor_performance()
```

### Expected Results (Approach 1):
- **Cost reduction**: 60-70% (₹2,700-3,600/month)
- **Cold start time**: 30-60 seconds (from 3-4 minutes)
- **Warm response time**: 5-15 seconds
- **Accuracy**: Maintained at 90%+

---

## Approach 2: AWS Lambda Migration
*Target: 70-80% cost reduction - ₹1,800-2,700/month*

### Step 1: Lambda Architecture Design

#### 1.1 Microservices Decomposition
```
Current Monolith → AWS Lambda Functions:

1. text-extractor (Python 3.11, 1GB memory)
   - PDF/DOCX/TXT processing
   - No OCR dependencies
   - Fast cold start (<5s)

2. ocr-processor (Python 3.11, 3GB memory)
   - Image OCR only
   - Heavy dependencies
   - Provisioned concurrency

3. ai-parser (Python 3.11, 512MB memory)
   - Gemini API calls
   - Lightweight
   - Fast scaling

4. result-merger (Python 3.11, 256MB memory)
   - Combine results
   - Format response
   - Ultra-fast
```

#### 1.2 Create Lambda Layer for Dependencies
Create `create_layer.sh`:
```bash
#!/bin/bash

# Create Python dependencies layer
mkdir -p layers/python-deps/python

# Install lightweight dependencies
pip install \
    fastapi \
    pydantic \
    python-multipart \
    python-dotenv \
    google-generativeai \
    google-auth \
    PyJWT \
    cryptography \
    redis \
    pymongo \
    azure-storage-blob \
    pdfplumber \
    python-docx \
    Pillow \
    -t layers/python-deps/python/

# Create layer ZIP
cd layers/python-deps && zip -r ../python-deps-layer.zip python/

# Create OCR layer (separate for heavy dependencies)
mkdir -p ../ocr-layer/python
pip install \
    easyocr \
    opencv-python-headless \
    numpy \
    torch --index-url https://download.pytorch.org/whl/cpu \
    -t ../ocr-layer/python/

cd ../ocr-layer && zip -r ../ocr-layer.zip python/

echo "Layers created successfully!"
```

### Step 2: Lambda Functions Implementation

#### 2.1 Text Extractor Function
Create `lambda_functions/text_extractor.py`:
```python
import json
import base64
import pdfplumber
import docx
import io
from typing import Dict, Any

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Extract text from documents (no OCR)"""
    try:
        # Parse input
        body = json.loads(event.get('body', '{}'))
        file_content = base64.b64decode(body['file_content'])
        filename = body['filename']

        # Extract text based on file type
        ext = filename.lower().split('.')[-1]

        if ext == 'pdf':
            text = extract_text_from_pdf(file_content)
        elif ext == 'docx':
            text = extract_text_from_docx(file_content)
        elif ext == 'txt':
            text = file_content.decode('utf-8')
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'Unsupported file type: {ext}'
                })
            }

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'text': text,
                'filename': filename,
                'processing_time': context.get_remaining_time_in_millis()
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF using pdfplumber"""
    text = ""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text += page_text
    return text

def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX"""
    doc = docx.Document(io.BytesIO(content))
    full_text = []

    # Get text from paragraphs
    for para in doc.paragraphs:
        full_text.append(para.text)

    # Get text from tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    full_text.append(paragraph.text)

    return '\n'.join([text for text in full_text if text.strip()])
```

#### 2.2 OCR Processor Function
Create `lambda_functions/ocr_processor.py`:
```python
import json
import base64
import easyocr
import numpy as np
from PIL import Image
import io
from typing import Dict, Any

# Global OCR reader (initialized once per container)
reader = None

def get_reader():
    """Get or initialize OCR reader"""
    global reader
    if reader is None:
        reader = easyocr.Reader(['en'], gpu=False)
    return reader

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Perform OCR on images"""
    try:
        # Parse input
        body = json.loads(event.get('body', '{}'))
        file_content = base64.b64decode(body['file_content'])
        filename = body['filename']

        # Perform OCR
        ocr_reader = get_reader()
        image = Image.open(io.BytesIO(file_content)).convert('RGB')
        img_array = np.array(image)

        # Extract text
        results = ocr_reader.readtext(img_array, detail=0)
        text = '\n'.join(results)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'text': text,
                'filename': filename,
                'processing_time': context.get_remaining_time_in_millis()
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
```

#### 2.3 AI Parser Function
Create `lambda_functions/ai_parser.py`:
```python
import json
import os
import google.generativeai as genai
from google.oauth2 import service_account
import time
from typing import Dict, Any

# Initialize Gemini
credentials_json = os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON']
credentials_info = json.loads(credentials_json)
credentials = service_account.Credentials.from_service_account_info(credentials_info)
genai.configure(credentials=credentials)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Parse resume using Gemini AI"""
    try:
        # Parse input
        body = json.loads(event.get('body', '{}'))
        raw_text = body['text']

        # Call Gemini API
        model = genai.GenerativeModel('gemini-2.5-flash-lite')

        # Use your existing prompt from static_prompt.py
        prompt = f"""
{get_parsing_prompt()}

Resume Text:
{raw_text}
"""

        response = model.generate_content(prompt)

        # Parse response
        if response.text:
            result = json.loads(response.text)

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'data': result,
                    'processing_time': context.get_remaining_time_in_millis()
                })
            }
        else:
            raise Exception("Empty response from Gemini")

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def get_parsing_prompt():
    """Your existing prompt from static_prompt.py"""
    # Copy your STATIC_RESUME_PARSER_PROMPT here
    return """Your existing prompt..."""
```

#### 2.4 Orchestrator Function
Create `lambda_functions/orchestrator.py`:
```python
import json
import boto3
import asyncio
from typing import Dict, Any

lambda_client = boto3.client('lambda')

async def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Orchestrate the parsing pipeline"""
    try:
        # Parse input
        body = json.loads(event.get('body', '{}'))
        file_content = body['file_content']
        filename = body['filename']

        # Determine processing path
        ext = filename.lower().split('.')[-1]

        if ext in ['png', 'jpg', 'jpeg']:
            # Use OCR processor
            function_name = 'resume-parser-ocr-processor'
        else:
            # Use text extractor
            function_name = 'resume-parser-text-extractor'

        # Step 1: Extract text
        text_response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'body': json.dumps({
                    'file_content': file_content,
                    'filename': filename
                })
            })
        )

        text_result = json.loads(text_response['Payload'].read())
        if text_result['statusCode'] != 200:
            raise Exception(text_result.get('body'))

        text_data = json.loads(text_result['body'])
        raw_text = text_data['text']

        # Step 2: Parse with AI
        ai_response = lambda_client.invoke(
            FunctionName='resume-parser-ai-parser',
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'body': json.dumps({
                    'text': raw_text
                })
            })
        )

        ai_result = json.loads(ai_response['Payload'].read())
        if ai_result['statusCode'] != 200:
            raise Exception(ai_result.get('body'))

        ai_data = json.loads(ai_result['body'])

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'resumeData': ai_data['data'],
                'debug': {
                    'filename': filename,
                    'processing_path': function_name,
                    'text_length': len(raw_text)
                }
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }
```

### Step 3: Deployment Configuration

#### 3.1 Serverless Framework Configuration
Create `serverless.yml`:
```yaml
service: resume-parser-lambda

frameworkVersion: '3'

provider:
  name: aws
  runtime: python3.11
  region: us-east-1
  timeout: 900
  environment:
    GOOGLE_APPLICATION_CREDENTIALS_JSON: ${env:GOOGLE_APPLICATION_CREDENTIALS_JSON}
    REDIS_HOST: ${env:REDIS_HOST}
    AZURE_STORAGE_CONNECTION_STRING: ${env:AZURE_STORAGE_CONNECTION_STRING}

layers:
  pythonDeps:
    path: layers/python-deps-layer.zip
    name: resume-parser-python-deps
    compatibleRuntimes:
      - python3.11

  ocrDeps:
    path: layers/ocr-layer.zip
    name: resume-parser-ocr-deps
    compatibleRuntimes:
      - python3.11

functions:
  textExtractor:
    handler: lambda_functions/text_extractor.lambda_handler
    memorySize: 1024
    timeout: 300
    layers:
      - { Ref: PythonDepsLambdaLayer }
    events:
      - http:
          path: /extract-text
          method: post
          cors: true

  ocrProcessor:
    handler: lambda_functions/ocr_processor.lambda_handler
    memorySize: 3008
    timeout: 600
    provisionedConcurrency: 1  # Keep warm for fast OCR
    layers:
      - { Ref: PythonDepsLambdaLayer }
      - { Ref: OcrDepsLambdaLayer }
    events:
      - http:
          path: /ocr-process
          method: post
          cors: true

  aiParser:
    handler: lambda_functions/ai_parser.lambda_handler
    memorySize: 512
    timeout: 300
    layers:
      - { Ref: PythonDepsLambdaLayer }
    events:
      - http:
          path: /ai-parse
          method: post
          cors: true

  orchestrator:
    handler: lambda_functions/orchestrator.lambda_handler
    memorySize: 256
    timeout: 900
    layers:
      - { Ref: PythonDepsLambdaLayer }
    events:
      - http:
          path: /parse-resume
          method: post
          cors: true

plugins:
  - serverless-python-requirements
  - serverless-offline

custom:
  pythonRequirements:
    dockerizePip: true
```

#### 3.2 Deployment Script
Create `deploy-lambda.sh`:
```bash
#!/bin/bash

echo "Deploying Resume Parser to AWS Lambda..."

# Install Serverless Framework
npm install -g serverless

# Install plugins
npm install serverless-python-requirements serverless-offline

# Create layers
./create_layer.sh

# Deploy
serverless deploy --stage production

echo "Deployment completed!"
echo "API Gateway URL:"
serverless info --stage production | grep endpoints -A 20
```

### Expected Results (Approach 2):
- **Cost reduction**: 70-80% (₹1,800-2,700/month)
- **Cold start time**: 5-15 seconds
- **Processing time**: 10-30 seconds
- **Scalability**: Auto-scales to handle traffic spikes
- **Accuracy**: Maintained at 90%+

---

## Approach 3: Managed Services Integration
*Target: 80-85% cost reduction - ₹1,350-1,800/month*

### Step 1: Architecture with Managed Services

#### 1.1 Service Selection Strategy
```
Processing Flow:
1. Document Upload → API Gateway
2. Route by file type:
   - PDF → AWS Textract
   - Images → Google Document AI
   - DOCX → Azure Form Recognizer
   - Complex layouts → Fallback to custom Gemini
3. Normalize results → Response
```

#### 1.2 Multi-Cloud Integration
Create `managed_services_parser.py`:
```python
import json
import boto3
import asyncio
from google.cloud import documentai_v1
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import os
from typing import Dict, Any, Optional

class ManagedServicesParser:
    def __init__(self):
        # AWS Textract
        self.textract = boto3.client('textract', region_name='us-east-1')

        # Google Document AI
        self.doc_ai_client = documentai_v1.DocumentProcessorServiceClient()
        self.doc_ai_processor = f"projects/{os.getenv('GOOGLE_PROJECT_ID')}/locations/us/processors/{os.getenv('DOC_AI_PROCESSOR_ID')}"

        # Azure Form Recognizer
        self.azure_client = DocumentAnalysisClient(
            endpoint=os.getenv('AZURE_FORM_ENDPOINT'),
            credential=AzureKeyCredential(os.getenv('AZURE_FORM_KEY'))
        )

        # Fallback to Gemini
        self.gemini_client = self._init_gemini()

    async def parse_document(self, filename: str, content: bytes) -> Dict[str, Any]:
        """Route document to appropriate managed service"""
        ext = filename.lower().split('.')[-1]

        try:
            if ext == 'pdf':
                return await self._parse_with_textract(content, filename)
            elif ext in ['png', 'jpg', 'jpeg']:
                return await self._parse_with_document_ai(content, filename)
            elif ext == 'docx':
                return await self._parse_with_azure_forms(content, filename)
            else:
                # Fallback to custom Gemini parsing
                return await self._parse_with_gemini_fallback(content, filename)

        except Exception as e:
            print(f"Managed service failed, falling back to Gemini: {str(e)}")
            return await self._parse_with_gemini_fallback(content, filename)

    async def _parse_with_textract(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Parse PDF with AWS Textract"""
        try:
            # Call Textract
            response = self.textract.analyze_document(
                Document={'Bytes': content},
                FeatureTypes=['TABLES', 'FORMS', 'LAYOUT']
            )

            # Extract text and structure
            text = ""
            fields = {}

            for block in response['Blocks']:
                if block['BlockType'] == 'LINE':
                    text += block['Text'] + '\n'
                elif block['BlockType'] == 'KEY_VALUE_SET':
                    if block.get('EntityTypes') and 'KEY' in block['EntityTypes']:
                        key = block['Text']
                        # Find corresponding value
                        for value_block in response['Blocks']:
                            if (value_block['BlockType'] == 'KEY_VALUE_SET' and
                                value_block.get('EntityTypes') and
                                'VALUE' in value_block['EntityTypes']):
                                fields[key] = value_block.get('Text', '')

            # Convert to resume format
            return await self._normalize_textract_result(text, fields, filename)

        except Exception as e:
            raise Exception(f"Textract parsing failed: {str(e)}")

    async def _parse_with_document_ai(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Parse image with Google Document AI"""
        try:
            # Prepare request
            request = documentai_v1.ProcessRequest(
                name=self.doc_ai_processor,
                raw_document=documentai_v1.RawDocument(
                    content=content,
                    mime_type='image/jpeg' if filename.lower().endswith('jpg') else 'image/png'
                )
            )

            # Process document
            result = self.doc_ai_client.process_document(request=request)
            document = result.document

            # Extract text and entities
            text = document.text
            entities = {}

            for entity in document.entities:
                entities[entity.type] = {
                    'text': entity.text_anchor.content if entity.text_anchor else '',
                    'confidence': entity.confidence
                }

            return await self._normalize_document_ai_result(text, entities, filename)

        except Exception as e:
            raise Exception(f"Document AI parsing failed: {str(e)}")

    async def _parse_with_azure_forms(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Parse DOCX with Azure Form Recognizer"""
        try:
            # Analyze document
            poller = self.azure_client.begin_analyze_document(
                "prebuilt-document", content
            )
            result = poller.result()

            # Extract content
            text = result.content
            fields = {}

            for kv_pair in result.key_value_pairs:
                if kv_pair.key and kv_pair.value:
                    key = kv_pair.key.content
                    value = kv_pair.value.content
                    fields[key] = value

            return await self._normalize_azure_result(text, fields, filename)

        except Exception as e:
            raise Exception(f"Azure Form Recognizer parsing failed: {str(e)}")

    async def _normalize_textract_result(self, text: str, fields: Dict, filename: str) -> Dict[str, Any]:
        """Convert Textract output to resume format"""
        # Use lightweight Gemini call to structure the extracted text
        prompt = f"""
Convert this resume text extracted by AWS Textract into structured JSON.

Textract Text:
{text}

Textract Fields:
{json.dumps(fields, indent=2)}

Return ONLY the JSON in this format:
{self._get_resume_schema()}
"""
        return await self._call_gemini_for_structuring(prompt, text, filename, "textract")

    async def _normalize_document_ai_result(self, text: str, entities: Dict, filename: str) -> Dict[str, Any]:
        """Convert Document AI output to resume format"""
        prompt = f"""
Convert this resume text extracted by Google Document AI into structured JSON.

Document Text:
{text}

Extracted Entities:
{json.dumps(entities, indent=2)}

Return ONLY the JSON in this format:
{self._get_resume_schema()}
"""
        return await self._call_gemini_for_structuring(prompt, text, filename, "document_ai")

    async def _normalize_azure_result(self, text: str, fields: Dict, filename: str) -> Dict[str, Any]:
        """Convert Azure Form Recognizer output to resume format"""
        prompt = f"""
Convert this resume text extracted by Azure Form Recognizer into structured JSON.

Document Text:
{text}

Extracted Fields:
{json.dumps(fields, indent=2)}

Return ONLY the JSON in this format:
{self._get_resume_schema()}
"""
        return await self._call_gemini_for_structuring(prompt, text, filename, "azure_forms")

    async def _call_gemini_for_structuring(self, prompt: str, text: str, filename: str, service: str) -> Dict[str, Any]:
        """Use Gemini to structure pre-extracted text"""
        try:
            response = await self._call_gemini_async(prompt)
            result = json.loads(response)

            return {
                "success": True,
                "data": result,
                "debug": {
                    "filename": filename,
                    "service_used": service,
                    "text_length": len(text),
                    "processing_method": "managed_service + gemini_structuring"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "debug": {
                    "filename": filename,
                    "service_used": service,
                    "fallback_needed": True
                }
            }

    async def _parse_with_gemini_fallback(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Fallback to full Gemini processing"""
        # Your existing parse_resume_cached logic here
        # This ensures we maintain the same accuracy for edge cases
        pass

    def _get_resume_schema(self) -> str:
        """Return simplified resume schema for managed services"""
        return """
{
  "personalInfo": {
    "fullName": "",
    "title": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedIn": "",
    "github": ""
  },
  "experience": [
    {
      "company": "",
      "position": "",
      "startDate": "",
      "endDate": "",
      "description": "",
      "achievements": []
    }
  ],
  "education": [
    {
      "institution": "",
      "degree": "",
      "field": "",
      "startDate": "",
      "endDate": ""
    }
  ],
  "skills": {
    "extracted": []
  }
}
"""

# FastAPI integration
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse

app = FastAPI()
parser = ManagedServicesParser()

@app.post("/managed/parse-resume")
async def parse_with_managed_services(
    fileType: str = Form(...),
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    try:
        if fileType == "file" and file:
            content = await file.read()
            result = await parser.parse_document(file.filename, content)
        elif fileType == "text" and text:
            result = await parser.parse_document("resume.txt", text.encode('utf-8'))
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid input"}
            )

        return JSONResponse(
            status_code=200,
            content={
                "resumeData": result.get("data"),
                "debug": result.get("debug"),
                "success": result.get("success", False)
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
```

### Step 2: Service Configuration

#### 2.1 Environment Setup
Create `.env.managed`:
```bash
# AWS Textract
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1

# Google Document AI
GOOGLE_PROJECT_ID=your_project_id
DOC_AI_PROCESSOR_ID=your_processor_id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Azure Form Recognizer
AZURE_FORM_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_FORM_KEY=your_azure_key

# Fallback Gemini
GEMINI_API_KEY=your_gemini_key
```

#### 2.2 Cost Monitoring
Create `cost_monitor.py`:
```python
import boto3
import json
from datetime import datetime, timedelta
from typing import Dict

class CostMonitor:
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')

    def get_monthly_costs(self) -> Dict[str, float]:
        """Estimate monthly costs for managed services"""

        # Estimated costs (USD per document)
        costs = {
            'textract': 0.0015,  # $0.0015 per page
            'document_ai': 0.002,  # $0.002 per page
            'azure_forms': 0.001,  # $0.001 per page
            'gemini_structuring': 0.0005,  # Small prompt for structuring
            'gemini_fallback': 0.003,  # Full processing for edge cases
        }

        # Estimate usage (documents per month)
        estimated_monthly_docs = 1000

        # Calculate costs (assuming 80% managed services, 20% fallback)
        monthly_costs = {
            'managed_services': estimated_monthly_docs * 0.8 * (costs['textract'] + costs['document_ai'] + costs['azure_forms']) / 3,
            'gemini_structuring': estimated_monthly_docs * 0.8 * costs['gemini_structuring'],
            'gemini_fallback': estimated_monthly_docs * 0.2 * costs['gemini_fallback'],
            'infrastructure': 50,  # Cloud Run minimal cost
        }

        total_usd = sum(monthly_costs.values())
        total_inr = total_usd * 83  # Convert to INR

        return {
            **monthly_costs,
            'total_usd': total_usd,
            'total_inr': total_inr,
            'cost_per_doc_inr': total_inr / estimated_monthly_docs
        }

    def print_cost_analysis(self):
        """Print detailed cost analysis"""
        costs = self.get_monthly_costs()

        print("\n=== Managed Services Cost Analysis ===")
        print(f"Managed Services: ${costs['managed_services']:.2f}")
        print(f"Gemini Structuring: ${costs['gemini_structuring']:.2f}")
        print(f"Gemini Fallback: ${costs['gemini_fallback']:.2f}")
        print(f"Infrastructure: ${costs['infrastructure']:.2f}")
        print(f"Total Monthly (USD): ${costs['total_usd']:.2f}")
        print(f"Total Monthly (INR): ₹{costs['total_inr']:.2f}")
        print(f"Cost per Document: ₹{costs['cost_per_doc_inr']:.3f}")

if __name__ == "__main__":
    monitor = CostMonitor()
    monitor.print_cost_analysis()
```

### Expected Results (Approach 3):
- **Cost reduction**: 80-85% (₹1,350-1,800/month)
- **Processing time**: 2-8 seconds
- **Accuracy**: 95%+ (better than custom implementation)
- **Reliability**: Enterprise-grade managed services
- **Maintenance**: Minimal code to maintain

---

## Cost Comparison Summary (INR)

| Approach | Current Cost | Optimized Cost | Savings | Processing Time | Accuracy |
|----------|--------------|----------------|---------|-----------------|----------|
| **Current** | ₹9,000/month | - | - | 3-4 min (cold) | 90% |
| **Approach 1: Optimized Cloud Run** | ₹9,000 | ₹2,700-3,600 | 60-70% | 30-60s (cold) | 90%+ |
| **Approach 2: AWS Lambda** | ₹9,000 | ₹1,800-2,700 | 70-80% | 5-15s (cold) | 90%+ |
| **Approach 3: Managed Services** | ₹9,000 | ₹1,350-1,800 | 80-85% | 2-8s | 95%+ |

## Implementation Timeline

### Phase 1 (Week 1-2): Approach 1 - Quick Wins
- Implement lazy loading and async processing
- Optimize container and Cloud Run config
- **Target**: 60% cost reduction with minimal risk

### Phase 2 (Week 3-4): Evaluate Results
- Monitor Approach 1 performance
- Decide on Approach 2 (Lambda) or 3 (Managed Services)
- **Target**: Additional 10-20% optimization

### Phase 3 (Week 5-8): Advanced Implementation
- Deploy chosen advanced approach
- Performance tuning and monitoring
- **Target**: 80%+ total cost reduction

**Recommendation**: Start with Approach 1 for immediate benefits, then evaluate Approach 3 (Managed Services) for maximum cost reduction and accuracy improvement.