import asyncio
import json
import time
import os
from typing import Dict, Any, Optional
from src.parsers.text_extractor import extract_text
from src.parsers.gemini_normalizer import normalize_with_gemini
from src.parsers.gemini_cached_normalizer import normalize_with_gemini_cached
from src.parsers.result_cache import (
    get_cache_key, get_from_cache, set_to_cache,
    should_bypass_cache, get_cache_stats
)


async def process_resume(file_content: bytes, filename: str, request_params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Main processing pipeline for resume parsing with result caching

    Flow: Cache Check → File → Text Extraction → Gemini Normalization → Cache Store → Structured Response
    Target: 15-second response time for production use (0.001s for cache hits)
    """
    start_time = time.time()
    request_params = request_params or {}

    try:
        # Step 0: Check result cache first
        cache_key = get_cache_key(file_content, filename)

        if not should_bypass_cache(request_params):
            cached_result = get_from_cache(cache_key)
            if cached_result:
                cache_time = time.time() - start_time
                print(f"✅ Cache hit for {filename} in {cache_time:.3f}s")
                return cached_result

        print(f"📄 Processing new resume: {filename}")

        # Step 1: Extract text based on file type (8-12 seconds)
        print(f"Starting text extraction for {filename}...")
        raw_text = await extract_text(file_content, filename)

        if not raw_text or len(raw_text.strip()) < 50:
            raise ValueError(f"Insufficient text extracted from {filename}")

        extraction_time = time.time() - start_time
        print(f"Text extraction completed in {extraction_time:.2f}s")

        # Step 2: Normalize with Gemini (3-5 seconds)
        # Choose caching mode based on environment configuration
        use_caching = os.getenv("USE_PROMPT_CACHING", "false").lower() == "true"

        if use_caching:
            print("Starting Gemini normalization with caching (89% cost reduction)...")
            normalization_start = time.time()
            structured_data = await normalize_with_gemini_cached(raw_text)
        else:
            print("Starting Gemini normalization (standard mode)...")
            normalization_start = time.time()
            structured_data = await normalize_with_gemini(raw_text)

        normalization_time = time.time() - normalization_start
        cache_mode = "cached" if use_caching else "standard"
        print(f"Gemini normalization ({cache_mode}) completed in {normalization_time:.2f}s")

        # Step 3: Add processing metadata
        total_time = time.time() - start_time
        result = add_processing_metadata(structured_data, filename, total_time, len(raw_text))

        # Step 4: Cache the result ONLY if successful
        if result.get("success", False):
            try:
                # Extract cost and token info for cache stats
                tokens_used = 0
                cost_usd = 0

                if "data" in result and "parseMetadata" in result["data"]:
                    metadata = result["data"]["parseMetadata"]
                    if "tokens" in metadata:
                        tokens_used = metadata["tokens"].get("total_tokens", 0)
                    if "cost" in metadata:
                        cost_usd = metadata["cost"].get("total_cost_usd", 0)

                # Cache successful results for 4 hours
                set_to_cache(
                    cache_key,
                    result,
                    ttl=4 * 3600,  # 4 hours
                    tokens_used=tokens_used,
                    cost_usd=cost_usd
                )
                print(f"💾 Successful result cached with key: {cache_key[:16]}...")
            except Exception as e:
                print(f"⚠️ Failed to cache result: {str(e)}")
        else:
            print(f"❌ Failed result NOT cached - can retry with fresh=true")

        print(f"Total processing time: {total_time:.2f}s")
        return result

    except Exception as e:
        total_time = time.time() - start_time
        print(f"Error processing {filename}: {str(e)}")
        return create_error_response(str(e), filename, total_time)


def add_processing_metadata(data: Dict[str, Any], filename: str, processing_time: float, text_length: int) -> Dict[str, Any]:
    """Add metadata to successful processing results"""

    file_extension = filename.lower().split('.')[-1] if '.' in filename else 'unknown'

    # Add success indicator to parseMetadata if it exists
    if "parseMetadata" in data:
        data["parseMetadata"]["processing_status"] = {
            "status": "success",
            "error_type": None,
            "can_retry": False,
            "cached": False,  # Will be updated if from cache
            "processing_method": get_processing_method(filename)
        }

    return {
        "success": True,
        "data": data,
        "metadata": {
            "filename": filename,
            "file_type": file_extension,
            "processing_time_seconds": round(processing_time, 2),
            "extracted_text_length": text_length,
            "processing_method": get_processing_method(filename),
            "timestamp": time.time()
        }
    }


def create_error_response(error_message: str, filename: str, processing_time: float) -> Dict[str, Any]:
    """Create standardized error response with retry indicators"""

    empty_structure = get_empty_resume_structure()

    # Update the parseMetadata with error info and retry suggestions
    empty_structure["data"]["parseMetadata"]["parseTime"] = processing_time
    empty_structure["data"]["parseMetadata"]["warnings"] = [
        {
            "type": "processing_error",
            "message": error_message,
            "section": "all",
            "field": "",
            "severity": "high"
        }
    ]

    # Add clear failure indicators for frontend
    empty_structure["data"]["parseMetadata"]["processing_status"] = {
        "status": "failed",
        "error_type": "processing_failure",
        "can_retry": True,
        "retry_suggestions": [
            "Try uploading again with ?fresh=true parameter",
            "Ensure the file is not corrupted",
            "Check if the file contains readable text",
            "Try a different file format if possible"
        ],
        "cached": False,
        "retry_endpoint": "Same endpoint with ?fresh=true"
    }

    return empty_structure


def get_processing_method(filename: str) -> str:
    """Determine processing method based on filename"""

    ext = filename.lower().split('.')[-1] if '.' in filename else ''

    if ext in ['jpg', 'jpeg', 'png']:
        return 'aws_textract_ocr'
    elif ext == 'pdf':
        return 'aws_textract_pdf'
    elif ext in ['doc', 'docx']:
        return 'python_docx'
    elif ext == 'txt':
        return 'direct_text'
    else:
        return 'unknown'


def get_empty_resume_structure() -> Dict[str, Any]:
    """Return empty structure matching static_prompt.py format for error cases"""

    content_data = {
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

    return {
        "success": False,
        "data": {
            "content": content_data,
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
                "warnings": [],
                "suggestions": [],
                "extractedKeywords": [],
                "industryDetected": "",
                "experienceLevel": "Entry",
                "totalExperienceYears": 0,
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
        }
    }


async def validate_resume_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and clean the resume data structure"""

    # Ensure all required fields exist
    if "personalInfo" not in data:
        data["personalInfo"] = {}

    # Validate personalInfo fields
    required_personal_fields = ["name", "email", "phone", "location", "linkedin", "github", "portfolio"]
    for field in required_personal_fields:
        if field not in data["personalInfo"]:
            data["personalInfo"][field] = ""

    # Ensure arrays exist
    if "experience" not in data or not isinstance(data["experience"], list):
        data["experience"] = []

    if "education" not in data or not isinstance(data["education"], list):
        data["education"] = []

    if "skills" not in data:
        data["skills"] = {"technical": [], "languages": [], "certifications": []}

    if "summary" not in data:
        data["summary"] = ""

    return data


def calculate_confidence_score(data: Dict[str, Any], text_length: int) -> float:
    """Calculate confidence score based on extracted data completeness"""

    score = 0.0
    total_weight = 1.0

    # Personal info completeness (40% weight)
    personal_info = data.get("personalInfo", {})
    personal_fields_filled = sum(1 for field in ["name", "email", "phone"] if personal_info.get(field, "").strip())
    score += (personal_fields_filled / 3) * 0.4

    # Experience data (30% weight)
    experience = data.get("experience", [])
    if experience and len(experience) > 0:
        score += 0.3

    # Education data (20% weight)
    education = data.get("education", [])
    if education and len(education) > 0:
        score += 0.2

    # Text length factor (10% weight)
    if text_length > 500:
        score += 0.1
    elif text_length > 200:
        score += 0.05

    return min(round(score, 2), 1.0)