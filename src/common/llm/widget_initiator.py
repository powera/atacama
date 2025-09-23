"""AI-powered widget creation from simple descriptions."""

import os
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

import tiktoken

import constants
from common.base.logging_config import get_logger
from common.llm.openai_client import generate_chat, DEFAULT_MODEL, PROD_MODEL
from common.llm.types import Schema, SchemaProperty
from common.llm.widget_schemas import DUAL_FILE_WIDGET_SCHEMA, SINGLE_FILE_WIDGET_SCHEMA
from react_compiler.lib import sanitize_widget_title_for_component_name

logger = get_logger(__name__)

def initiate_widget(prompt: str, model: str = "gpt-5-mini", dual_file: bool = True) -> Tuple[bool, Dict, str]:
    """
    Generate a React widget based on a natural language prompt.

    :param prompt: Natural language description of the desired widget
    :param model: LLM model to use for generation
    :param dual_file: Whether to generate separate code and data files
    :return: Tuple of (success, widget_data, error_message)
    """
    try:
        # Select the appropriate model
        selected_model = PROD_MODEL if "mini" in model else DEFAULT_MODEL
        if "nano" in model:
            selected_model = constants.GPT_5_NANO
        elif "mini" in model:
            selected_model = constants.GPT_5_MINI
        else:
            selected_model = model
        logger.info(f"Using model: {selected_model} for widget initiation")

        # Select schema based on dual_file parameter
        widget_schema = DUAL_FILE_WIDGET_SCHEMA if dual_file else SINGLE_FILE_WIDGET_SCHEMA

        # Build context for the LLM
        if dual_file:
            context = """You are an expert React developer. Create a complete, functional React widget with separate code and data files.

Requirements:
- Code file: Modern React component with hooks (useState, useEffect, etc.)
- Data file: Separate JavaScript module exporting data (arrays, objects, etc.)
- The code file should import data from the data file using: import data from './data.js'
- Include all necessary imports in the code file
- Export the component as default from the code file
- Export data as default from the data file
- Use inline styles or CSS classes for styling
- Make the widget interactive and engaging
- For educational apps (GRE words, Lithuanian, etc.), put all learning data in the data file

Available external libraries (specify in code_file.imports if used):
- recharts, lodash, d3, axios, date-fns, lucide-react

Data file should export complex datasets like:
- Word lists with translations, definitions, examples
- Quiz questions and answers
- Educational content
- Any large arrays or objects

Both files should be complete and production-ready."""
        else:
            context = """You are an expert React developer. Create a complete, functional React widget based on the user's requirements.

Requirements:
- Use modern React with hooks (useState, useEffect, etc.)
- Include all necessary imports
- Export the component as default
- Use inline styles or CSS classes for styling
- Make the widget interactive and engaging
- Ensure the code is complete and ready to run

Available external libraries (specify in dependencies if used):
- recharts, lodash, d3, axios, date-fns, lucide-react

The widget should be self-contained and production-ready."""

        full_prompt = f"{context}\n\nUser Prompt: {prompt}"

        # Calculate input tokens using tiktoken
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            input_tokens = len(encoding.encode(full_prompt))
        except Exception as e:
            logger.warning(f"Failed to calculate input tokens with tiktoken: {e}")
            input_tokens = 0

        max_tokens = max(2048, input_tokens * 1.25 + 500)

        # Generate widget code
        response = generate_chat(
            prompt=full_prompt,
            model=selected_model,
            schema=widget_schema,
            brief=False,
            max_tokens=int(max_tokens),
        )

        if not response.response_text:
            return False, {'error': 'No response from AI model'}, ''

        # Parse the response based on the schema
        widget_data = {}
        error_message = ""
        try:
            parsed_response = response.parsed_response
            if parsed_response:
                widget_data = parsed_response
                if dual_file:
                    if "code_file" not in widget_data or "data_file" not in widget_data:
                        error_message = "Model response did not conform to dual-file schema."
                        return False, {'error': error_message}, response.response_text
                else:
                    if "code" not in widget_data:
                        error_message = "Model response did not conform to single-file schema."
                        return False, {'error': error_message}, response.response_text
            else:
                error_message = "Failed to parse AI response according to schema."
                return False, {'error': error_message}, response.response_text

        except Exception as e:
            error_message = f"Error parsing AI response: {str(e)}"
            return False, {'error': error_message}, response.response_text

        return True, widget_data, error_message

    except Exception as e:
        logger.error(f"Error initiating widget: {str(e)}")
        return False, {'error': str(e)}, ''


