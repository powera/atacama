#!/usr/bin/python3
"""Client for interacting with OpenAI API using direct HTTP requests."""

import json
import logging
import os
import time
from typing import Dict, Optional, Any, Tuple

import requests

import constants
from common.llm.telemetry import LLMUsage
from common.llm.types import Response, Schema
from common.llm.lib import schema_from_dict, to_openai_schema

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Model identifiers
TEST_MODEL = "gpt-5-nano"
PROD_MODEL = "gpt-5-mini"
DEFAULT_MODEL = TEST_MODEL
DEFAULT_TIMEOUT = 240
API_BASE = "https://api.openai.com/v1"

def measure_completion(func):
    """Decorator to measure completion API call duration."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration_ms = (time.time() - start_time) * 1000
        return result, duration_ms
    return wrapper

class OpenAIClient:
    """Client for making direct HTTP requests to OpenAI API."""
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, debug: bool = False):
        """Initialize OpenAI client with API key."""
        self.timeout = timeout
        self.debug = debug
        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Initialized OpenAIClient in debug mode")
        self.api_key = self._load_key()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        } if self.api_key else None

    def _load_key(self) -> Optional[str]:
        """Load OpenAI API key from file."""
        key_path = os.path.join(constants.KEY_DIR, "openai.key")
        try:
            with open(key_path) as f:
                return f.read().strip()
        except (FileNotFoundError, IOError) as e:
            logger.error("Failed to load OpenAI API key from %s: %s", key_path, str(e))
            return None

    def _check_api_key(self):
        """Check if API key is available and raise exception if not."""
        if not self.api_key:
            raise Exception("OpenAI API key not available. Please ensure the key file exists at the configured path.")

    @measure_completion
    def _create_completion(self, **kwargs) -> Dict:
        """Make direct HTTP request to OpenAI chat completions endpoint."""
        self._check_api_key()
        
        url = f"{API_BASE}/chat/completions"
        
        if self.debug:
            logger.debug("Making request to %s", url)
            logger.debug("Request data: %s", json.dumps(kwargs, indent=2))
            
        response = requests.post(
            url,
            headers=self.headers,
            json=kwargs,
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            error_msg = f"Error {response.status_code}: {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        return response.json()

    def warm_model(self, model: str) -> bool:
        """Simulate model warmup (not needed for OpenAI but kept for API compatibility)."""
        self._check_api_key()
        if self.debug:
            logger.debug("Model warmup not required for OpenAI: %s", model)
        return True

    def generate_chat(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        brief: bool = False,
        json_schema: Optional[Any] = None,
        context: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Response:
        """
        Generate chat completion using OpenAI API.
        
        Args:
            prompt: The main prompt/question
            model: Model to use for generation
            brief: Whether to limit response length
            json_schema: Schema for structured response (if provided, returns JSON)
            context: Optional context to include before the prompt
        
        Returns:
            Response containing response_text, structured_data, and usage
            For text responses, structured_data will be empty dict
            For JSON responses, response_text will be empty string
        """
        if self.debug:
            logger.debug("Generating chat response")
            logger.debug("Model: %s", model)
            logger.debug("Brief mode: %s", brief)
            logger.debug("Context: %s", context)
            logger.debug("JSON schema: %s", json_schema)
        else:
            logger.info("Generating chat response with model: %s", model)
        
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})
        
        # Set max_tokens with proper limits
        if not max_tokens:
            if brief:
                max_tokens = 512
            else:
                max_tokens = 2048

        logger.info("Using max_tokens: %d", max_tokens)
        
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.35,
        }
        
        # If JSON schema provided, configure for structured response
        if json_schema:
            if isinstance(json_schema, Schema):
                schema_obj = json_schema
            else:
                schema_obj = schema_from_dict(json_schema)
            
            clean_schema = to_openai_schema(schema_obj)
            
            kwargs["temperature"] = 0.15  # Lower temperature for structured output
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "Details",
                    "description": "N/A",
                    "strict": True,
                    "schema": clean_schema
                }
            }
        
        completion_data, duration_ms = self._create_completion(**kwargs)
        
        response_content = completion_data["choices"][0]["message"]["content"]
        if self.debug:
            logger.debug("Response content: %s", response_content)

        # Calculate token usage
        usage = LLMUsage.from_api_response(
            {
                "prompt_tokens": completion_data["usage"]["prompt_tokens"],
                "completion_tokens": completion_data["usage"]["completion_tokens"],
                "total_duration": duration_ms
            },
            model=model
        )
        
        # Parse JSON response if schema was provided
        if json_schema:
            try:
                structured_data = json.loads(response_content)
                response_text = ""
            except json.JSONDecodeError:
                error_msg = f"Failed to parse JSON response: {response_content}"
                logger.error(error_msg)
                structured_data = {"error": error_msg}
                response_text = ""
        else:
            response_text = response_content
            structured_data = {}
        
        if self.debug:
            if response_text:
                logger.debug("Response text: %s", response_text)
            elif structured_data:
                logger.debug("Structured data: %s", structured_data)
            else:
                logger.debug("No response text or structured data")
            logger.debug("Usage metrics: %s", usage.to_dict())
        
        return Response(
            response_text=response_text,
            structured_data=structured_data,
            usage=usage
        )

# Create default client instance
client = OpenAIClient(debug=False)  # Set to True to enable debug logging

# Expose key functions at module level for API compatibility
def warm_model(model: str) -> bool:
    return client.warm_model(model)

def generate_chat(
    prompt: str,
    model: str = DEFAULT_MODEL,
    brief: bool = False,
    json_schema: Optional[Any] = None,
    context: Optional[str] = None,
    max_tokens: Optional[int] = None
) -> Response:
    """
    Generate a chat response using OpenAI API.
    
    Returns:
        Response containing response_text, structured_data, and usage
        For text responses, structured_data will be empty dict
        For JSON responses, response_text will be empty string
    """
    return client.generate_chat(prompt, model, brief, json_schema, context,
                                max_tokens=max_tokens)
