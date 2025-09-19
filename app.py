import asyncio
import time
import os
import json
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends, Form
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv
import uvicorn

from src.parsers.resume_processor import process_resume
from src.auth.auth_middleware import require_authentication, optional_authentication, require_valid_origin, optional_origin_validation
from src.parsers.result_cache import get_cache_stats, clear_cache


# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""

    # Startup
    print("🚀 Resume Parser API Starting...")
    print("📊 Production-ready for 100 concurrent users")

    # Verify environment variables
    required_vars = ['GEMINI_API_KEY', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'JWT_SECRET_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ Missing environment variables: {missing_vars}")
        raise ValueError(f"Missing required environment variables: {missing_vars}")

    print("✅ Environment variables validated")

    # Start background worker with error handling
    global worker_task
    try:
        worker_task = asyncio.create_task(worker())
        print("✅ Background worker started")
    except Exception as e:
        print(f"⚠️ Failed to start background worker: {str(e)}")
        print("⚠️ App will continue without async processing - sync endpoints still work")
        worker_task = None
    print("✅ Ready to process resumes")

    yield

    # Shutdown
    print("🛑 Resume Parser API Shutting down...")
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    print("✅ Background worker stopped")


# Initialize FastAPI with optimized settings for concurrency
app = FastAPI(
    title="Resume Parser API",
    description="Production-ready resume parsing service supporting PDF, DOC, DOCX, and Images",
    version="1.0.0",
    lifespan=lifespan
)

def get_managed_cors_origins():
    return [
            'https://jobstackuidev-gwakgfdgbgh5emdw.canadacentral-01.azurewebsites.net',
            'https://jobstackuiuat-cybnbdf8h6gkb7g3.canadacentral-01.azurewebsites.net',
            'http://localhost:5173'
        ]


def get_smart_cors_origins():
    """
    Smart CORS origin detection: Check environment first, then fall back to managed origins
    """
    # Check if environment has custom CORS origins
    env_origins = os.getenv('ALLOWED_ORIGINS')
    if env_origins:
        # Split by comma and clean whitespace
        origins = [origin.strip() for origin in env_origins.split(',') if origin.strip()]
        print(f"Using CORS origins from environment: {origins}")
        return origins

    # Fall back to managed origins
    managed_origins = get_managed_cors_origins()
    print(f"Using managed CORS origins: {managed_origins}")
    return managed_origins


# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_smart_cors_origins(),  # Smart origin detection: env first, then managed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global stats for monitoring
request_stats = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "concurrent_requests": 0,
    "average_processing_time": 0.0
}


# Job storage for async processing
job_storage = {}
job_queue = asyncio.Queue()
executor = ThreadPoolExecutor(max_workers=4)


# Job status types
class JobStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


async def process_resume_job(job_id: str, file_content: bytes, filename: str, request_params: Dict[str, Any], user_context: Dict[str, Any]):
    """Background worker function to process resume"""
    try:
        # Update job status to processing
        job_storage[job_id]["status"] = JobStatus.PROCESSING
        job_storage[job_id]["updated_at"] = time.time()

        print(f"🔄 Starting background processing for job: {job_id}")

        # Process the resume (same logic as sync endpoint)
        result = await process_resume(file_content, filename, request_params)

        # Add user context to metadata (same as sync endpoint)
        if "metadata" in result:
            result["metadata"]["user_id"] = user_context.get("user_id")
            result["metadata"]["origin"] = user_context.get("origin")
            result["metadata"]["origin_valid"] = user_context.get("origin_valid")

        # Store the result with same format as sync endpoint
        final_result = {
            **(result['data'] if result.get('success') else result),
            "metadata": result.get('metadata', {})
        }

        # Update job with result
        job_storage[job_id].update({
            "status": JobStatus.COMPLETED,
            "result": final_result,
            "completed_at": time.time(),
            "updated_at": time.time()
        })

        print(f"✅ Background processing completed for job: {job_id}")

    except Exception as e:
        # Update job with error
        job_storage[job_id].update({
            "status": JobStatus.FAILED,
            "error": str(e),
            "failed_at": time.time(),
            "updated_at": time.time()
        })

        print(f"❌ Background processing failed for job: {job_id}, error: {str(e)}")


