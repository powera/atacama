const MyWidget = () => {
  const { settings, SettingsModal, SettingsToggle } = useGlobalSettings();

  return (
    <div className="w-container">
      <div className="w-header">
        <h1>Widget Title</h1>
        <SettingsToggle />
      </div>

      {/* Use settings to customize behavior */}
      <div className={`difficulty-${settings.difficulty}`}>
        {settings.userName && <p>Hello, {settings.userName}!</p>}
        {/* Widget content here */}
      </div>

      <SettingsModal />
    </div>
  );
};
```

The useGlobalSettings hook provides all necessary components and state management - just import and use it.'''
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
            'src/web/css/widgets/widget_tools.css',
            'src/web/css/widgets/widget_settings.css',
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
        use_advanced_model: bool = False,
        data_file: str = None
    ) -> Dict[str, Any]:
        """
        Improve an existing React widget based on a prompt.

        :param current_code: The current widget code
        :param improvement_prompt: What improvements to make
        :param model: LLM model to use
        :param data_file: Optional current data file content
        :return: Tuple of (success, improved_code, improved_data_file, error_message)
        """
        try:
            # Select the appropriate model
            selected_model = "gpt-5-mini" if use_advanced_model else "gpt-5-nano"
            logger.info(f"Using model: {selected_model} for widget improvement")

            # Build the full prompt with context
            full_prompt = self._build_improvement_prompt(
                current_code, prompt, widget_title, data_file
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
                    'improved_data_file': data_file,
                    'usage_stats': response.usage.to_dict() if response.usage else {}
                }

            # Extract code and data file from response
            improved_code, improved_data_file = self._extract_code_and_data_from_response(response.response_text)

            logger.info(f"Finished improving widget code for '{widget_title}'.")
            return {
                'success': True,
                'improved_code': improved_code,
                'improved_data_file': improved_data_file,
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
                'improved_data_file': data_file,
                'usage_stats': {}
            }

    def _build_improvement_prompt(self, current_code: str, improvement_prompt: str, widget_title: str, data_file: Optional[str] = None) -> str:
        """Build the full prompt for widget improvement."""
        prompt_parts = [
            f"""You are an expert React developer helping to improve a React widget. 

WIDGET CONTEXT:
- Widget Title: {widget_title}
- Component should be named: {sanitize_widget_title_for_component_name(widget_title)}
""",
            "CURRENT CSS STYLES AVAILABLE:\n" + self.common_css,
            "CURRENT WIDGET CODE:\n" + current_code,
            "IMPROVEMENT REQUEST:\n" + improvement_prompt,
        ]
        if data_file:
            prompt_parts.append("CURRENT DATA FILE CONTENT:\n" + data_file)

        prompt_parts.extend([
            """
INSTRUCTIONS:
1. Analyze the current widget code and understand its functionality
2. Apply the requested improvements while maintaining existing functionality
3. Use the provided CSS variables and classes where appropriate
4. Ensure the code is clean, well-commented, and follows React best practices
5. Make sure the component name matches the widget title (spaces removed)
6. Return the improved React component code and the improved data file content.

IMPORTANT: 
- Keep all existing functionality intact
- Use modern React patterns (hooks, functional components)
- Ensure the code is production-ready
- Test that all imports are available (React, lucide-react icons, etc.)

Please provide the improved React component code and, if applicable, the improved data file content. Structure your response with clear delimiters for code and data:

CODE:
```jsx
// Improved React component code here
```

DATA:
```json
// Improved data file content here (e.g., JSON)
```
"""
        ])
        return "\n".join(prompt_parts)

    def _extract_code_and_data_from_response(self, response: str) -> Tuple[str, str]:
        """Extract React code and data file from AI response."""
        import re

        code_content = ""
        data_content = ""

        # Look for ```jsx or ```javascript code blocks for the component code
        code_block_pattern = r'```(?:javascript|jsx|react|js)?\n(.*?)\n```'
        code_matches = re.findall(code_block_pattern, response, re.DOTALL)

        if code_matches:
            code_content = code_matches[0].strip()
        else:
            # Fallback: try to find lines that look like React code
            lines = response.split('\n')
            code_lines = []
            in_code = False
            for line in lines:
                if not in_code and ('import React' in line or 'const ' in line or 'function ' in line or 'export default' in line):
                    in_code = True
                if in_code:
                    code_lines.append(line)
            if code_lines:
                code_content = '\n'.join(code_lines).strip()

        # Look for ```json or ``` data blocks for the data file
        data_block_pattern = r'```json\n(.*?)\n```'
        data_matches = re.findall(data_block_pattern, response, re.DOTALL)

        if data_matches:
            data_content = data_matches[0].strip()

        # If no specific data block, but there's a "DATA:" section, try to extract from there
        if not data_content:
            data_section_match = re.search(r'DATA:\n*```json?\n?(.*?)\n*```?', response, re.DOTALL | re.IGNORECASE)
            if data_section_match:
                data_content = data_section_match.group(1).strip()

        # If still no data content, and code content was extracted, assume the rest might be data if it doesn't look like code
        if not data_content and code_content and code_content != response.strip():
            remaining_response = response.replace(code_content, '').strip()
            if remaining_response and not remaining_response.startswith('CODE:'):
                data_content = remaining_response

        return code_content, data_content

    def get_canned_prompts(self) -> Dict[str, Dict[str, str]]:
        """Get available canned improvement prompts."""
        return self.CANNED_PROMPTS.copy()

# Create default instance
widget_improver = WidgetImprover()
const MyWidget = () => {
  const { settings, SettingsModal, SettingsToggle } = useGlobalSettings();

  return (
    <div className="w-container">
      <div className="w-header">
        <h1>Widget Title</h1>
        <SettingsToggle />
      </div>

      {/* Use settings to customize behavior */}
      <div className={`difficulty-${settings.difficulty}`}>
        {settings.userName && <p>Hello, {settings.userName}!</p>}
        {/* Widget content here */}
      </div>

      <SettingsModal />
    </div>
  );
};
```

