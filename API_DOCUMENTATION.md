# Resume Parser API Documentation

## Overview

The Resume Parser API provides both synchronous and asynchronous processing of resumes from files or direct text input. It supports multiple file formats and uses AI-powered parsing to extract structured data.

## Base URL
```
http://localhost:8000
```

## Authentication

All endpoints require:
- **Authorization Header**: `Bearer <jwt_token>`
- **Origin Header**: Must be from allowed origins

## Supported File Types
- PDF (.pdf)
- Microsoft Word (.doc, .docx)
- Images (.png, .jpg, .jpeg)
- Text files (.txt)

## Endpoints

### 1. Health Check

#### `GET /`
Basic health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "message": "Resume parser is running"
}
```

---

### 2. Synchronous Resume Parsing

#### `POST /parse-resume`
Processes resume synchronously and returns result immediately (15-60 second wait).

**Request:**
- **Content-Type**: `multipart/form-data`
- **Body Parameters:**
  - `fileType` (string, required): Either "file" or "text"
  - `file` (file, optional): Resume file (required if fileType="file")
  - `text` (string, optional): Resume text content (required if fileType="text")
  - `fresh` (boolean, optional): Bypass cache if true (default: false)

**Example Request (File Upload):**
```bash
curl -X POST http://localhost:8000/parse-resume \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Origin: http://localhost:5173" \
  -F "fileType=file" \
  -F "file=@resume.pdf" \
  -F "fresh=false"
```

**Example Request (Text Input):**
```bash
curl -X POST http://localhost:8000/parse-resume \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Origin: http://localhost:5173" \
  -F "fileType=text" \
  -F "text=John Doe\nSoftware Engineer\n..." \
  -F "fresh=false"
```

**Response (Success):**
```json
{
  "personal": {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890",
    "location": "New York, NY"
  },
  "experience": [
    {
      "title": "Software Engineer",
      "company": "Tech Corp",
      "duration": "2020-2023",
      "description": "Developed web applications..."
    }
  ],
  "education": [
    {
      "degree": "Bachelor of Science",
      "field": "Computer Science",
      "institution": "University Name",
      "year": "2020"
    }
  ],
  "skills": [
    "JavaScript", "Python", "React", "Node.js"
  ],
  "metadata": {
    "user_id": "user123",
    "origin": "http://localhost:5173",
    "origin_valid": true,
    "parseTime": 12.34,
    "tokens": {
      "input_tokens": 1500,
      "output_tokens": 800,
      "total_tokens": 2300
    },
    "cost": {
      "total_cost_usd": 0.0023
    }
  }
}
```

---

### 3. Asynchronous Resume Parsing

#### `POST /parse-resume-async`
Submits resume for background processing and returns job ID immediately.
**Automatically falls back to sync processing if worker is unavailable.**

**Request:** Same format as `/parse-resume` plus:
- `fallback_to_sync` (boolean, optional): Enable automatic fallback (default: true)

**Response (Job Created):**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Resume processing started",
  "estimatedTime": "15 seconds",
  "statusUrl": "/parse-resume-async/status/550e8400-e29b-41d4-a716-446655440000",
  "streamUrl": "/parse-resume-async/stream/550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (Sync Fallback - Worker Unavailable):**
```json
{
  "jobId": null,
  "status": "completed",
  "message": "Processed synchronously (worker unavailable)",
  "processingMode": "sync_fallback",
  "result": {
    // Same structure as /parse-resume
    "personal": { ... },
    "experience": [ ... ],
    "metadata": {
      "processing_mode": "sync_fallback",
      "fallback_reason": "worker_unavailable"
    }
  }
}
```

**Error Response (Worker Unavailable + Fallback Disabled):**
```json
{
  "detail": "Background worker is not available. Please use /parse-resume endpoint instead."
}
```

---

### 4. Job Status Polling

#### `GET /parse-resume-async/status/{job_id}`
Check the status of an async job (polling method).

**Response (Queued):**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "createdAt": 1703123456.789,
  "updatedAt": 1703123456.789
}
```

**Response (Processing):**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Processing resume...",
  "createdAt": 1703123456.789,
  "updatedAt": 1703123460.123
}
```

**Response (Completed):**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "createdAt": 1703123456.789,
  "updatedAt": 1703123470.456,
  "completedAt": 1703123470.456,
  "result": {
    // Same structure as synchronous response
    "personal": { ... },
    "experience": [ ... ],
    "education": [ ... ],
    "skills": [ ... ],
    "metadata": { ... }
  }
}
```

**Response (Failed):**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "error": "File too large (max 10MB)",
  "createdAt": 1703123456.789,
  "updatedAt": 1703123460.123,
  "failedAt": 1703123460.123
}
```

---

### 5. Real-Time Job Updates (SSE)

#### `GET /parse-resume-async/stream/{job_id}`
Server-Sent Events stream for real-time job status updates.

**Response Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**SSE Events:**

**Status Update Event:**
```
data: {
  "event": "status_update",
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Processing resume...",
  "updatedAt": 1703123460.123
}
```

**Completion Event:**
```
data: {
  "event": "status_update",
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "message": "Processing completed",
  "result": {
    // Same structure as synchronous response
    "personal": { ... },
    "experience": [ ... ],
    // ... complete result
  },
  "updatedAt": 1703123470.456
}

data: {"event": "complete"}
```

**Error Event:**
```
data: {
  "event": "status_update",
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "message": "Processing failed",
  "error": "File too large (max 10MB)",
  "updatedAt": 1703123460.123
}

