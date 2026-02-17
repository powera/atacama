"""Pytest configuration for all tests."""

import sys
from unittest.mock import MagicMock

# Mock tiktoken before any imports to avoid network calls
sys.modules["tiktoken"] = MagicMock()


# Mock the OpenAI client to avoid initialization issues
def mock_openai_client():
    """Mock the OpenAI client module to prevent initialization errors."""
    mock_client = MagicMock()
    mock_client.OpenAIClient = MagicMock
    return mock_client


# This will prevent the OpenAI client from initializing during import
sys.modules["common.llm.openai_client"] = mock_openai_client()
