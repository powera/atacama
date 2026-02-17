"""LLM-powered editor assistant for three-stage blog post composition.

This module provides the EditorAssistant class that helps users compose blog posts
by deciding whether to APPEND new content or MODIFY existing content based on
user input.
"""

from typing import Dict, Any, Optional

from common.base.logging_config import get_logger
from common.llm.openai_client import generate_chat
from common.llm.types import Schema, SchemaProperty

logger = get_logger(__name__)

DEFAULT_MODEL = "gpt-5-nano"

# AML formatting reference for the LLM
AML_FORMATTING_GUIDE = """
ATACAMA MARKUP LANGUAGE (AML) FORMATTING GUIDE:

*** IMPORTANT: THIS IS NOT HTML. THERE ARE NO CLOSING TAGS. ***
*** NEVER WRITE </green>, </red>, </orange>, </quote>, etc. ***
*** CLOSING TAGS DO NOT EXIST IN AML AND WILL BREAK RENDERING. ***

1. COLOR TAGS (semantic meaning):
   - <xantham> - Sarcastic/overconfident tone
   - <red> - Forceful statements
   - <orange> - Counterpoints
   - <quote> - Quoted material
   - <green> - Technical content
   - <teal> - AI-generated content
   - <blue> - Voice from beyond
   - <violet> - Serious announcements
   - <music> - Musical content
   - <mogue> - Actions taken
   - <gray> - Past stories
   - <hazel> - Storytelling

   HOW COLOR TAGS WORK:
   - A color tag at the start of a line colors the ENTIRE line
   - The color ends at the newline character - no closing tag needed or allowed
   - To switch colors, start a new line with a new tag

   CORRECT:
     <green> This entire line is green.
     <orange> This entire line is orange.
     This line has no tag, so it's the default color.

   WRONG (NEVER do this - closing tags don't exist):
     <green>text</green> <orange>text</orange>

   For parenthetical asides in a different color mid-line:
     <green> The function works (<orange> usually) when called.
   The (<orange> ...) creates an inline orange aside within the green line.

   STYLE: Use color tags sparingly. Most text should be untagged plain prose.
   Reserve colors for emphasis: a key technical point, a strong opinion, an aside.

2. INLINE FORMATTING:
   - *text* for emphasis (italic/bold)
   - << text >> for literal/monospace text
   - [[Page Title]] for wiki-style links

3. BLOCK FORMATTING:
   - <<< ... >>> for multi-line literal blocks
   - ---- (four dashes) for section breaks / horizontal rules
   - --MORE-- to mark where truncation should happen

4. LISTS:
   - * item - bullet list
   - # item - numbered list
   - > item - arrow/quote list

5. PRIVATE CONTENT:
   - <<PRIVATE: text >> - inline private note (only visible in private view)
   - <<<PRIVATE: multi-line text >>> - multi-line private block
"""


def create_editor_append_schema() -> Schema:
    """Create the JSON schema for AI append responses (just new text)."""
    return Schema(
        name="EditorAppend",
        description="New content to append to the blog post",
        properties={
            "new_text": SchemaProperty(
                type="string",
                description="The new text to append (NOT the full post, just the addition)",
                required=True,
            ),
            "summary": SchemaProperty(
                type="string", description="Brief description of what was added", required=True
            ),
        },
    )


def create_editor_command_schema() -> Schema:
    """Create the JSON schema for AI command responses (full rewrite)."""
    return Schema(
        name="EditorCommand",
        description="The modified blog post content",
        properties={
            "new_content": SchemaProperty(
                type="string", description="The complete updated blog post content", required=True
            ),
            "summary": SchemaProperty(
                type="string", description="Brief description of what was changed", required=True
            ),
        },
    )


