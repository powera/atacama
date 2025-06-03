"""AI-powered widget improvement using OpenAI API."""

import os
from typing import Optional, Dict, Any
from pathlib import Path

import tiktoken

from common.llm.openai_client import generate_chat, DEFAULT_MODEL, PROD_MODEL
from common.base.logging_config import get_logger

logger = get_logger(__name__)

class WidgetImprover:
    """Handles AI-powered widget improvements using OpenAI."""

    # Canned improvement prompts
    CANNED_PROMPTS = {
        'fullscreen': {
            'name': 'Improve Full-Screen Mode',
            'prompt': '''Add fullscreen functionality to this React widget using the existing useFullscreen hook.

IMPORTANT: DO NOT implement toggleFullscreen() or any fullscreen logic yourself. Use the pre-built hook instead.

Required changes:
1. Add this import at the top: import { useFullscreen } from './useFullscreen'
2. Inside your component, add: const { isFullscreen, toggleFullscreen, containerRef } = useFullscreen();
3. Attach containerRef to your main container: <div ref={containerRef} className={isFullscreen ? 'w-fullscreen' : 'w-container'}>
4. Add a fullscreen toggle button: <button onClick={toggleFullscreen}>{isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}</button>

The useFullscreen hook is already implemented in fullscreen.js - just import and use it. Do NOT write any fullscreen implementation code yourself.
'''
        },
        'global_settings': {
            'name': 'Add Global Settings Support',
            'prompt': '''Enhance this React widget to support global application settings. Add:
- Theme support (dark/light mode compatibility)
- User preference integration
- Configurable colors and styling
- Accessibility improvements
- Settings persistence

Use CSS custom properties (--var-name) for themeable values and ensure the widget respects the global design system.'''
        },
        'accessibility': {
            'name': 'Improve Accessibility',
            'prompt': '''Improve the accessibility of this React widget by adding:
- Proper ARIA labels and roles
- Keyboard navigation support
- Screen reader compatibility
- High contrast support
- Focus management
- Semantic HTML structure

Ensure the widget is usable by people with disabilities and follows WCAG guidelines.'''
        },
        'performance': {
            'name': 'Optimize Performance',
            'prompt': '''Optimize this React widget for better performance:
- Use React.memo where appropriate
- Implement proper dependency arrays for hooks
- Minimize re-renders
- Optimize heavy calculations
- Lazy load components if applicable
- Use efficient data structures

Focus on making the widget fast and responsive.'''
        },
        'mobile_friendly': {
            'name': 'Make Mobile-Friendly',
            'prompt': '''Optimize this React widget for mobile devices:
- Touch-friendly interface elements
- Responsive design for small screens
- Proper touch gestures
- Mobile-optimized interactions
- Swipe and pinch support where relevant
- Fast loading on mobile networks

Ensure the widget provides an excellent mobile user experience.'''
        }
    }

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.common_css = self._load_common_css()

    def _load_common_css(self) -> str:
        """Load common CSS for context."""
        css_files = [
            'src/web/css/common.css',
            'src/web/css/widget_tools.css',
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

    def improve_widget(
        self, 
        current_code: str, 
        prompt: str, 
        improvement_type: str = 'custom',
        widget_title: str = "Widget",
        use_advanced_model: bool = False
    ) -> Dict[str, Any]:
        """
        Improve widget code using AI.

        Args:
            current_code: The current React widget code
            prompt: The improvement prompt
            improvement_type: Type of improvement ('canned', 'custom', 'manual')
            widget_title: Title of the widget for context
            use_advanced_model: If True, use GPT-4.1-mini instead of nano

        Returns:
            Dict containing improved_code, success, error, and usage stats
        """
        try:
            # Select the appropriate model
            selected_model = PROD_MODEL if use_advanced_model else DEFAULT_MODEL
            logger.info(f"Using model: {selected_model} for widget improvement")
            
            # Build the full prompt with context
            full_prompt = self._build_improvement_prompt(
                current_code, prompt, widget_title
            )
            logger.info(f"Improving widget code for '{widget_title}' with prompt: {full_prompt[:100]}...")  # Log first 100 chars

            # Calculate input tokens using tiktoken
            try:
                encoding = tiktoken.get_encoding("cl100k_base")
                input_tokens = 0
                input_tokens += len(encoding.encode(full_prompt))
            except Exception as e:
                logger.warning(f"Failed to calculate input tokens with tiktoken: {e}")
                input_tokens = 0

            max_tokens = max(2048, input_tokens * 1.25 + 500)

            # Generate improved code
            response = generate_chat(
                prompt=full_prompt,
                model=selected_model,
                brief=False,
                max_tokens=int(max_tokens),
            )

            if not response.response_text:
                return {
                    'success': False,
                    'error': 'No response from AI model',
                    'improved_code': current_code,
                    'usage_stats': response.usage.to_dict() if response.usage else {}
                }

            # Extract code from response
            improved_code = self._extract_code_from_response(response.response_text)

            logger.info(f"Finished improving widget code for '{widget_title}'.")
            return {
                'success': True,
                'improved_code': improved_code,
                'error': None,
                'usage_stats': response.usage.to_dict() if response.usage else {},
                'full_response': response.response_text
            }

        except Exception as e:
            logger.error(f"Error improving widget: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'improved_code': current_code,
                'usage_stats': {}
            }

    def _build_improvement_prompt(self, current_code: str, improvement_prompt: str, widget_title: str) -> str:
        """Build the full prompt for widget improvement."""
        return f"""You are an expert React developer helping to improve a React widget. 

WIDGET CONTEXT:
- Widget Title: {widget_title}
- Component should be named: {widget_title.replace(' ', '')}

CURRENT CSS STYLES AVAILABLE:
{self.common_css}

CURRENT WIDGET CODE:
{current_code}

IMPROVEMENT REQUEST:
{improvement_prompt}

INSTRUCTIONS:
1. Analyze the current widget code and understand its functionality
2. Apply the requested improvements while maintaining existing functionality
3. Use the provided CSS variables and classes where appropriate
4. Ensure the code is clean, well-commented, and follows React best practices
5. Make sure the component name matches the widget title (spaces removed)
6. Return ONLY the improved React component code, no explanation unless asked

IMPORTANT: 
- Keep all existing functionality intact
- Use modern React patterns (hooks, functional components)
- Ensure the code is production-ready
- Test that all imports are available (React, lucide-react icons, etc.)

Please provide the improved React component code:"""

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

    def get_canned_prompts(self) -> Dict[str, Dict[str, str]]:
        """Get available canned improvement prompts."""
        return self.CANNED_PROMPTS.copy()

# Create default instance
widget_improver = WidgetImprover()