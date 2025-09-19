import os
import json
import time
import threading
from typing import Optional, Dict, Any
import requests
import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account
import logging

logger = logging.getLogger(__name__)

# Global cache variables for prompt caching
resume_cache_id: Optional[str] = None
resume_cache_expiry: Optional[float] = None
resume_cache_lock = threading.Lock()

# Google Cloud credentials
_credentials = None
_google_config = None


def get_google_credentials():
    """Initialize Google Cloud credentials for Vertex AI"""
    global _credentials, _google_config

    if _credentials is None:
        # Get credentials from JSON string environment variable
        google_app_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if not google_app_credentials:
            raise ValueError("Missing GOOGLE_APPLICATION_CREDENTIALS secret")

        # Parse the JSON string into a dict
        credentials_info = json.loads(google_app_credentials)

        # Create credentials object
        _credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        _google_config = {"project_id": credentials_info.get("project_id")}
        logger.info("✅ Loaded Google Cloud credentials from GOOGLE_APPLICATION_CREDENTIALS environment variable")

    return _credentials, _google_config


def create_prompt_cache(static_instructions: str, model: str) -> str:
    """Create cache entry for static instructions"""
    try:
        credentials, config = get_google_credentials()

        logger.info(f"Using project: {config.get('project_id')}")

        # Get access token
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        access_token = credentials.token

        if not access_token:
            raise Exception("Failed to obtain access token from credentials")

        logger.info(f"Access token obtained, length: {len(access_token) if access_token else 0}")

        endpoint = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{config['project_id']}/locations/us-central1/cachedContents"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        data = {
            "model": f"projects/{config['project_id']}/locations/us-central1/publishers/google/models/{model}",
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": static_instructions}]
                }
            ],
            "ttl": "86400s"  # 24 hours
        }

        logger.info(f"Creating prompt cache for model: {model}")
        response = requests.post(endpoint, headers=headers, json=data, timeout=60)
        response.raise_for_status()

        result = response.json()
        cache_id = result["name"]

        logger.info(f"✅ Prompt cache created: {cache_id}")
        return cache_id

    except Exception as e:
        logger.error(f"❌ Failed to create prompt cache: {str(e)}")
        raise Exception(f"Prompt cache creation failed: {str(e)}")


def init_prompt_cache(static_instructions: str, model: str) -> str:
    """Initialize and manage prompt cache with thread safety"""
    global resume_cache_id, resume_cache_expiry

    now = time.time() * 1000  # Convert to milliseconds

    # Check if cache is still valid
    if resume_cache_id and resume_cache_expiry and now < resume_cache_expiry:
        return resume_cache_id

    with resume_cache_lock:
        # Double-check after acquiring lock
        if resume_cache_id and resume_cache_expiry and now < resume_cache_expiry:
            return resume_cache_id

        logger.info("Creating resume parser prompt cache...")
        resume_cache_id = create_prompt_cache(static_instructions, model)
        resume_cache_expiry = time.time() * 1000 + (23 * 60 * 60 * 1000)  # 23 hours
        logger.info(f"Resume Parser Cache created: {resume_cache_id}")
        return resume_cache_id


def build_dynamic_prompt(resume_text: str) -> str:
    """Build dynamic prompt that references cached instructions"""
    return f"""Use the cached instructions.

<<<RESUME_START>>>
{resume_text}
<<<RESUME_END>>>

RESPONSE FORMAT:
Return ONLY the JSON object as specified in the cached schema. No markdown, no explanations."""


def call_gemini_with_cache_and_retry(
    static_instructions: str,
    dynamic_prompt: str,
    model: str = "gemini-2.5-flash-lite",
    max_retries: int = 2
) -> str:
    """Call Gemini API with caching and retry logic"""
    global resume_cache_id, resume_cache_expiry

    retries = 0

    while retries < max_retries:
        try:
            cache_id = init_prompt_cache(static_instructions, model)
            credentials, config = get_google_credentials()

            # Get access token
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
            access_token = credentials.token

            if not access_token:
                raise Exception("Failed to obtain access token from credentials")

            logger.info(f"Access token obtained for API call, length: {len(access_token) if access_token else 0}")

            endpoint = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{config['project_id']}/locations/us-central1/publishers/google/models/{model}:generateContent"

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            data = {
                "cachedContent": cache_id,
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": dynamic_prompt}]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": 8000,
                    "temperature": 0.1,
                    "topP": 0.8,
                    "topK": 40
                }
            }

            logger.info(f"Calling Gemini with cached content: {cache_id[:50]}...")
            response = requests.post(endpoint, headers=headers, json=data, timeout=90)
            response.raise_for_status()

            result = response.json()

            # Extract text from response
            if (result.get("candidates") and
                result["candidates"][0].get("content") and
                result["candidates"][0]["content"].get("parts") and
                result["candidates"][0]["content"]["parts"][0].get("text")):

                response_text = result["candidates"][0]["content"]["parts"][0]["text"]
                logger.info(f"✅ Gemini response received ({len(response_text)} chars)")
                return response_text
            else:
                raise Exception("Invalid response structure from Gemini API")

        except Exception as err:
            error_str = str(err)
            if ("Cache content" in error_str or "cached" in error_str.lower()) and retries < max_retries:
                logger.warning(f"Gemini cache expired, retrying attempt {retries + 1}")
                # Force refresh local cache
                resume_cache_id = None
                resume_cache_expiry = None
                retries += 1
                continue

            logger.error(f"❌ Gemini API call failed: {error_str}")
            raise Exception(f"Gemini API call failed: {error_str}")

    raise Exception(f"Failed after {max_retries} retries")


def get_cache_status() -> Dict[str, Any]:
    """Get current cache status for monitoring"""
    global resume_cache_id, resume_cache_expiry

    now = time.time() * 1000
    left_time_minutes = 0

    if resume_cache_expiry:
        left_time_minutes = max(round((resume_cache_expiry - now) / 60000), 0)

    return {
        "cache_id": resume_cache_id,
        "cache_active": bool(resume_cache_id and resume_cache_expiry and now < resume_cache_expiry),
        "time_left_minutes": left_time_minutes,
        "expiry_timestamp": resume_cache_expiry / 1000 if resume_cache_expiry else None
    }