The useGlobalSettings hook provides all necessary components and state management - just import and use it.'''
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
            'src/web/css/widget_settings.css',
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
        improvement_prompt: str, 
        improvement_type: str = 'custom',
        widget_title: str = "Widget",
        use_advanced_model: bool = False,
        data_file: str = None
    ) -> Dict[str, Any]:
        """
        Improve an existing React widget based on a prompt.

        :param current_code: The current widget code
        :param improvement_prompt: What improvements to make
        :param model: LLM model to use
        :param data_file: Optional current data file content
        :return: Tuple of (success, improved_code, improved_data_file, error_message)
        """
        try:
            # Select the appropriate model
            selected_model = "gpt-5-mini" if use_advanced_model else "gpt-5-nano"
            logger.info(f"Using model: {selected_model} for widget improvement")

            # Build the full prompt with context
            full_prompt = self._build_improvement_prompt(
                current_code, improvement_prompt, widget_title, data_file
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
                    'improved_data_file': data_file,
                    'usage_stats': response.usage.to_dict() if response.usage else {}
                }

            # Extract code and data file from response
            improved_code, improved_data_file = self._extract_code_and_data_from_response(response.response_text)

            logger.info(f"Finished improving widget code for '{widget_title}'.")
            return {
                'success': True,
                'improved_code': improved_code,
                'improved_data_file': improved_data_file,
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
                'improved_data_file': data_file,
                'usage_stats': {}
            }

    def _build_improvement_prompt(self, current_code: str, improvement_prompt: str, widget_title: str, data_file: Optional[str] = None) -> str:
        """Build the full prompt for widget improvement."""
        prompt_parts = [
            f"""You are an expert React developer helping to improve a React widget. 

WIDGET CONTEXT:
- Widget Title: {widget_title}
- Component should be named: {sanitize_widget_title_for_component_name(widget_title)}
""",
            "CURRENT CSS STYLES AVAILABLE:\n" + self.common_css,
            "CURRENT WIDGET CODE:\n" + current_code,
            "IMPROVEMENT REQUEST:\n" + improvement_prompt,
        ]
        if data_file:
            prompt_parts.append("CURRENT DATA FILE CONTENT:\n" + data_file)

        prompt_parts.extend([
            """
INSTRUCTIONS:
1. Analyze the current widget code and understand its functionality
2. Apply the requested improvements while maintaining existing functionality
3. Use the provided CSS variables and classes where appropriate
4. Ensure the code is clean, well-commented, and follows React best practices
5. Make sure the component name matches the widget title (spaces removed)
6. Return the improved React component code and the improved data file content.

IMPORTANT: 
- Keep all existing functionality intact
- Use modern React patterns (hooks, functional components)
- Ensure the code is production-ready
- Test that all imports are available (React, lucide-react icons, etc.)

Please provide the improved React component code and, if applicable, the improved data file content. Structure your response with clear delimiters for code and data:

CODE:
```jsx
// Improved React component code here
```

DATA:
```json
// Improved data file content here (e.g., JSON)
```
"""
        ])
        return "\n".join(prompt_parts)

    def _extract_code_and_data_from_response(self, response: str) -> Tuple[str, str]:
        """Extract React code and data file from AI response."""
        import re

        code_content = ""
        data_content = ""

        # Look for ```jsx or ```javascript code blocks for the component code
        code_block_pattern = r'```(?:javascript|jsx|react|js)?\n(.*?)\n```'
        code_matches = re.findall(code_block_pattern, response, re.DOTALL)

        if code_matches:
            code_content = code_matches[0].strip()
        else:
            # Fallback: try to find lines that look like React code
            lines = response.split('\n')
            code_lines = []
            in_code = False
            for line in lines:
                if not in_code and ('import React' in line or 'const ' in line or 'function ' in line or 'export default' in line):
                    in_code = True
                if in_code:
                    code_lines.append(line)
            if code_lines:
                code_content = '\n'.join(code_lines).strip()

        # Look for ```json or ``` data blocks for the data file
        data_block_pattern = r'```json\n(.*?)\n```'
        data_matches = re.findall(data_block_pattern, response, re.DOTALL)

        if data_matches:
            data_content = data_matches[0].strip()

        # If no specific data block, but there's a "DATA:" section, try to extract from there
        if not data_content:
            data_section_match = re.search(r'DATA:\n*```json?\n?(.*?)\n*