async def worker():
    """Background worker that processes jobs from the queue - crash resistant"""
    worker_id = str(uuid.uuid4())[:8]
    print(f"🔄 Worker {worker_id} started")

    while True:
        job_data = None
        try:
            # Get job from queue with timeout to prevent hanging
            job_data = await asyncio.wait_for(job_queue.get(), timeout=30.0)

            # Process the job
            await process_resume_job(**job_data)
            job_queue.task_done()

        except asyncio.TimeoutError:
            # No jobs in queue, continue loop
            continue

        except Exception as e:
            print(f"❌ Worker {worker_id} error: {str(e)}")

            # Mark job as failed if we have job data
            if job_data and "job_id" in job_data:
                try:
                    job_id = job_data["job_id"]
                    if job_id in job_storage:
                        job_storage[job_id].update({
                            "status": JobStatus.FAILED,
                            "error": f"Worker error: {str(e)}",
                            "failed_at": time.time(),
                            "updated_at": time.time()
                        })
                        print(f"❌ Marked job {job_id} as failed due to worker error")
                except Exception as mark_error:
                    print(f"❌ Failed to mark job as failed: {str(mark_error)}")

            # Mark task as done to prevent queue hanging
            try:
                job_queue.task_done()
            except ValueError:
                pass  # task_done() called more times than get()

            # Sleep before retrying to prevent rapid error loops
            await asyncio.sleep(5)

        except asyncio.CancelledError:
            print(f"🛑 Worker {worker_id} cancelled")
            break


# Start background worker task
worker_task = None


@app.post("/parse-resume")
async def parse_resume_endpoint(
    fileType: str = Form(...),  # either "file" or "text"
    file: Optional[UploadFile] = File(default=None),
    text: Optional[str] = Form(default=None),
    fresh: bool = Form(default=False),
    auth_user: Optional[Dict[str, Any]] = Depends(require_authentication),
    origin_info: Optional[Dict[str, Any]] = Depends(require_valid_origin)
) -> JSONResponse:
    """
    Single endpoint for resume parsing
    Supports: PDF, DOC, DOCX, PNG, JPG, JPEG, TXT, or direct text input
    Target: 15-second response time
    Concurrency: 100+ users
    """

    request_start = time.time()
    request_stats["total_requests"] += 1
    request_stats["concurrent_requests"] += 1

    try:
        # Process based on fileType
        if fileType == "file":
            # Validate file
            if not file or not file.filename:
                raise HTTPException(status_code=400, detail="No file provided")

            # Check file size (10MB limit for Textract)
            content = await file.read()
            if len(content) > 10_000_000:  # 10MB
                raise HTTPException(status_code=413, detail="File too large (max 10MB)")

            # Validate file type
            allowed_extensions = ['pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'txt']
            file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''

            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
                )

            filename = file.filename

        elif fileType == "text":
            # Validate text input
            if not text or not text.strip():
                raise HTTPException(status_code=400, detail="No text provided")

            # Convert text to bytes for processing
            content = text.encode('utf-8')
            filename = "resume.txt"  # Default filename for text input

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid fileType. Must be 'file' or 'text'."
            )

        # Log authenticated user and origin
        user_id = auth_user.get("userId") if auth_user else "anonymous"
        origin = origin_info.get("origin") if origin_info else "no-origin"
        origin_valid = origin_info.get("is_origin_valid") if origin_info else True
        print(f"📄 Processing: {filename} ({len(content)} bytes) for user: {user_id} from origin: {origin} (valid: {origin_valid})")

        # Process the resume with request parameters
        request_params = {"fresh": fresh}
        result = await process_resume(content, filename, request_params)

        # Add user context and origin info to response metadata
        if "metadata" in result:
            result["metadata"]["user_id"] = user_id
            result["metadata"]["origin"] = origin
            result["metadata"]["origin_valid"] = origin_valid

        # Update stats
        processing_time = time.time() - request_start
        request_stats["successful_requests"] += 1
        request_stats["average_processing_time"] = (
            (request_stats["average_processing_time"] * (request_stats["successful_requests"] - 1) + processing_time)
            / request_stats["successful_requests"]
        )

        print(f"✅ Completed: {filename if fileType == 'text' else file.filename} in {processing_time:.2f}s")

        return JSONResponse(
            status_code=200,
            content={
                **(result['data'] if result.get('success') else result),
                "metadata": result.get('metadata', {})
            }
        )

    except HTTPException:
        request_stats["failed_requests"] += 1
        raise

    except Exception as e:
        request_stats["failed_requests"] += 1
        processing_time = time.time() - request_start

        print(f"❌ Error processing {file.filename}: {str(e)}")

        # Return structured error response
        error_response = {
            "success": False,
            "error": {
                "message": str(e),
                "filename": file.filename,
                "processing_time_seconds": round(processing_time, 2),
                "timestamp": time.time()
            },
            "data": {
                "personalInfo": {
                    "name": "", "email": "", "phone": "", "location": "",
                    "linkedin": "", "github": "", "portfolio": ""
                },
                "experience": [],
                "education": [],
                "skills": {"technical": [], "languages": [], "certifications": []},
                "summary": ""
            }
        }

        return JSONResponse(
            status_code=500,
            content=error_response
        )

    finally:
        request_stats["concurrent_requests"] -= 1

