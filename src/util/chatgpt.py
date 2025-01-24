"""Functions for analyzing email content using LLM models."""

from typing import Tuple, Optional
from sqlalchemy.orm import Session

from common.database import db
from common.models import Email
from common.messages import get_message_by_id
import common.openai_client
from common.telemetry import LLMUsage

def analyze_email(email_id: int, model: str = "gpt-4o-2024-11-20") -> Tuple[str, LLMUsage]:
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
1. A brief summary of the main content
2. Key topics or themes discussed
3. Any notable writing style characteristics
4. Important references or links mentioned
5. Overall tone and purpose of the message"""

    prompt = f"""Analyze this email message:

Subject: {message.subject}

{message.content}"""

    # Request analysis from the model
    response, _, usage = common.openai_client.generate_chat(
        prompt=prompt,
        model=model,
        context=context
    )
    
    return response.strip(), usage
