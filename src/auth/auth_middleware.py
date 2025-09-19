from fastapi import HTTPException, Request
from typing import Dict, Any, Optional
import logging
from .token_service import verify_token, get_auth_user_id
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

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

async def extract_and_verify_token(request: Request) -> Dict[str, Any]:
    """
    Extract and verify JWT token from Authorization header

    Args:
        request: FastAPI request object

    Returns:
        Dict[str, Any]: Decoded token payload with user info

    Raises:
        HTTPException: If authentication fails
    """

    # Check Authorization header
    auth_header = request.headers.get("authorization")
    if not auth_header:
        logger.warning("Missing Authorization header")
        raise HTTPException(
            status_code=400,
            detail={"error": "Authorization header is missing", "status": 400}
        )

    # Extract token from Bearer format
    try:
        token = auth_header.split(" ")[1]
    except IndexError:
        logger.warning("Invalid Authorization header format")
        raise HTTPException(
            status_code=400,
            detail={"error": "Bearer token missing", "status": 400}
        )

    # Verify token
    try:
        decoded_token = await verify_token(token)
        user_id = get_auth_user_id(decoded_token)

        # Return enhanced payload with user info
        return {
            "userId": user_id,
            "decoded_token": decoded_token,
            "is_authenticated": True
        }

    except Exception as err:
        logger.warning(f"Token verification failed: {str(err)}")
        raise HTTPException(
            status_code=401,
            detail={"error": str(err), "status": 401}
        )


def require_auth(allow_anonymous: bool = False):
    """
    Decorator factory for endpoints that require authentication

    Args:
        allow_anonymous: If True, allows unauthenticated access but still extracts user info if token is present

    Returns:
        Function that extracts user authentication info
    """

    async def auth_dependency(request: Request) -> Optional[Dict[str, Any]]:
        """
        FastAPI dependency that extracts and validates authentication

        Returns:
            Dict with user info if authenticated, None if anonymous allowed and no token
        """

        if allow_anonymous:
            # Try to extract token but don't fail if missing
            auth_header = request.headers.get("authorization")
            if not auth_header:
                return None

            try:
                return await extract_and_verify_token(request)
            except HTTPException:
                return None
        else:
            # Require valid authentication
            return await extract_and_verify_token(request)

    return auth_dependency


async def extract_and_verify_origin(request: Request, allowed_origins: list) -> Dict[str, Any]:
    """
    Extract and verify Origin header against allowed origins

    Args:
        request: FastAPI request object
        allowed_origins: List of allowed origin URLs

    Returns:
        Dict[str, Any]: Origin validation info

    Raises:
        HTTPException: If origin validation fails
    """

    # Check Origin header
    origin_header = request.headers.get("origin")
    if not origin_header:
        logger.warning("Missing Origin header")
        raise HTTPException(
            status_code=403,
            detail={"error": "Origin header is missing", "status": 403}
        )

    # Normalize origin (remove trailing slash)
    normalized_origin = origin_header.rstrip('/')
    normalized_allowed = [origin.rstrip('/') for origin in allowed_origins]

    # Check if origin is allowed
    if normalized_origin not in normalized_allowed:
        logger.warning(f"Origin not allowed: {origin_header}")
        raise HTTPException(
            status_code=403,
            detail={
                "error": f"Origin '{origin_header}' is not allowed",
                "allowed_origins": allowed_origins,
                "status": 403
            }
        )

    return {
        "origin": origin_header,
        "normalized_origin": normalized_origin,
        "is_origin_valid": True
    }


def require_origin(allowed_origins: list = None, allow_no_origin: bool = False):
    """
    Decorator factory for endpoints that require origin validation

    Args:
        allowed_origins: List of allowed origin URLs. If None, uses default from get_cors_origins()
        allow_no_origin: If True, allows requests without Origin header

    Returns:
        Function that extracts origin validation info
    """

    # Import here to avoid circular import

    if allowed_origins is None:
        allowed_origins = get_smart_cors_origins()

    async def origin_dependency(request: Request) -> Optional[Dict[str, Any]]:
        """
        FastAPI dependency that extracts and validates origin

        Returns:
            Dict with origin info if valid, None if no origin allowed and no origin header
        """

        if allow_no_origin:
            # Try to extract origin but don't fail if missing
            origin_header = request.headers.get("origin")
            if not origin_header:
                return {
                    "origin": None,
                    "normalized_origin": None,
                    "is_origin_valid": True
                }

            try:
                return await extract_and_verify_origin(request, allowed_origins)
            except HTTPException:
                return {
                    "origin": origin_header,
                    "normalized_origin": origin_header.rstrip('/'),
                    "is_origin_valid": False
                }
        else:
            # Require valid origin
            return await extract_and_verify_origin(request, allowed_origins)

    return origin_dependency


# Common dependency instances
require_authentication = require_auth(allow_anonymous=False)
optional_authentication = require_auth(allow_anonymous=True)
require_valid_origin = require_origin(allow_no_origin=False)
optional_origin_validation = require_origin(allow_no_origin=True)