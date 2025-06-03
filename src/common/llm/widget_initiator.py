
"""AI-powered widget creation from simple descriptions."""

import os
from typing import Optional, Dict, Any
from pathlib import Path

import tiktoken

from common.llm.openai_client import generate_chat, DEFAULT_MODEL
from common.base.logging_config import get_logger

logger = get_logger(__name__)

class WidgetInitiator:
    """Handles AI-powered widget creation from simple descriptions."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.common_css = self._load_common_css()
        self.fullscreen_hook = self._load_fullscreen_hook()
        self.global_settings_hook = self._load_global_settings_hook()

    def _load_common_css(self) -> str:
        """Load common CSS for context."""
        css_files = [
            'src/web/css/common.css',
            'src/web/css/widget_tools.css',
            'src/web/css/widget.css'
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
            with open('src/react_compiler/js/fullscreen.js', 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("Fullscreen hook file not found")
            return ""

    def _load_global_settings_hook(self) -> str:
        """Load global settings hook code for reference."""
        try:
            with open('src/react_compiler/js/globalSettings.js', 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("Global settings hook file not found")
            return ""

    def create_widget(
        self, 
        slug: str,
        description: str, 
        widget_title: str = None
    ) -> Dict[str, Any]:
        """
        Create a new widget from a description.

        Args:
            slug: URL slug for the widget
            description: Simple description of what the widget should do
            widget_title: Title of the widget (defaults to formatted slug)

        Returns:
            Dict containing widget_code, success, error, and usage stats
        """
        try:
            # Generate widget title from slug if not provided
            if not widget_title:
                widget_title = ' '.join(word.capitalize() for word in slug.replace('-', ' ').replace('_', ' ').split())

            # Build the full prompt with context
            full_prompt = self._build_creation_prompt(
                slug, description, widget_title
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

            # Generate widget code
            response = generate_chat(
                prompt=full_prompt,
                model=self.model,
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
            widget_code = self._extract_code_from_response(response.response_text)

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

    def _build_creation_prompt(self, slug: str, description: str, widget_title: str) -> str:
        """Build the full prompt for widget creation."""
        return f"""You are an expert React developer creating a new React widget from scratch.

WIDGET REQUIREMENTS:
- Widget Title: {widget_title}
- Widget Slug: {slug}
- Component Name: {widget_title.replace(' ', '')}
- Description: {description}

AVAILABLE CSS STYLES:
{self.common_css}

AVAILABLE BUILT-IN HOOKS:

1. FULLSCREEN HOOK (import {{ useFullscreen }} from './useFullscreen'):
{self.fullscreen_hook}

2. GLOBAL SETTINGS HOOK (import {{ useGlobalSettings }} from './useGlobalSettings'):
{self.global_settings_hook}

INSTRUCTIONS:
1. Create a complete, functional React component that fulfills the description
2. Use modern React patterns (hooks, functional components)
3. Make the component interactive and engaging
4. Use the provided CSS variables and classes for styling
5. Consider adding fullscreen support if it would enhance the widget
6. Consider adding global settings integration if appropriate (audio, difficulty, user preferences)
7. Use lucide-react icons where appropriate (import from 'lucide-react')
8. Make sure the component name exactly matches: {widget_title.replace(' ', '')}
9. Include helpful comments explaining the functionality
10. Return ONLY the React component code, no explanation

STYLING GUIDELINES:
- Use CSS custom properties (--color-primary, --color-background, etc.)
- Apply widget-specific classes like 'w-container', 'w-fullscreen' for fullscreen
- Use proper semantic HTML structure
- Make it responsive and accessible

EXAMPLE WIDGET STRUCTURE:
```jsx
import React, {{ useState, useEffect }} from 'react';
import {{ SomeIcon, AnotherIcon }} from 'lucide-react';
import {{ useFullscreen }} from './useFullscreen';
import {{ useGlobalSettings }} from './useGlobalSettings';

const {widget_title.replace(' ', '')} = () => {{
  const [state, setState] = useState(initialValue);
  const {{ isFullscreen, toggleFullscreen, containerRef }} = useFullscreen();
  const {{ settings, SettingsToggle, SettingsModal }} = useGlobalSettings();

  // Widget logic here

  return (
    <div ref={{containerRef}} className={{isFullscreen ? 'w-fullscreen' : 'w-container'}}>
      <div className="widget-header">
        <h1>{widget_title}</h1>
        <div className="widget-controls">
          <SettingsToggle />
          <button onClick={{toggleFullscreen}}>
            {{isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}}
          </button>
        </div>
      </div>
      
      {{/* Main widget content */}}
      <div className="widget-content">
        {{/* Your widget implementation */}}
      </div>
      
      <SettingsModal />
    </div>
  );
}};

export default {widget_title.replace(' ', '')};
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