@app.post("/cached/parse-resume")
async def parse_resume_endpoint(
    fileType: str = Form(...),  # either "file" or "text"
    file: Optional[UploadFile] = File(default=None),
    text: Optional[str] = Form(default=None),
    fresh: bool = Form(default=False),
    auth_user: Optional[Dict[str, Any]] = Depends(require_authentication),
    origin_info: Optional[Dict[str, Any]] = Depends(require_valid_origin)
) -> JSONResponse:
    """
    Single endpoint for resume parsing
    Supports: PDF, DOC, DOCX, PNG, JPG, JPEG, TXT, or direct text input
    Target: 15-second response time
    Concurrency: 100+ users
    """

    request_start = time.time()
    request_stats["total_requests"] += 1
    request_stats["concurrent_requests"] += 1

    try:
        # Process based on fileType
        if fileType == "file":
            # Validate file
            if not file or not file.filename:
                raise HTTPException(status_code=400, detail="No file provided")

            # Check file size (10MB limit for Textract)
            content = await file.read()
            if len(content) > 10_000_000:  # 10MB
                raise HTTPException(status_code=413, detail="File too large (max 10MB)")

            # Validate file type
            allowed_extensions = ['pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'txt']
            file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''

            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
                )

            filename = file.filename

        elif fileType == "text":
            # Validate text input
            if not text or not text.strip():
                raise HTTPException(status_code=400, detail="No text provided")

            # Convert text to bytes for processing
            content = text.encode('utf-8')
            filename = "resume.txt"  # Default filename for text input

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid fileType. Must be 'file' or 'text'."
            )

        # Log authenticated user and origin
        user_id = auth_user.get("userId") if auth_user else "anonymous"
        origin = origin_info.get("origin") if origin_info else "no-origin"
        origin_valid = origin_info.get("is_origin_valid") if origin_info else True
        print(f"📄 Processing: {filename} ({len(content)} bytes) for user: {user_id} from origin: {origin} (valid: {origin_valid})")

        # Process the resume with request parameters
        request_params = {"fresh": fresh}
        result = await process_resume(content, filename, request_params)

        # Add user context and origin info to response metadata
        if "metadata" in result:
            result["metadata"]["user_id"] = user_id
            result["metadata"]["origin"] = origin
            result["metadata"]["origin_valid"] = origin_valid

        # Update stats
        processing_time = time.time() - request_start
        request_stats["successful_requests"] += 1
        request_stats["average_processing_time"] = (
            (request_stats["average_processing_time"] * (request_stats["successful_requests"] - 1) + processing_time)
            / request_stats["successful_requests"]
        )

        print(f"✅ Completed: {filename if fileType == 'text' else file.filename} in {processing_time:.2f}s")

        return JSONResponse(
            status_code=200,
            content={
                **(result['data'] if result.get('success') else result),
                "metadata": result.get('metadata', {})
            }
        )

    except HTTPException:
        request_stats["failed_requests"] += 1
        raise

    except Exception as e:
        request_stats["failed_requests"] += 1
        processing_time = time.time() - request_start

        print(f"❌ Error processing {file.filename}: {str(e)}")

        # Return structured error response
        error_response = {
            "success": False,
            "error": {
                "message": str(e),
                "filename": file.filename,
                "processing_time_seconds": round(processing_time, 2),
                "timestamp": time.time()
            },
            "data": {
                "personalInfo": {
                    "name": "", "email": "", "phone": "", "location": "",
                    "linkedin": "", "github": "", "portfolio": ""
                },
                "experience": [],
                "education": [],
                "skills": {"technical": [], "languages": [], "certifications": []},
                "summary": ""
            }
        }

        return JSONResponse(
            status_code=500,
            content=error_response
        )

    finally:
        request_stats["concurrent_requests"] -= 1


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring
    """
    cache_stats = get_cache_stats()
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "stats": request_stats,
        "cache": {
            "result_cache_enabled": cache_stats["enabled"],
            "cached_entries": cache_stats["total_entries"],
            "cache_hits": cache_stats["total_hits"],
            "cost_savings_usd": cache_stats["total_cost_saved_usd"]
        },
        "environment": {
            "gemini_configured": bool(os.getenv('GEMINI_API_KEY')),
            "aws_configured": bool(os.getenv('AWS_ACCESS_KEY_ID')),
            "auth_configured": bool(os.getenv('JWT_SECRET_KEY')),
            "prompt_caching_enabled": os.getenv('USE_PROMPT_CACHING', 'false').lower() == 'true'
        }
    }


@app.post("/parse-resume-async")
async def parse_resume_async_endpoint(
    fileType: str = Form(...),  # either "file" or "text"
    file: Optional[UploadFile] = File(default=None),
    text: Optional[str] = Form(default=None),
    fresh: bool = Form(default=False),
    fallback_to_sync: bool = Form(default=True),  # New parameter for fallback control
    auth_user: Optional[Dict[str, Any]] = Depends(require_authentication),
    origin_info: Optional[Dict[str, Any]] = Depends(require_valid_origin)
) -> JSONResponse:
    """
    Async endpoint for resume parsing - returns job ID immediately
    Automatically falls back to sync processing if worker is unavailable
    """
    # Check if worker is available
    if worker_task is None or worker_task.done():
        if fallback_to_sync:
            print("⚠️ Worker unavailable, falling back to synchronous processing")

            # Call the sync endpoint directly with same parameters
            try:
                sync_result = await parse_resume_endpoint(
                    fileType=fileType,
                    file=file,
                    text=text,
                    fresh=fresh,
                    auth_user=auth_user,
                    origin_info=origin_info
                )

                # Return sync result but indicate it was processed synchronously
                result_content = json.loads(sync_result.body)
                result_content["metadata"]["processing_mode"] = "sync_fallback"
                result_content["metadata"]["fallback_reason"] = "worker_unavailable"

                return JSONResponse(
                    status_code=200,  # 200 OK (completed immediately)
                    content={
                        "jobId": None,  # No job ID since processed immediately
                        "status": "completed",
                        "message": "Processed synchronously (worker unavailable)",
                        "processingMode": "sync_fallback",
                        "result": result_content
                    }
                )

            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Sync fallback failed: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=503,
                detail="Background worker is not available. Please use /parse-resume endpoint instead."
            )

    try:
        # Same validation logic as sync endpoint
        if fileType == "file":
            if not file or not file.filename:
                raise HTTPException(status_code=400, detail="No file provided")

            content = await file.read()
            if len(content) > 10_000_000:  # 10MB
                raise HTTPException(status_code=413, detail="File too large (max 10MB)")

            allowed_extensions = ['pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'txt']
            file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''

            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
                )

            filename = file.filename

        elif fileType == "text":
            if not text or not text.strip():
                raise HTTPException(status_code=400, detail="No text provided")

            content = text.encode('utf-8')
            filename = "resume.txt"

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid fileType. Must be 'file' or 'text'."
            )

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Prepare user context (same as sync endpoint)
        user_id = auth_user.get("userId") if auth_user else "anonymous"
        origin = origin_info.get("origin") if origin_info else "no-origin"
        origin_valid = origin_info.get("is_origin_valid") if origin_info else True

        user_context = {
            "user_id": user_id,
            "origin": origin,
            "origin_valid": origin_valid
        }

        # Store job in storage
        job_storage[job_id] = {
            "id": job_id,
            "status": JobStatus.QUEUED,
            "created_at": time.time(),
            "updated_at": time.time(),
            "filename": filename,
            "user_context": user_context
        }

        # Add job to queue for background processing with retry mechanism
        try:
            await asyncio.wait_for(job_queue.put({
                "job_id": job_id,
                "file_content": content,
                "filename": filename,
                "request_params": {"fresh": fresh},
                "user_context": user_context
            }), timeout=5.0)  # 5 second timeout for queue operations
        except asyncio.TimeoutError:
            if fallback_to_sync:
                print("⚠️ Queue timeout, falling back to synchronous processing")

                # Remove job from storage since we're falling back
                if job_id in job_storage:
                    del job_storage[job_id]

                # Process synchronously
                try:
                    sync_result = await parse_resume_endpoint(
                        fileType=fileType,
                        file=file,
                        text=text,
                        fresh=fresh,
                        auth_user=auth_user,
                        origin_info=origin_info
                    )

                    result_content = json.loads(sync_result.body)
                    result_content["metadata"]["processing_mode"] = "sync_fallback"
                    result_content["metadata"]["fallback_reason"] = "queue_timeout"

                    return JSONResponse(
                        status_code=200,
                        content={
                            "jobId": None,
                            "status": "completed",
                            "message": "Processed synchronously (queue timeout)",
                            "processingMode": "sync_fallback",
                            "result": result_content
                        }
                    )
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Sync fallback failed: {str(e)}")
            else:
                raise HTTPException(status_code=503, detail="Queue is overloaded, please try again")

        print(f"📋 Queued job: {job_id} for file: {filename}")

        # Return job ID immediately with SSE stream URL
        return JSONResponse(
            status_code=202,  # 202 Accepted
            content={
                "jobId": job_id,
                "status": JobStatus.QUEUED,
                "message": "Resume processing started",
                "estimatedTime": "15 seconds",
                "statusUrl": f"/parse-resume-async/status/{job_id}",
                "streamUrl": f"/parse-resume-async/stream/{job_id}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")


@app.get("/parse-resume-async/status/{job_id}")
async def get_job_status(
    job_id: str,
    auth_user: Optional[Dict[str, Any]] = Depends(require_authentication),
    origin_info: Optional[Dict[str, Any]] = Depends(require_valid_origin)
) -> JSONResponse:
    """
    Get status of async resume parsing job
    Returns the same result format as /parse-resume when completed
    """

    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")

    job = job_storage[job_id]

    # Basic security: check if user context matches (optional)
    user_id = auth_user.get("userId") if auth_user else "anonymous"
    if job["user_context"]["user_id"] != user_id and user_id != "anonymous":
        raise HTTPException(status_code=403, detail="Access denied to this job")

    response_data = {
        "jobId": job_id,
        "status": job["status"],
        "createdAt": job["created_at"],
        "updatedAt": job["updated_at"]
    }

    # Add result if completed
    if job["status"] == JobStatus.COMPLETED:
        response_data["result"] = job["result"]
        response_data["completedAt"] = job["completed_at"]

    # Add error if failed
    elif job["status"] == JobStatus.FAILED:
        response_data["error"] = job["error"]
        response_data["failedAt"] = job["failed_at"]

    # Add progress info for processing status
    elif job["status"] == JobStatus.PROCESSING:
        response_data["message"] = "Processing resume..."

    return JSONResponse(content=response_data)


@app.get("/parse-resume-async/stream/{job_id}")
async def stream_job_status(
    job_id: str,
    auth_user: Optional[Dict[str, Any]] = Depends(require_authentication),
    origin_info: Optional[Dict[str, Any]] = Depends(require_valid_origin)
):
    """
    SSE endpoint for real-time job status updates
    Streams job progress until completion or failure
    """

    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")

    job = job_storage[job_id]

    # Basic security: check if user context matches
    user_id = auth_user.get("userId") if auth_user else "anonymous"
    if job["user_context"]["user_id"] != user_id and user_id != "anonymous":
        raise HTTPException(status_code=403, detail="Access denied to this job")

    async def generate_sse_events():
        """Generate SSE events for job status updates"""
        last_status = None
        last_updated = 0

        while True:
            try:
                current_job = job_storage.get(job_id)
                if not current_job:
                    # Job was deleted, send error and close
                    yield f"data: {{'event': 'error', 'message': 'Job not found'}}\n\n"
                    break

                # Check if status or content changed
                if (current_job["status"] != last_status or
                    current_job["updated_at"] != last_updated):

                    last_status = current_job["status"]
                    last_updated = current_job["updated_at"]

                    # Prepare SSE event data
                    event_data = {
                        "event": "status_update",
                        "jobId": job_id,
                        "status": current_job["status"],
                        "updatedAt": current_job["updated_at"]
                    }

                    # Add specific data based on status
                    if current_job["status"] == JobStatus.QUEUED:
                        event_data["message"] = "Job queued for processing"

                    elif current_job["status"] == JobStatus.PROCESSING:
                        event_data["message"] = "Processing resume..."

                    elif current_job["status"] == JobStatus.COMPLETED:
                        event_data["message"] = "Processing completed"
                        event_data["result"] = current_job["result"]

                        # Send final result and close connection
                        yield f"data: {json.dumps(event_data)}\n\n"
                        yield f"data: {{'event': 'complete'}}\n\n"
                        break

                    elif current_job["status"] == JobStatus.FAILED:
                        event_data["message"] = "Processing failed"
                        event_data["error"] = current_job.get("error", "Unknown error")

                        # Send error and close connection
                        yield f"data: {json.dumps(event_data)}\n\n"
                        yield f"data: {{'event': 'error'}}\n\n"
                        break

                    # Send status update
                    yield f"data: {json.dumps(event_data)}\n\n"

                # Wait before next check (poll every 2 seconds)
                await asyncio.sleep(2)

            except Exception as e:
                # Send error event and close connection
                error_data = {
                    "event": "error",
                    "message": f"Stream error: {str(e)}"
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                break

    return StreamingResponse(
        generate_sse_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """
    Detailed statistics endpoint
    """
    return {
        "request_stats": request_stats,
        "success_rate": (
            request_stats["successful_requests"] / request_stats["total_requests"] * 100
            if request_stats["total_requests"] > 0 else 0
        ),
        "average_processing_time": round(request_stats["average_processing_time"], 2),
        "concurrent_requests": request_stats["concurrent_requests"]
    }


@app.post("/parse-resume-test")
async def parse_resume_test_endpoint(
    file: UploadFile = File(...),
    fresh: bool = False
) -> JSONResponse:
    """
    Test endpoint for resume parsing without authentication
    Use this for testing and development only
    """
    return await parse_resume_endpoint(file, fresh, auth_user=None, origin_info=None)


@app.get("/")
async def root():
    """
    API root endpoint
    """
    return {
        "message": "Resume Parser API",
        "version": "1.0.0",
        "status": "running",
        "authentication": {
            "required": True,
            "type": "JWT Bearer Token",
            "header": "Authorization: Bearer <token>"
        },
        "endpoints": {
            "parse": "/parse-resume (requires auth)",
            "parse_test": "/parse-resume-test (no auth, for testing)",
            "health": "/health",
            "stats": "/stats"
        },
        "supported_formats": ["PDF", "DOC", "DOCX", "PNG", "JPG", "JPEG"],
        "max_file_size": "10MB",
        "target_response_time": "15 seconds",
        "caching": {
            "result_cache": "Enabled (4 hours TTL)",
            "prompt_cache": "Available with USE_PROMPT_CACHING=true",
            "cache_bypass": "Use ?fresh=true parameter"
        }
    }


@app.get("/cache/stats")
async def get_cache_stats_endpoint() -> Dict[str, Any]:
    """
    Get result cache statistics
    """
    return {
        "cache_stats": get_cache_stats(),
        "prompt_cache_enabled": os.getenv("USE_PROMPT_CACHING", "false").lower() == "true"
    }


@app.post("/cache/clear")
async def clear_cache_endpoint(pattern: str = None) -> Dict[str, Any]:
    """
    Clear result cache (optionally with pattern)
    Use for cache management and testing
    """
    cleared_count = clear_cache(pattern)
    return {
        "message": f"Cleared {cleared_count} cache entries",
        "pattern": pattern or "all",
        "cleared_count": cleared_count
    }


@app.get("/secure/origin-test")
async def origin_protected_endpoint(
    origin_info: Dict[str, Any] = Depends(require_valid_origin)
) -> Dict[str, Any]:
    """
    Example endpoint that requires valid origin header
    Demonstrates origin validation functionality
    """
    return {
        "message": "Origin validation successful",
        "origin_info": origin_info,
        "allowed_origins": get_smart_cors_origins(),
        "timestamp": time.time()
    }


@app.get("/secure/auth-and-origin")
async def auth_and_origin_protected_endpoint(
    auth_user: Dict[str, Any] = Depends(require_authentication),
    origin_info: Dict[str, Any] = Depends(optional_origin_validation)
) -> Dict[str, Any]:
    """
    Example endpoint that requires authentication and validates origin
    Demonstrates combining auth and origin validation
    """
    return {
        "message": "Authentication and origin validation successful",
        "user_info": {
            "user_id": auth_user.get("userId"),
            "is_authenticated": auth_user.get("is_authenticated")
        },
        "origin_info": origin_info,
        "timestamp": time.time()
    }


# Concurrency settings for production
if __name__ == "__main__":
    print("🚀 Starting Resume Parser API...")
    print("💡 For production deployment, use: uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4")

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Set to False for production
        access_log=True,
        log_level="info",
        workers=1  # For development; use multiple workers in production
    )