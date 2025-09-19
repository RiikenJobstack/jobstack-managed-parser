"""
Configuration management for managed services.
Handles environment variables and service configurations.
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ServiceEndpoints:
    """Service endpoint configurations"""
    aws_textract_region: str = "us-east-1"
    google_documentai_location: str = "us"
    azure_form_recognizer_api_version: str = "2022-08-31"

@dataclass
class BudgetLimits:
    """Budget and cost control settings"""
    monthly_budget_inr: float = 3000.0
    warning_threshold_percent: float = 80.0
    hard_limit_percent: float = 100.0
    cost_per_request_limit_inr: float = 50.0

class ManagedServicesConfig:
    """Central configuration for managed services"""

    def __init__(self):
        self.endpoints = ServiceEndpoints()
        self.budget = BudgetLimits()
        self._validate_environment()

    def get_aws_config(self) -> Dict[str, Any]:
        """Get AWS Textract configuration"""
        return {
            "region": os.getenv("AWS_REGION", self.endpoints.aws_textract_region),
            "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
            "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY")
        }

    def get_google_config(self) -> Dict[str, Any]:
        """Get Google Document AI configuration"""
        return {
            "project_id": os.getenv("GOOGLE_PROJECT_ID"),
            "location": os.getenv("GOOGLE_DOCUMENTAI_LOCATION", self.endpoints.google_documentai_location),
            "processor_id": os.getenv("GOOGLE_DOCUMENTAI_PROCESSOR_ID"),
            "credentials_path": os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        }

    def get_azure_config(self) -> Dict[str, Any]:
        """Get Azure Form Recognizer configuration"""
        return {
            "endpoint": os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT"),
            "api_key": os.getenv("AZURE_FORM_RECOGNIZER_API_KEY"),
            "api_version": os.getenv("AZURE_FORM_RECOGNIZER_API_VERSION",
                                   self.endpoints.azure_form_recognizer_api_version)
        }

    def get_gemini_config(self) -> Dict[str, Any]:
        """Get Gemini AI configuration"""
        return {
            "api_key": os.getenv("GEMINI_API_KEY"),
            "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.1")),
            "max_output_tokens": int(os.getenv("GEMINI_MAX_TOKENS", "8192"))
        }

    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get all service configurations"""
        return {
            "aws": self.get_aws_config(),
            "google": self.get_google_config(),
            "azure": self.get_azure_config(),
            "gemini": self.get_gemini_config(),
            "budget": {
                "monthly_budget": self.budget.monthly_budget_inr,
                "warning_threshold": self.budget.warning_threshold_percent,
                "hard_limit": self.budget.hard_limit_percent,
                "cost_per_request_limit": self.budget.cost_per_request_limit_inr
            }
        }

    def _validate_environment(self):
        """Validate required environment variables"""
        required_vars = [
            "GEMINI_API_KEY"  # Gemini is required as fallback
        ]

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def is_service_configured(self, service: str) -> bool:
        """Check if a specific service is properly configured"""
        if service.lower() == "aws" or service.lower() == "textract":
            config = self.get_aws_config()
            return bool(config["access_key_id"] and config["secret_access_key"])

        elif service.lower() == "google" or service.lower() == "documentai":
            config = self.get_google_config()
            return bool(config["project_id"] and config["processor_id"])

        elif service.lower() == "azure" or service.lower() == "forms":
            config = self.get_azure_config()
            return bool(config["endpoint"] and config["api_key"])

        elif service.lower() == "gemini":
            config = self.get_gemini_config()
            return bool(config["api_key"])

        return False

    def get_configured_services(self) -> list[str]:
        """Get list of properly configured services"""
        services = []

        if self.is_service_configured("aws"):
            services.append("aws_textract")

        if self.is_service_configured("google"):
            services.append("google_documentai")

        if self.is_service_configured("azure"):
            services.append("azure_form_recognizer")

        # Gemini is always required
        services.append("gemini_fallback")

        return services

# Global configuration instance
config = ManagedServicesConfig()