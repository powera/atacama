#!/usr/bin/python3
"""Client for interacting with OpenAI Responses API using direct HTTP requests."""

import json
import logging
import os
import time
from typing import Dict, Optional, Any, Tuple

import requests
import tiktoken

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
    """Client for making direct HTTP requests to OpenAI Responses API."""
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, debug: bool = False):
        """Initialize OpenAI client with API key."""
        self.timeout = timeout
        self.debug = debug
        # Check for HTTP debug environment variable
        self.http_debug = os.getenv('ATACAMA_HTTP_DEBUG') == '1'
        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Initialized OpenAIClient in debug mode")
        if self.http_debug:
            logger.info("HTTP debug logging enabled for OpenAI API requests")
        self.api_key = self._load_key()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def _load_key(self) -> str:
        """Load OpenAI API key from file."""
        key_path = os.path.join(constants.KEY_DIR, "openai.key")
        with open(key_path) as f:
            return f.read().strip()

    def _truncate_for_logging(self, content: str, max_bytes: int = 512) -> str:
        """Truncate content for logging while preserving UTF-8 encoding."""
        if not content:
            return content
            
        original_length = len(content)
        content_bytes = content.encode('utf-8')
        
        if len(content_bytes) <= max_bytes:
            return content
            
        # Truncate at byte boundary and decode back to string
        truncated_bytes = content_bytes[:max_bytes]
        
        # Handle potential UTF-8 character boundary issues
        try:
            truncated_content = truncated_bytes.decode('utf-8')
        except UnicodeDecodeError:
            # If we cut in the middle of a UTF-8 character, back up until we find a valid boundary
            for i in range(1, 5):  # UTF-8 characters are at most 4 bytes
                try:
                    truncated_content = truncated_bytes[:-i].decode('utf-8')
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Fallback: just use the first max_bytes-4 bytes to be safe
                truncated_content = truncated_bytes[:-4].decode('utf-8', errors='ignore')
        
        return f"{truncated_content}... [truncated from {original_length} chars]"

    @measure_completion
    def _create_response(self, **kwargs) -> Dict:
        """Make direct HTTP request to OpenAI responses endpoint."""
        url = f"{API_BASE}/responses"
        
        if self.debug:
            logger.debug("Making request to %s", url)
            logger.debug("Request data: %s", json.dumps(kwargs, indent=2))
        
        # HTTP debug logging
        if self.http_debug:
            logger.info("=" * 80)
            logger.info("HTTP REQUEST TO OPENAI API")
            logger.info("=" * 80)
            logger.info("URL: %s", url)
            logger.info("Method: POST")
            
            # Log headers (redact Authorization)
            debug_headers = self.headers.copy()
            if 'Authorization' in debug_headers:
                debug_headers['Authorization'] = '[REDACTED]'
            logger.info("Headers: %s", json.dumps(debug_headers, indent=2))
            
            # Log request body (truncated)
            request_body = json.dumps(kwargs, indent=2)
            truncated_request = self._truncate_for_logging(request_body)
            logger.info("Request Body: %s", truncated_request)
            
        response = requests.post(
            url,
            headers=self.headers,
            json=kwargs,
            timeout=self.timeout
        )
        
        # HTTP debug logging for response
        if self.http_debug:
            logger.info("-" * 80)
            logger.info("HTTP RESPONSE FROM OPENAI API")
            logger.info("-" * 80)
            logger.info("Status Code: %d", response.status_code)
            logger.info("Response Headers: %s", dict(response.headers))
            
            # Log response body (truncated)
            response_text = response.text
            truncated_response = self._truncate_for_logging(response_text)
            logger.info("Response Body: %s", truncated_response)
            logger.info("=" * 80)
        
        if response.status_code != 200:
            error_msg = f"Error {response.status_code}: {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        return response.json()

    def warm_model(self, model: str) -> bool:
        """Simulate model warmup (not needed for OpenAI but kept for API compatibility)."""
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
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None
    ) -> Response:
        """
        Generate chat response using OpenAI Responses API.
        
        Args:
            prompt: The main prompt/question
            model: Model to use for generation
            brief: Whether to limit response length
            json_schema: Schema for structured response (if provided, returns JSON)
            context: Optional context to include before the prompt
            max_tokens: Maximum number of tokens to generate (overrides brief setting)
            reasoning_effort: Reasoning effort level for reasoning models ('minimal', 'low', 'medium', 'high', or None to disable)
        
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
        
        # Determine which token limit parameter to use based on model
        # Newer reasoning models (o1, gpt-5, o3) require max_output_tokens
        reasoning_models = ['o1-', 'gpt-5-', 'o3-']
        uses_output_tokens = any(model.startswith(prefix) for prefix in reasoning_models)
        
        # gpt-5 models don't support custom temperature (only default value of 1)
        is_gpt5_model = model.startswith('gpt-5-')
        is_gpt5_nano_or_mini = model.startswith('gpt-5-nano') or model.startswith('gpt-5-mini')
        
        # Determine token limit: max_tokens takes precedence, then brief flag, then default
        if max_tokens is not None:
            token_limit = max_tokens
        else:
            token_limit = 512 if brief else 4096
        kwargs: Dict[str, Any] = {
            "model": model,
            "input": prompt,
        }
        
        # Add instructions (system message) if context provided
        if context:
            kwargs["instructions"] = context
        
        # Only set temperature for models that support it
        if not is_gpt5_model:
            kwargs["temperature"] = 0.35
        
        # Set token limit parameter
        if uses_output_tokens:
            kwargs["max_output_tokens"] = token_limit
        else:
            # For non-reasoning models, we still use max_output_tokens in Responses API
            kwargs["max_output_tokens"] = token_limit
        
        # Set reasoning and text parameters for gpt-5-nano and gpt-5-mini
        if is_gpt5_nano_or_mini:
            # Set reasoning effort based on parameter, default to "minimal" if not specified
            if reasoning_effort is not None:
                if reasoning_effort.lower() in ['minimal', 'low', 'medium', 'high']:
                    kwargs["reasoning"] = {"effort": reasoning_effort.lower()}
                # If reasoning_effort is explicitly set to something else (like "none" or "disable"), don't set reasoning
            else:
                # Default behavior: use minimal reasoning
                kwargs["reasoning"] = {"effort": "minimal"}
            
            # Only set text verbosity if not overridden by JSON schema below
            if not json_schema:
                kwargs["text"] = {"verbosity": "low"}
        
        # If JSON schema provided, configure for structured response
        if json_schema:
            if isinstance(json_schema, Schema):
                schema_obj = json_schema
            else:
                schema_obj = schema_from_dict(json_schema)
            
            clean_schema = to_openai_schema(schema_obj)
            
            # Lower temperature for structured output (only for models that support it)
            if not is_gpt5_model:
                kwargs["temperature"] = 0.15
            
            # Use text.format for structured outputs in Responses API
            text_config: Dict[str, Any] = {
                "format": {
                    "type": "json_schema",
                    "name": "Details",
                    "description": "N/A",
                    "strict": True,
                    "schema": clean_schema
                }
            }
            
            # For gpt-5-nano and gpt-5-mini, also include verbosity
            if is_gpt5_nano_or_mini:
                text_config["verbosity"] = "low"
            
            kwargs["text"] = text_config
        
        response_data, duration_ms = self._create_response(**kwargs)
        
        # Extract response content from Responses API structure
        response_content = ""
        if response_data.get("output"):
            # Look for the message output item (skip reasoning items)
            # GPT-5 models with reasoning may have both "reasoning" and "message" output items
            for output_item in response_data["output"]:
                if output_item.get("type") == "message" and output_item.get("content"):
                    for content_item in output_item["content"]:
                        if content_item.get("type") == "output_text":
                            response_content = content_item.get("text", "")
                            break
                    if response_content:
                        break
            
            # If no message content found, log the response structure for debugging
            if not response_content:
                logger.warning("No message content found in response. Available output types: %s", 
                             [item.get("type") for item in response_data.get("output", [])])
                if self.debug:
                    logger.debug("Full output structure: %s", 
                               json.dumps(response_data.get("output", []), indent=2))
        
        if self.debug:
            logger.debug("Response content: %s", response_content)

        # Calculate token usage
        usage_data = response_data.get("usage", {})
        usage = LLMUsage.from_api_response(
            {
                "prompt_tokens": usage_data.get("input_tokens", 0),
                "completion_tokens": usage_data.get("output_tokens", 0),
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

# Lazy client initialization to avoid errors at import time
_client = None

def _get_client() -> OpenAIClient:
    """Get or create the default client instance (lazy initialization)."""
    global _client
    if _client is None:
        _client = OpenAIClient(debug=False)  # Set to True to enable debug logging
    return _client

# Expose key functions at module level for API compatibility
def warm_model(model: str) -> bool:
    return _get_client().warm_model(model)

def generate_chat(
    prompt: str,
    model: str = DEFAULT_MODEL,
    brief: bool = False,
    json_schema: Optional[Any] = None,
    context: Optional[str] = None,
    max_tokens: Optional[int] = None,
    reasoning_effort: Optional[str] = None
) -> Response:
    """
    Generate a chat response using OpenAI Responses API.

    Returns:
        Response containing response_text, structured_data, and usage
        For text responses, structured_data will be empty dict
        For JSON responses, response_text will be empty string
    """
    return _get_client().generate_chat(prompt, model, brief, json_schema, context, max_tokens, reasoning_effort)
