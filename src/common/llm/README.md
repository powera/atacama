# Common LLM Module

This module provides a high-level interface for working with various LLM providers (currently OpenAI) with support for structured outputs and telemetry.

## Features

- Type-safe schema definitions for LLM inputs and outputs
- Support for both text and structured (JSON) responses
- Built-in telemetry for token usage and cost tracking
- Consistent interface across different LLM providers

## Installation

Make sure you have the required dependencies installed:

```bash
pip install requests
```

## Usage

### 1. Import the Required Modules

```python
from common.llm.types import Schema, SchemaProperty
from common.llm.openai_client import generate_chat
```

### 2. Define a Schema (Optional)

Create a schema to define the structure of the output you expect from the LLM:

```python
# Define a schema for a person
person_schema = Schema(
    "Person",
    "Information about a person",
    {
        "name": SchemaProperty("string", "The person's full name"),
        "age": SchemaProperty("integer", "The person's age", minimum=0, maximum=120),
        "email": SchemaProperty("string", "Email address", required=False),
        "interests": SchemaProperty(
            "array", 
            "List of interests", 
            items={"type": "string"},
            required=False
        ),
        "address": SchemaProperty(
            "object",
            "Home address",
            properties={
                "street": SchemaProperty("string", "Street address"),
                "city": SchemaProperty("string", "City name"),
                "postal_code": SchemaProperty("string", "Postal code")
            },
            required=False
        )
    }
)
```

### 3. Make API Calls

#### Text Response (No Schema)

```python
response = generate_chat(
    prompt="Tell me a joke about programming",
    model="gpt-4.1-mini-2025-04-14",
    brief=True,  # Limits response length
    context="You are a helpful assistant that tells clean, appropriate jokes.")

print(f"Response: {response.response_text}")
print(f"Tokens used: {response.usage.total_tokens}")
print(f"Estimated cost: ${response.usage.cost:.6f}")
```

#### Structured Response (With Schema)

```python
response = generate_chat(
    prompt="Extract information about John Doe, a 30-year-old who loves Python and hiking.",
    json_schema=person_schema,
    model="gpt-4.1-mini-2025-04-14",
    context="Extract the information accurately from the given text. If a field isn't mentioned, leave it empty.")

# Access the structured data
person = response.structured_data
print(f"Name: {person['name']}")
print(f"Age: {person['age']}")
print(f"Interests: {', '.join(person.get('interests', []))}")

# Access usage information
print(f"Prompt tokens: {response.usage.tokens_in}")
print(f"Completion tokens: {response.usage.tokens_out}")
print(f"Total cost: ${response.usage.cost:.6f}")
```

### 4. Using Context

You can provide additional context to guide the model's response:

```python
context = """You are a helpful assistant that specializes in analyzing programming code.
Provide clear, concise explanations and include code examples when relevant."""

response = generate_chat(
    prompt="Explain how Python's list comprehensions work",
    context=context,
    model="gpt-4.1-mini-2025-04-14"
)

print(response.response_text)
```

## Response Object

The `generate_chat` function returns a `Response` object with the following attributes:

- `response_text`: The raw text response from the model (empty for JSON responses)
- `structured_data`: The parsed JSON response as a dictionary (empty for text responses)
- `usage`: An `LLMUsage` object containing token usage and cost information
  - `tokens_in`: Number of tokens in the prompt
  - `tokens_out`: Number of tokens in the completion
  - `cost`: Estimated cost in USD
  - `total_msec`: Total request duration in milliseconds

## Error Handling

The client will raise exceptions for HTTP errors or invalid responses. Always wrap API calls in try/except blocks:

```python
try:
    response = generate_chat("Your prompt here")
    # Process response...
except Exception as e:
    print(f"Error: {str(e)}")
```

## Configuration

Set the following environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `LLM_DEBUG`: Set to `1` to enable debug logging

## Best Practices

1. Always define schemas for structured data to ensure consistent output
2. Use the `brief` parameter for shorter responses when possible to reduce costs
3. Cache responses when appropriate to minimize API calls
4. Monitor usage and costs using the `LLMUsage` object
5. Handle rate limiting and retries in your application code
