"""
Token counting and cost calculation utilities for Gemini API
"""
import os
import json
import requests
import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account
import logging

logger = logging.getLogger(__name__)

# Cache for credentials to avoid repeated loading
_credentials = None
_config = None

def get_credentials():
    """Get Google Cloud credentials for token counting"""
    global _credentials, _config

    if _credentials is None:
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_MANAGED")

        if not credentials_path or not os.path.exists(credentials_path):
            logger.warning("Google Cloud credentials not found for token counting")
            return None, None

        try:
            _credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )

            with open(credentials_path) as f:
                _config = json.load(f)

        except Exception as e:
            logger.error(f"Failed to load credentials for token counting: {str(e)}")
            return None, None

    return _credentials, _config


def count_tokens(text: str, model: str = "gemini-2.5-flash-lite") -> int:
    """
    Count tokens in the provided text using Vertex AI API
    Returns 0 if counting fails (fallback to estimation)
    """
    try:
        credentials, config = get_credentials()

        if not credentials or not config:
            # Fallback to estimation if credentials not available
            return estimate_tokens(text)

        # Get access token
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        access_token = credentials.token

        if not access_token:
            return estimate_tokens(text)

        # Use Vertex AI endpoint for token counting
        endpoint = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{config['project_id']}/locations/us-central1/publishers/google/models/{model}:countTokens"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        data = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": text}]
                }
            ]
        }

        response = requests.post(endpoint, headers=headers, json=data, timeout=10)

        if response.status_code == 200:
            result = response.json()
            token_count = result.get("totalTokens", 0)
            logger.info(f"Token count via API: {token_count}")
            return token_count
        else:
            logger.warning(f"Token counting API returned {response.status_code}, using estimation")
            return estimate_tokens(text)

    except Exception as e:
        logger.warning(f"Token counting failed: {str(e)}, using estimation")
        return estimate_tokens(text)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count (roughly 1 token per 4 characters)
    This is a fallback when API counting is not available
    """
    estimated = len(text) // 4
    logger.info(f"Estimated token count: {estimated}")
    return estimated


def calculate_cost(input_tokens: int, output_tokens: int, cached: bool = False) -> dict:
    """
    Calculate cost based on token usage

    Pricing for Gemini 2.5 Flash:
    - Input: $0.25 per 1M tokens
    - Output: $0.75 per 1M tokens

    With caching (89% reduction on input tokens):
    - Cached input: $0.0275 per 1M tokens (89% discount)
    - Output: $0.75 per 1M tokens (same)
    """

    # Base pricing per million tokens
    if cached:
        # 89% reduction on input token cost when using caching
        input_price_per_million = 0.25 * 0.11  # 11% of original cost
    else:
        input_price_per_million = 0.25

    output_price_per_million = 0.75

    # Calculate costs
    input_cost = (input_tokens / 1_000_000) * input_price_per_million
    output_cost = (output_tokens / 1_000_000) * output_price_per_million
    total_cost = input_cost + output_cost

    # Convert to USD cents for better readability
    USD_TO_INR = 83.0

    cost_details = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_cost, 6),
        "input_cost_inr": round(input_cost * USD_TO_INR, 6),
        "output_cost_inr": round(output_cost * USD_TO_INR, 6),
        "total_cost_inr": round(total_cost * USD_TO_INR, 6),
        "cached": cached,
        "savings_percentage": 89 if cached else 0
    }

    logger.info(f"Cost calculation: {cost_details}")

    return cost_details