class EditorAssistant:
    """
    LLM-powered assistant for the three-stage blog post editor.

    Two modes:
    - AI Append: Generate new content to add (we concatenate, preserving existing)
    - AI Command: Full rewrite for edits, deletions, restructuring
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.append_schema = create_editor_append_schema()
        self.command_schema = create_editor_command_schema()

    def ai_append(
        self, user_input: str, current_content: str, target_version: str = "both", model: str = None
    ) -> Dict[str, Any]:
        """
        AI generates new content based on user input, we concatenate it.
        Preserves existing content exactly (including ---- dividers).

        Args:
            user_input: What the user wants to add/write about
            current_content: The current AML content (preserved exactly)
            target_version: "both" or "private"
            model: LLM model to use

        Returns:
            Dict with success, new_content (full), new_text (just addition), summary
        """
        try:
            use_model = model or self.model
            logger.info(f"AI append with {use_model}: {user_input[:100]}...")

            # Build append prompt
            prompt = self._build_append_prompt(user_input, current_content, target_version)

            response = generate_chat(
                prompt=prompt,
                model=use_model,
                json_schema=self.append_schema,
                brief=False,
                max_tokens=4096,
            )

            if not response.structured_data:
                return {
                    "success": False,
                    "error": "No response from AI model",
                    "new_content": current_content,
                    "usage_stats": response.usage.to_dict() if response.usage else {},
                }

            data = response.structured_data
            new_text = data.get("new_text", "")

            # Concatenate preserving existing content exactly
            if current_content and not current_content.endswith("\n"):
                separator = "\n\n"
            elif current_content:
                separator = "\n"
            else:
                separator = ""

            new_content = current_content + separator + new_text

            return {
                "success": True,
                "new_content": new_content,
                "new_text": new_text,
                "summary": data.get("summary", ""),
                "error": None,
                "usage_stats": response.usage.to_dict() if response.usage else {},
            }

        except Exception as e:
            logger.error(f"Error in AI append: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "new_content": current_content,
                "usage_stats": {},
            }

    def ai_command(
        self, user_input: str, current_content: str, target_version: str = "both", model: str = None
    ) -> Dict[str, Any]:
        """
        AI executes a command that may modify/delete/restructure content.
        Returns full rewritten content.

        Args:
            user_input: The command (e.g., "delete last paragraph", "make it formal")
            current_content: The current AML content
            target_version: "both" or "private"
            model: LLM model to use

        Returns:
            Dict with success, new_content (full rewrite), summary
        """
        try:
            use_model = model or self.model
            logger.info(f"AI command with {use_model}: {user_input[:100]}...")

            prompt = self._build_command_prompt(user_input, current_content, target_version)

            response = generate_chat(
                prompt=prompt,
                model=use_model,
                json_schema=self.command_schema,
                brief=False,
                max_tokens=8192,
            )

            if not response.structured_data:
                return {
                    "success": False,
                    "error": "No response from AI model",
                    "new_content": current_content,
                    "usage_stats": response.usage.to_dict() if response.usage else {},
                }

            data = response.structured_data

            return {
                "success": True,
                "new_content": data.get("new_content", current_content),
                "summary": data.get("summary", ""),
                "error": None,
                "usage_stats": response.usage.to_dict() if response.usage else {},
            }

        except Exception as e:
            logger.error(f"Error in AI command: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "new_content": current_content,
                "usage_stats": {},
            }

    def _build_append_prompt(
        self, user_input: str, current_content: str, target_version: str
    ) -> str:
        """Build prompt for AI append (generate new text only)."""
        version_note = ""
        if target_version == "private":
            version_note = "Wrap your output in <<PRIVATE: ... >> markers."

        # Show last few lines for context
        context = ""
        if current_content:
            lines = current_content.split("\n")
            last_lines = lines[-10:] if len(lines) > 10 else lines
            context = "Recent content (for context):\n" + "\n".join(last_lines)

        return f"""Write new blog content based on the user's request.

{AML_FORMATTING_GUIDE}

{context}

USER REQUEST: {user_input}

{version_note}

Return JSON with:
- new_text: The new content to add (just your addition, NOT the existing content)
- summary: One sentence describing what you wrote

RULES:
- Write actual prose, not meta-commentary
- NO "Here is a section about..." or "[Section about X]"
- Just write the actual content the reader would see
- Use the color tags above to convey semantic meaning when appropriate"""

    def _build_command_prompt(
        self, user_input: str, current_content: str, target_version: str
    ) -> str:
        """Build prompt for AI command (full rewrite)."""
        version_note = ""
        if target_version == "private":
            version_note = "If adding new content, wrap it in <<PRIVATE: ... >> markers."

        return f"""Execute the user's editing command on this blog post.

{AML_FORMATTING_GUIDE}

CURRENT BLOG POST:
---
{current_content if current_content else "(empty)"}
---

COMMAND: {user_input}

{version_note}

Return JSON with:
- new_content: The complete updated blog post
- summary: One sentence describing what you changed

RULES:
- Preserve ---- section dividers unless told to remove them
- Preserve <<PRIVATE: ... >> markers unless told to remove them
- Write actual prose, not meta-commentary
- Return the COMPLETE post, not just the changed parts
- Use the color tags above to convey semantic meaning when appropriate"""

    def quick_append(
        self, user_input: str, current_content: str, target_version: str = "both"
    ) -> Dict[str, Any]:
        """
        Quick append without LLM processing - for simple text additions.

        This is a faster path when the user just wants to add literal text
        without LLM interpretation.

        Args:
            user_input: The text to append
            current_content: The current content
            target_version: Either "both" or "private"

        Returns:
            Dict with the updated content
        """
        if target_version == "private":
            # Wrap in private markers
            if "\n" in user_input:
                formatted_input = f"<<<PRIVATE: {user_input} >>>"
            else:
                formatted_input = f"<<PRIVATE: {user_input} >>"
        else:
            formatted_input = user_input

        # Add spacing if needed
        if current_content and not current_content.endswith("\n"):
            separator = "\n\n"
        elif current_content:
            separator = "\n"
        else:
            separator = ""

        new_content = current_content + separator + formatted_input

        return {
            "success": True,
            "action": "append",
            "new_content": new_content,
            "reasoning": "Quick append without LLM processing",
            "changes_summary": (
                f"Added: {user_input[:50]}..." if len(user_input) > 50 else f"Added: {user_input}"
            ),
            "error": None,
            "usage_stats": {},
        }


# Default instance
editor_assistant = EditorAssistant()
