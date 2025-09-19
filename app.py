import asyncio
import time
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    print("✅ Ready to process resumes")

    yield

    # Shutdown
    print("🛑 Resume Parser API Shutting down...")


# Initialize FastAPI with optimized settings for concurrency
app = FastAPI(
    title="Resume Parser API",
    description="Production-ready resume parsing service supporting PDF, DOC, DOCX, and Images",
    version="1.0.0",
    lifespan=lifespan
)

def get_managed_cors_origins():
    return [
            'https://jobstackuidev-gwakgfdgbgh5emdw.canadacentral-01.azurewebsites.net/',
            'https://jobstackuiuat-cybnbdf8h6gkb7g3.canadacentral-01.azurewebsites.net/',
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


@app.post("/parse-resume")
async def parse_resume_endpoint(
    file: UploadFile = File(...),
    fresh: bool = False,
    auth_user: Optional[Dict[str, Any]] = Depends(require_authentication),
    origin_info: Optional[Dict[str, Any]] = Depends(require_valid_origin)
) -> JSONResponse:
    """
    Single endpoint for resume parsing
    Supports: PDF, DOC, DOCX, PNG, JPG, JPEG
    Target: 15-second response time
    Concurrency: 100+ users
    """

    request_start = time.time()
    request_stats["total_requests"] += 1
    request_stats["concurrent_requests"] += 1

    try:
        # Validate file
        if not file.filename:
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

        # Log authenticated user and origin
        user_id = auth_user.get("userId") if auth_user else "anonymous"
        origin = origin_info.get("origin") if origin_info else "no-origin"
        origin_valid = origin_info.get("is_origin_valid") if origin_info else True
        print(f"📄 Processing: {file.filename} ({len(content)} bytes) for user: {user_id} from origin: {origin} (valid: {origin_valid})")

        # Process the resume with request parameters
        request_params = {"fresh": fresh}
        result = await process_resume(content, file.filename, request_params)

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

        print(f"✅ Completed: {file.filename} in {processing_time:.2f}s")

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