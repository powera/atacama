"""LLM functionality for Atacama - OpenAI client and widget tools."""

# Core types
from .types import (
    SchemaProperty,
    Schema,
    Response
)

# OpenAI client
from .openai_client import (
    OpenAIClient,
    warm_model,
    generate_chat,
    TEST_MODEL,
    PROD_MODEL,
    DEFAULT_MODEL
)

# Schema conversion utilities
from .lib import (
    to_openai_schema,
    to_anthropic_schema,
    to_gemini_schema,
    to_ollama_schema,
    schema_from_dict
)

# Widget tools
from .widget_initiator import WidgetInitiator
from .widget_improver import WidgetImprover

__all__ = [
    # Types
    'SchemaProperty', 'Schema', 'Response',
    
    # OpenAI client
    'OpenAIClient', 'warm_model', 'generate_chat', 'TEST_MODEL', 'PROD_MODEL', 'DEFAULT_MODEL',
    
    # Schema utilities
    'to_openai_schema', 'to_anthropic_schema', 'to_gemini_schema', 'to_ollama_schema', 'schema_from_dict',
    
    # Widget tools
    'WidgetInitiator', 'WidgetImprover'
]