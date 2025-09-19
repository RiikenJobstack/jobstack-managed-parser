import json
import os
import re
import asyncio
import time
from typing import Dict, Any, Optional
import google.generativeai as genai
from src.config.static_prompt import STATIC_RESUME_PARSER_PROMPT
from .token_utils import count_tokens, calculate_cost


# Global model for efficiency
_gemini_model = None


def get_gemini_model():
    """Lazy loading of Gemini model"""
    global _gemini_model
    if not _gemini_model:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")

        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel('gemini-2.5-flash-lite')

    return _gemini_model


async def normalize_with_gemini(raw_text: str) -> Dict[str, Any]:
    """
    Convert raw extracted text to structured resume format
    Matches static_prompt.py structure exactly
    """

    if not raw_text or len(raw_text.strip()) < 20:
        raise ValueError("Insufficient text for normalization")

    try:
        start_time = time.time()
        model = get_gemini_model()
        prompt = create_normalization_prompt(raw_text)

        # Count input tokens
        input_tokens = count_tokens(prompt, "gemini-2.5-flash-lite")

        print(f"Sending {len(raw_text)} characters to Gemini for normalization...")

        # Use async generation
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config={
                "temperature": 0.1,
                "top_p": 0.8,
                "max_output_tokens": 4096,
            }
        )

        # Count output tokens
        output_tokens = count_tokens(response.text, "gemini-2.5-flash-lite")

        # Calculate cost (non-cached)
        cost_details = calculate_cost(input_tokens, output_tokens, cached=False)

        # Parse JSON response
        structured_data = parse_json_response(response.text)

        # Validate and clean the structure with token info
        validated_data = validate_resume_structure(
            structured_data,
            input_tokens,
            output_tokens,
            cost_details,
            time.time() - start_time
        )

        print(f"Gemini normalization completed successfully")
        return validated_data

    except Exception as e:
        print(f"Gemini normalization failed: {str(e)}")
        # Return fallback structure with basic extraction
        return create_fallback_structure(raw_text)


def create_normalization_prompt(raw_text: str) -> str:
    """
    Create prompt using the existing static_prompt.py structure
    """

    prompt = f"""{STATIC_RESUME_PARSER_PROMPT}

RESUME TEXT TO PARSE:
{raw_text[:4000]}

Return only the JSON structure:"""

    return prompt


def parse_json_response(response_text: str) -> Dict[str, Any]:
    """
    Parse JSON from Gemini response with error handling
    """

    try:
        # Clean the response
        response_text = response_text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        # Try to parse JSON
        data = json.loads(response_text)
        return data

    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {str(e)}")
        print(f"Response text: {response_text[:500]}...")

        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        raise ValueError(f"Could not parse JSON response from Gemini: {str(e)}")


def validate_resume_structure(
    data: Dict[str, Any],
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_details: Dict[str, Any] = None,
    processing_time: float = 0.0
) -> Dict[str, Any]:
    """
    Validate and ensure proper structure matching static_prompt.py format
    Returns complete structure with both content and parseMetadata
    """

    # If Gemini returns the full structure, use it
    if "success" in data and "data" in data:
        # Add token and cost info to existing structure
        if "parseMetadata" in data["data"]:
            data["data"]["parseMetadata"]["tokens"] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            }
            if cost_details:
                data["data"]["parseMetadata"]["cost"] = cost_details
            data["data"]["parseMetadata"]["parseTime"] = processing_time
        return data

    # If Gemini returns just the content, wrap it in the full structure
    content_data = data
    if "data" in data and "content" in data["data"]:
        content_data = data["data"]["content"]
    elif "content" in data:
        content_data = data["content"]

    # Build metadata with token and cost info
    metadata = {
        "confidence": 0.85,
        "parseTime": processing_time,
        "detectedSections": get_detected_sections(content_data),
        "missingSections": [],
        "sectionConfidence": {
            "personalInfo": 0.9,
            "experience": 0.8,
            "education": 0.8,
            "skills": 0.7,
            "projects": 0.6
        },
        "warnings": [],
        "suggestions": [],
        "extractedKeywords": [],
        "industryDetected": "",
        "experienceLevel": "Mid",
        "totalExperienceYears": None,
        "educationLevel": "Bachelor's",
        "tokens": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        },
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

    # Add cost details if available
    if cost_details:
        metadata["cost"] = cost_details

    return {
        "success": True,
        "data": {
            "content": content_data,
            "parseMetadata": metadata
        }
    }