class WidgetInitiator:
    """Handles AI-powered widget creation from simple descriptions."""

    # Look and feel options with descriptions
    LOOK_AND_FEEL_OPTIONS = {
        'tone': {
            'playful': 'The widget should have a fun and lighthearted tone with casual language and engaging interactions',
            'serious': 'The widget should maintain a professional and focused tone with formal language and clear purpose',
            'educational': 'The widget should take a learning-focused approach with explanations and guided discovery',
            'professional': 'The widget should emphasize business efficiency and reliability with a polished presentation'
        },
        'complexity': {
            'minimal': 'Keep the interface simple and clean with only essential features',
            'balanced': 'Create a well-rounded interface with core features and some useful enhancements',
            'feature-rich': 'Build a comprehensive interface with advanced features and extensive customization options'
        },
        'interaction': {
            'guided': 'Design the user experience with step-by-step guidance, clear instructions, and structured flow',
            'exploratory': 'Encourage user discovery and experimentation with an open-ended, flexible approach',
            'game-like': 'Make the experience interactive and engaging with challenges, rewards, and game mechanics'
        },
        'visual': {
            'clean': 'Use a minimalist design with plenty of whitespace and subtle, understated styling',
            'colorful': 'Create a vibrant design with rich colors, visual variety, and eye-catching elements',
            'themed': 'Follow a cohesive visual theme or style that creates a unified aesthetic experience',
            'data-focused': 'Optimize the design for displaying information with clear data presentation and metrics'
        },
        'feedback': {
            'immediate': 'Provide instant responses and real-time updates to keep users informed of their actions',
            'subtle': 'Use gentle and unobtrusive feedback that guides without interrupting the user flow',
            'celebratory': 'Give enthusiastic and rewarding feedback that celebrates achievements and progress',
            'informative': 'Offer detailed and educational feedback that explains what happened and why'
        }
    }

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.common_css = self._load_common_css()
        self.fullscreen_hook = self._load_fullscreen_hook()
        self.global_settings_hook = self._load_global_settings_hook()

    def _load_common_css(self) -> str:
        """Load common CSS for context."""
        css_files = [
            os.path.join(constants.WEB_DIR, 'css', 'common.css'),
            os.path.join(constants.WEB_DIR, 'css', 'widgets', 'widget_tools.css'),
            os.path.join(constants.WEB_DIR, 'css', 'widgets', 'widget.css')
        ]

        css_content = ""
        for css_file in css_files:
            try:
                with open(css_file, 'r') as f:
                    css_content += f"\n/* {css_file} */\n"
                    css_content += f.read()
                    css_content += "\n"
            except FileNotFoundError:
                logger.warning(f"CSS file not found: {css_file}")
                continue

        return css_content

    def _load_fullscreen_hook(self) -> str:
        """Load fullscreen hook code for reference."""
        try:
            fullscreen_path = os.path.join(constants.REACT_COMPILER_JS_DIR, 'useFullscreen.js')
            with open(fullscreen_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("Fullscreen hook file not found")
            return ""

    def _load_global_settings_hook(self) -> str:
        """Load global settings hook code for reference."""
        try:
            global_settings_path = os.path.join(constants.REACT_COMPILER_JS_DIR, 'useGlobalSettings.js')
            with open(global_settings_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("Global settings hook file not found")
            return ""

    def create_widget(
        self,
        slug: str,
        description: str,
        widget_title: str = None,
        use_advanced_model: bool = False,
        look_and_feel: Optional[Dict[str, str]] = None,
        dual_file: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new widget from a description.

        Args:
            slug: URL slug for the widget
            description: Simple description of what the widget should do
            widget_title: Title of the widget (defaults to formatted slug)
            use_advanced_model: If True, use a more advanced model (GPT-5)
            look_and_feel: Dict with keys 'tone', 'complexity', 'interaction', 'visual', 'feedback'
            dual_file: Whether to generate separate code and data files

        Returns:
            Dict containing widget_code, success, error, and usage stats
        """
        try:
            # Select the appropriate model
            selected_model = PROD_MODEL if use_advanced_model else DEFAULT_MODEL
            if use_advanced_model:
                selected_model = constants.GPT_5_MINI # Default to mini if advanced is requested
            else:
                selected_model = constants.GPT_5_NANO # Default to nano for standard

            logger.info(f"Using model: {selected_model} for widget creation")

            # Generate widget title from slug if not provided
            if not widget_title:
                widget_title = ' '.join(word.capitalize() for word in slug.replace('-', ' ').replace('_', ' ').split())

            # Build the full prompt with context
            full_prompt = self._build_creation_prompt(
                slug, description, widget_title, look_and_feel, dual_file
            )
            logger.info(f"Creating widget '{widget_title}' with slug '{slug}' from description: {description[:100]}...")

            # Calculate input tokens using tiktoken
            try:
                encoding = tiktoken.get_encoding("cl100k_base")
                input_tokens = len(encoding.encode(full_prompt))
            except Exception as e:
                logger.warning(f"Failed to calculate input tokens with tiktoken: {e}")
                input_tokens = 0

            max_tokens = max(2048, input_tokens * 1.25 + 500)

            # Select schema based on dual_file parameter
            widget_schema = DUAL_FILE_WIDGET_SCHEMA if dual_file else SINGLE_FILE_WIDGET_SCHEMA

            # Generate widget code
            response = generate_chat(
                prompt=full_prompt,
                model=selected_model,
                schema=widget_schema,
                brief=False,
                max_tokens=int(max_tokens),
            )

            if not response.response_text:
                return {
                    'success': False,
                    'error': 'No response from AI model',
                    'widget_code': '',
                    'usage_stats': response.usage.to_dict() if response.usage else {}
                }

            # Extract code from response
            if dual_file:
                widget_code_content = response.parsed_response.get("code_file", "")
                data_file_content = response.parsed_response.get("data_file", "")
                widget_code = {
                    "code_file": widget_code_content,
                    "data_file": data_file_content
                }
            else:
                widget_code = response.parsed_response.get("code", "")

            logger.info(f"Finished creating widget code for '{widget_title}'.")
            return {
                'success': True,
                'widget_code': widget_code,
                'error': None,
                'usage_stats': response.usage.to_dict() if response.usage else {},
                'full_response': response.response_text
            }

        except Exception as e:
            logger.error(f"Error creating widget: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'widget_code': '',
                'usage_stats': {}
            }

    def _build_creation_prompt(self, slug: str, description: str, widget_title: str, look_and_feel: Optional[Dict[str, str]] = None, dual_file: bool = False) -> str:
        """Build the full prompt for widget creation."""

        # Build look and feel guidance
        look_and_feel_guidance = ""
        if look_and_feel:
            guidance_parts = []
            for category, selected_value in look_and_feel.items():
                if category in self.LOOK_AND_FEEL_OPTIONS and selected_value in self.LOOK_AND_FEEL_OPTIONS[category]:
                    guidance_parts.append(self.LOOK_AND_FEEL_OPTIONS[category][selected_value])

            if guidance_parts:
                look_and_feel_guidance = f"""
LOOK AND FEEL REQUIREMENTS:
{'. '.join(guidance_parts)}.

"""

        # Context for generation
        if dual_file:
            context = """You are an expert React developer. Create a complete, functional React widget with separate code and data files.

Requirements:
- Code file: Modern React component with hooks (useState, useEffect, etc.)
- Data file: Separate JavaScript module exporting data (arrays, objects, etc.)
- The code file should import data from the data file using: import data from './data.js'
- Include all necessary imports in the code file
- Export the component as default from the code file
- Export data as default from the data file
- Use inline styles or CSS classes for styling
- Make the widget interactive and engaging
- For educational apps (GRE words, Lithuanian, etc.), put all learning data in the data file

Available external libraries (specify in code_file.imports if used):
- recharts, lodash, d3, axios, date-fns, lucide-react

Data file should export complex datasets like:
- Word lists with translations, definitions, examples
- Quiz questions and answers
- Educational content
- Any large arrays or objects

Both files should be complete and production-ready."""
        else:
            context = """You are an expert React developer. Create a complete, functional React widget based on the user's requirements.

Requirements:
- Use modern React with hooks (useState, useEffect, etc.)
- Include all necessary imports
- Export the component as default
- Use inline styles or CSS classes for styling
- Make the widget interactive and engaging
- Ensure the code is complete and ready to run

Available external libraries (specify in dependencies if used):
- recharts, lodash, d3, axios, date-fns, lucide-react

The widget should be self-contained and production-ready."""

        return f"""{context}

WIDGET REQUIREMENTS:
- Widget Title: {widget_title}
- Widget Slug: {slug}
- Component Name: {sanitize_widget_title_for_component_name(widget_title)}
- Description: {description}
- Look and Feel: {look_and_feel_guidance}

AVAILABLE CSS STYLES:
{self.common_css}

AVAILABLE BUILT-IN HOOKS:

1. FULLSCREEN HOOK (import {{ useFullscreen }} from './useFullscreen'):
{self.fullscreen_hook}

2. GLOBAL SETTINGS HOOK (import {{ useGlobalSettings }} from './useGlobalSettings'):
{self.global_settings_hook}

EXTERNAL MODULES (use only if necessary):
- lucide-react: Icon library (import {{ IconName }} from 'lucide-react')
- recharts: Charting library for data visualization

INSTRUCTIONS:
1. Create a complete, functional React component that fulfills the description
2. Use modern React patterns (hooks, functional components)
3. Make the component interactive and engaging
4. Use the provided CSS variables and classes for styling
5. Follow the LOOK AND FEEL REQUIREMENTS above - they define the tone, complexity, interaction style, visual design, and feedback approach
6. Consider adding fullscreen support if it would enhance the widget
7. Consider adding global settings integration if appropriate (audio, difficulty, user preferences)
8. PREFER EMOJI over icons - use emoji characters (🎮, 📊, ⚙️, 🔍, etc.) instead of icon libraries
9. Only use external modules (lucide-react, recharts) when necessary for complex functionality
10. Make sure the component name exactly matches: {sanitize_widget_title_for_component_name(widget_title)}
11. Include helpful comments explaining the functionality
12. Return ONLY the React component code, no explanation

STYLING GUIDELINES:
- Use CSS custom properties (--color-primary, --color-background, etc.)
- Apply widget-specific classes like 'w-container', 'w-fullscreen' for fullscreen
- Use proper semantic HTML structure
- Make it responsive and accessible

EXAMPLE WIDGET STRUCTURE:
```jsx
import React, {{ useState, useEffect }} from 'react';
import {{ useFullscreen }} from './useFullscreen';
import {{ useGlobalSettings }} from './useGlobalSettings';

const {sanitize_widget_title_for_component_name(widget_title)} = () => {{
  const [state, setState] = useState(initialValue);
  const {{ isFullscreen, toggleFullscreen, containerRef }} = useFullscreen();
  const {{ settings, SettingsToggle, SettingsModal }} = useGlobalSettings();

  // Widget logic here

  return (
    <div ref={{containerRef}} className={{isFullscreen ? 'w-fullscreen' : 'w-container'}}>
      <div className="widget-header">
        <h1>🎮 {widget_title}</h1>
        <div className="widget-controls">
          <SettingsToggle />
          <button onClick={{toggleFullscreen}}>
            {{isFullscreen ? '🔙 Exit Fullscreen' : '🔍 Fullscreen'}}
          </button>
        </div>
      </div>

      {{/* Main widget content */}}
      <div className="widget-content">
        {{/* Your widget implementation with emoji for visual elements */}}
        <button>▶️ Start</button>
        <button>⏸️ Pause</button>
        <div>📊 Score: {{score}}</div>
      </div>

      <SettingsModal />
    </div>
  );
}};

export default {sanitize_widget_title_for_component_name(widget_title)};
```

Please create a complete, functional React widget based on the description: "{description}"
"""

    def _extract_code_from_response(self, response: str) -> str:
        """Extract React code from AI response."""
        # Try to extract code from markdown code blocks
        import re

        # Look for ```javascript, ```jsx, or ```react code blocks
        code_block_pattern = r'```(?:javascript|jsx|react|js)?\n(.*?)\n```'
        matches = re.findall(code_block_pattern, response, re.DOTALL)

        if matches:
            # Return the first code block found
            return matches[0].strip()

        # If no code blocks found, look for code that starts with typical React patterns
        lines = response.split('\n')
        code_lines = []
        in_code = False

        for line in lines:
            # Start collecting when we see React-like code
            if not in_code and ('import React' in line or 'const ' in line or 'function ' in line or 'export default' in line):
                in_code = True

            if in_code:
                code_lines.append(line)

        if code_lines:
            return '\n'.join(code_lines).strip()

        # Fallback: return the response as-is
        return response.strip()

# Create default instance
widget_initiator = WidgetInitiator()