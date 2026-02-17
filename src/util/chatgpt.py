"""Functions for analyzing email content using LLM models."""

from typing import Tuple

from models.messages import get_message_by_id
from common.llm import openai_client
from common.llm.telemetry import LLMUsage


def analyze_email(email_id: int, model: str = "gpt-4o-mini-2024-07-18") -> Tuple[str, LLMUsage]:
    """
    Retrieve and analyze an email using the specified LLM model.

    Args:
        email_id: ID of the email to analyze
        model: Model identifier to use for analysis

    Returns:
        Tuple containing (analysis_text, usage_metrics)

    Raises:
        ValueError: If email not found or inaccessible
    """
    # Get the email using existing message access control
    message = get_message_by_id(email_id)
    if not message:
        raise ValueError(f"Email with ID {email_id} not found or not accessible")

    # Set up analysis prompting
    context = """You are analyzing an email message. Please provide:
1. A one-paragraph summary of the main content
2. Key topics or themes discussed
3. Cultural references that may not be understood by all readers
4. Confusing or vague topics
5. Material that might not be suitable for publication, due to its tone or subject

There are "color" tags with the following meanings:
Xantham / 🔥 / Sarcastic or overconfident tone
Red / 💡 / Forceful and certain statements
Orange / ⚔️ / Counterpoint or contrasting perspective
Yellow/Quote / 💬 / Direct quotations
Green / ⚙️ / Technical explanations
Teal / 🤖 / Artificial Intelligence or computational output
Blue / ✨ / "Voice from beyond" or ethereal commentary
Violet / 📣 / Serious, authoritative tone
Music / 🎵 / Musical references or lyrical content
Mogue / 🌎 / Actions taken or global perspectives
Gray / 💭 / Past stories or reflective content
Hazel / 🎭 / Storytelling and narrative content
"""

    prompt = f"""Analyze this message:

Subject: {message.subject}

{message.content}"""

    # Request analysis from the model
    response = openai_client.generate_chat(prompt=prompt, model=model, context=context)

    return response.response_text.strip(), response.usage