def get_detected_sections(content_data: Dict[str, Any]) -> list:
    """Detect which sections have actual content"""
    detected = []

    if content_data.get("personalInfo"):
        detected.append("personalInfo")
    if content_data.get("summary", {}).get("content"):
        detected.append("summary")
    if content_data.get("experience") and len(content_data["experience"]) > 0:
        detected.append("experience")
    if content_data.get("education") and len(content_data["education"]) > 0:
        detected.append("education")
    if content_data.get("skills", {}).get("extracted") and len(content_data["skills"]["extracted"]) > 0:
        detected.append("skills")
    if content_data.get("projects") and len(content_data["projects"]) > 0:
        detected.append("projects")
    if content_data.get("certifications") and len(content_data["certifications"]) > 0:
        detected.append("certifications")

    return detected


def create_fallback_structure(raw_text: str) -> Dict[str, Any]:
    """
    Create fallback structure matching static_prompt.py format when Gemini fails
    """

    print("Creating fallback structure with regex extraction...")

    # Basic regex patterns
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    phone_pattern = r'[\+]?[1-9]?[0-9]{7,14}'
    linkedin_pattern = r'linkedin\.com/in/[\w-]+'
    github_pattern = r'github\.com/[\w-]+'

    # Extract basic info
    email_match = re.search(email_pattern, raw_text, re.IGNORECASE)
    phone_match = re.search(phone_pattern, raw_text)
    linkedin_match = re.search(linkedin_pattern, raw_text, re.IGNORECASE)
    github_match = re.search(github_pattern, raw_text, re.IGNORECASE)

    # Try to extract name (first line or common patterns)
    lines = raw_text.split('\n')
    name = ""
    for line in lines[:5]:  # Check first 5 lines
        line = line.strip()
        if len(line) > 2 and len(line) < 50 and ' ' in line:
            # Simple heuristic: contains letters and space, reasonable length
            if re.match(r'^[A-Za-z\s\.]+$', line):
                name = line
                break

    # Return full structure matching static_prompt.py format
    content_data = {
        "personalInfo": {
            "fullName": name,
            "title": "",
            "email": email_match.group() if email_match else "",
            "phone": phone_match.group() if phone_match else "",
            "location": "",
            "linkedIn": linkedin_match.group() if linkedin_match else "",
            "portfolio": "",
            "github": github_match.group() if github_match else "",
            "customLinks": []
        },
        "summary": {
            "content": raw_text[:500] if raw_text else ""
        },
        "experience": [],
        "education": [],
        "skills": {
            "extracted": []
        }
    }

    return {
        "success": True,
        "data": {
            "content": content_data,
            "parseMetadata": {
                "confidence": 0.3,  # Low confidence for fallback
                "parseTime": 0.0,
                "detectedSections": get_detected_sections(content_data),
                "missingSections": ["experience", "education", "skills"],
                "sectionConfidence": {
                    "personalInfo": 0.5,
                    "experience": 0.0,
                    "education": 0.0,
                    "skills": 0.0,
                    "projects": 0.0
                },
                "warnings": [
                    {
                        "type": "low_confidence",
                        "message": "Fallback parsing used due to AI processing failure",
                        "section": "all",
                        "field": "",
                        "severity": "high"
                    }
                ],
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
                    "totalWords": len(raw_text.split()) if raw_text else 0,
                    "bulletPoints": 0,
                    "quantifiedAchievements": 0,
                    "actionVerbs": 0,
                    "uniqueSkills": 0
                }
            }
        }
    }


def extract_urls_from_text(text: str) -> Dict[str, str]:
    """
    Extract various URLs from text with improved patterns
    """

    urls = {
        "linkedin": "",
        "github": "",
        "portfolio": ""
    }

    # LinkedIn patterns
    linkedin_patterns = [
        r'linkedin\.com/in/[\w-]+',
        r'www\.linkedin\.com/in/[\w-]+',
        r'https?://(?:www\.)?linkedin\.com/in/[\w-]+'
    ]

    # GitHub patterns
    github_patterns = [
        r'github\.com/[\w-]+',
        r'www\.github\.com/[\w-]+',
        r'https?://(?:www\.)?github\.com/[\w-]+'
    ]

    # Portfolio patterns (common domains)
    portfolio_patterns = [
        r'https?://[\w.-]+\.(?:com|net|org|io|dev|me|portfolio)',
        r'[\w-]+\.(?:herokuapp|vercel|netlify|github\.io)'
    ]

    # Extract LinkedIn
    for pattern in linkedin_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            urls["linkedin"] = match.group()
            break

    # Extract GitHub
    for pattern in github_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            urls["github"] = match.group()
            break

    # Extract Portfolio
    for pattern in portfolio_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Skip LinkedIn and GitHub URLs
            url = match.group()
            if 'linkedin.com' not in url.lower() and 'github.com' not in url.lower():
                urls["portfolio"] = url
                break

    return urls