data: {"event": "error"}
```

---

### 6. System Statistics

#### `GET /stats`
Get detailed system statistics and performance metrics.

**Response:**
```json
{
  "request_stats": {
    "total_requests": 1250,
    "successful_requests": 1180,
    "failed_requests": 70,
    "concurrent_requests": 15,
    "average_processing_time": 12.34
  },
  "cache_stats": {
    "hit_rate": 78.5,
    "total_hits": 892,
    "total_misses": 245,
    "cache_size": 156,
    "total_cost_saved_usd": 45.67
  },
  "system_info": {
    "gemini_configured": true,
    "aws_configured": true,
    "auth_configured": true,
    "prompt_caching_enabled": true
  }
}
```

#### `GET /cache/stats`
Get cache-specific statistics.

**Response:**
```json
{
  "hit_rate": 78.5,
  "total_hits": 892,
  "total_misses": 245,
  "cache_size": 156,
  "total_tokens_saved": 245680,
  "total_cost_saved_usd": 45.67,
  "avg_tokens_per_request": 2340
}
```

---

## Complete API Flows

### Flow 1: Synchronous Processing
```
1. Client submits resume via POST /parse-resume
2. Server processes immediately (15-60 seconds)
3. Server returns complete result
4. Done ✅
```

### Flow 2: Asynchronous with Polling
```
1. Client submits resume via POST /parse-resume-async
2. Server returns job ID immediately
3. Client polls GET /parse-resume-async/status/{jobId} every 2-3 seconds
4. When status = "completed", client gets result
5. Done ✅
```

### Flow 3: Asynchronous with Real-Time Updates (SSE)
```
1. Client submits resume via POST /parse-resume-async
2. Server returns job ID and stream URL
3. Client connects to GET /parse-resume-async/stream/{jobId}
4. Server sends real-time status updates via SSE
5. When complete, client receives result and connection closes
6. Done ✅
```

---

## Frontend Implementation Examples

### JavaScript Smart Implementation (Handles Fallback)
```javascript
// Submit job with automatic fallback handling
const response = await fetch('/parse-resume-async', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Origin': 'http://localhost:5173'
  },
  body: formData
});

const responseData = await response.json();

// Check if it was processed synchronously (fallback)
if (responseData.status === 'completed' && responseData.processingMode === 'sync_fallback') {
  console.log('Processed synchronously due to:', responseData.result.metadata.fallback_reason);
  return responseData.result; // Got result immediately
}

// Otherwise, it's async processing
const { jobId } = responseData;

// Poll for result
const pollForResult = async (jobId) => {
  while (true) {
    const statusResponse = await fetch(`/parse-resume-async/status/${jobId}`, {
      headers: {
        'Authorization': 'Bearer ' + token,
        'Origin': 'http://localhost:5173'
      }
    });

    const status = await statusResponse.json();

    if (status.status === 'completed') {
      return status.result;
    } else if (status.status === 'failed') {
      throw new Error(status.error);
    }

    // Wait 2 seconds before next poll
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
};

const result = await pollForResult(jobId);
```

### JavaScript SSE Implementation
```javascript
// Submit job
const response = await fetch('/parse-resume-async', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Origin': 'http://localhost:5173'
  },
  body: formData
});

const { jobId, streamUrl } = await response.json();

// Connect to SSE stream
const eventSource = new EventSource(streamUrl + '?authorization=' + token);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.event === 'status_update') {
    console.log('Status:', data.status);

    if (data.status === 'completed') {
      console.log('Result:', data.result);
      eventSource.close();
    } else if (data.status === 'failed') {
      console.error('Error:', data.error);
      eventSource.close();
    }
  } else if (data.event === 'complete') {
    eventSource.close();
  } else if (data.event === 'error') {
    eventSource.close();
  }
};

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
  eventSource.close();
};
```

---

## Error Handling

### Common Error Responses

**400 Bad Request - Invalid File Type:**
```json
{
  "detail": "Unsupported file type: exe. Allowed: pdf, doc, docx, png, jpg, jpeg, txt"
}
```

**413 Payload Too Large:**
```json
{
  "detail": "File too large (max 10MB)"
}
```

**401 Unauthorized:**
```json
{
  "detail": "Invalid or expired token"
}
```

**403 Forbidden - Invalid Origin:**
```json
{
  "detail": "Origin not allowed"
}
```

**404 Not Found - Job Not Found:**
```json
{
  "detail": "Job not found"
}
```

**503 Service Unavailable - Worker Down:**
```json
{
  "detail": "Background worker is not available. Please use /parse-resume endpoint instead."
}
```

---

## Rate Limiting & Performance

- **Concurrent Users**: Optimized for 100+ concurrent users
- **Processing Time**: Target 15 seconds, typically 5-20 seconds
- **File Size Limit**: 10MB maximum
- **Caching**: Results cached for 4 hours to improve performance
- **Queue Capacity**: In-memory queue with 4 worker threads

---

## Development & Testing

### Running the Server
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GEMINI_API_KEY="your_key"
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export JWT_SECRET_KEY="your_secret"

# Run server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Testing with cURL
```bash
# Health check
curl http://localhost:8000/

# Test sync endpoint
curl -X POST http://localhost:8000/parse-resume \
  -H "Authorization: Bearer your_token" \
  -H "Origin: http://localhost:5173" \
  -F "fileType=file" \
  -F "file=@resume.pdf"

# Test async endpoint
curl -X POST http://localhost:8000/parse-resume-async \
  -H "Authorization: Bearer your_token" \
  -H "Origin: http://localhost:5173" \
  -F "fileType=file" \
  -F "file=@resume.pdf"
```

### Testing SSE with JavaScript
```javascript
// Test SSE connection
const eventSource = new EventSource('http://localhost:8000/parse-resume-async/stream/test-job-id');
eventSource.onmessage = (event) => console.log(JSON.parse(event.data));
```