"""
Result caching system for parsed resumes
Provides 100% cost savings on duplicate resume uploads
"""
import hashlib
import json
import time
import logging
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

# In-memory cache for development (replace with Redis in production)
_cache_store: Dict[str, Dict[str, Any]] = {}

# Cache configuration
CACHE_CONFIG = {
    "default_ttl": (1/6) * 3600,      # 10 mins default
    "max_ttl": 24 * 3600,         # 24 hours maximum
    "max_cache_size": 1000,       # Maximum number of cached items
    "enable_caching": True,       # Global cache enable/disable
}

def get_cache_config() -> Dict[str, Any]:
    """Get cache configuration with environment overrides"""
    config = CACHE_CONFIG.copy()

    # Allow environment variables to override
    if os.getenv("RESULT_CACHE_TTL"):
        config["default_ttl"] = int(os.getenv("RESULT_CACHE_TTL"))

    if os.getenv("RESULT_CACHE_ENABLED"):
        config["enable_caching"] = os.getenv("RESULT_CACHE_ENABLED").lower() == "true"

    return config


def generate_content_hash(content: str) -> str:
    """
    Generate SHA-256 hash of content for cache key
    """
    # Normalize content (remove extra whitespace, lowercase)
    normalized = " ".join(content.lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def get_cache_key(file_content: bytes, filename: str) -> str:
    """
    Generate unique cache key based on file content
    """
    # Create hash from file content
    content_hash = hashlib.sha256(file_content).hexdigest()

    # Include file extension in key (same content, different format)
    file_ext = filename.split('.')[-1].lower() if '.' in filename else 'unknown'

    return f"resume_result:{file_ext}:{content_hash[:16]}"


def get_from_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached result if available and not expired
    """
    config = get_cache_config()

    if not config["enable_caching"]:
        return None

    if cache_key not in _cache_store:
        logger.info(f"Cache miss: {cache_key}")
        return None

    cached_item = _cache_store[cache_key]

    # Check if expired
    if time.time() > cached_item["expires_at"]:
        logger.info(f"Cache expired: {cache_key}")
        del _cache_store[cache_key]
        return None

    # Update access time
    cached_item["last_accessed"] = time.time()
    cached_item["hit_count"] += 1

    logger.info(f"Cache hit: {cache_key} (hit #{cached_item['hit_count']})")

    # Return the cached result with cache metadata
    result = cached_item["data"].copy()

    # Add cache information to metadata
    cache_age_seconds = time.time() - cached_item["created_at"]
    expires_in_seconds = cached_item["expires_at"] - time.time()

    if "data" in result and "parseMetadata" in result["data"]:
        # Update processing status for cached response
        if "processing_status" in result["data"]["parseMetadata"]:
            result["data"]["parseMetadata"]["processing_status"]["cached"] = True
            result["data"]["parseMetadata"]["processing_status"]["cache_hit"] = True

        # Add detailed cache information
        result["data"]["parseMetadata"]["cache"] = {
            "hit": True,
            "cache_key": cache_key[:8] + "...",  # Shortened for privacy
            "age_minutes": round(cache_age_seconds / 60, 1),
            "expires_in_minutes": round(expires_in_seconds / 60, 1),
            "hit_count": cached_item["hit_count"],
            "created_at": cached_item["created_at"],
            "response_time": 0.001,  # Near-instant for cache hit
            "cost_savings": {
                "tokens_saved": cached_item.get("tokens_saved", 0),
                "cost_saved_usd": cached_item.get("cost_saved_usd", 0),
                "cost_saved_inr": cached_item.get("cost_saved_inr", 0)
            }
        }

    return result


def set_to_cache(
    cache_key: str,
    data: Dict[str, Any],
    ttl: Optional[int] = None,
    tokens_used: int = 0,
    cost_usd: float = 0
) -> bool:
    """
    Store result in cache with TTL
    """
    config = get_cache_config()

    if not config["enable_caching"]:
        return False

    # Use provided TTL or default
    ttl = ttl or config["default_ttl"]
    ttl = min(ttl, config["max_ttl"])  # Don't exceed max TTL

    # Check cache size limit
    if len(_cache_store) >= config["max_cache_size"]:
        # Remove oldest entry
        oldest_key = min(_cache_store.keys(),
                        key=lambda k: _cache_store[k]["last_accessed"])
        del _cache_store[oldest_key]
        logger.info(f"Cache limit reached, removed oldest: {oldest_key}")

    # Store in cache
    _cache_store[cache_key] = {
        "data": data,
        "created_at": time.time(),
        "expires_at": time.time() + ttl,
        "last_accessed": time.time(),
        "hit_count": 0,
        "ttl": ttl,
        "tokens_saved": tokens_used,
        "cost_saved_usd": cost_usd,
        "cost_saved_inr": cost_usd * 83.0  # USD to INR conversion
    }

    logger.info(f"Cached result: {cache_key} (TTL: {ttl}s)")
    return True


def clear_cache(pattern: Optional[str] = None) -> int:
    """
    Clear cache entries matching pattern or all
    """
    if pattern:
        keys_to_remove = [k for k in _cache_store.keys() if pattern in k]
        for key in keys_to_remove:
            del _cache_store[key]
        logger.info(f"Cleared {len(keys_to_remove)} cache entries matching '{pattern}'")
        return len(keys_to_remove)
    else:
        count = len(_cache_store)
        _cache_store.clear()
        logger.info(f"Cleared all {count} cache entries")
        return count


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics for monitoring
    """
    total_hits = sum(item["hit_count"] for item in _cache_store.values())
    total_tokens_saved = sum(item.get("tokens_saved", 0) for item in _cache_store.values())
    total_cost_saved_usd = sum(item.get("cost_saved_usd", 0) for item in _cache_store.values())

    return {
        "enabled": get_cache_config()["enable_caching"],
        "total_entries": len(_cache_store),
        "total_hits": total_hits,
        "total_tokens_saved": total_tokens_saved,
        "total_cost_saved_usd": round(total_cost_saved_usd, 4),
        "total_cost_saved_inr": round(total_cost_saved_usd * 83.0, 2),
        "cache_size_bytes": sum(len(json.dumps(item["data"])) for item in _cache_store.values()),
        "oldest_entry": min((item["created_at"] for item in _cache_store.values()), default=0),
        "newest_entry": max((item["created_at"] for item in _cache_store.values()), default=0)
    }


def should_bypass_cache(request_params: Dict[str, Any]) -> bool:
    """
    Check if cache should be bypassed based on request parameters
    """
    # Allow force refresh via parameter
    if request_params.get("fresh") or request_params.get("no_cache"):
        logger.info("Cache bypass requested via parameter")
        return True

    # Check if caching is disabled
    if not get_cache_config()["enable_caching"]:
        logger.info("Cache disabled globally")
        return True

    return False