import tiktoken
from typing import Dict, Any, Optional, Tuple, List

from common.base.logging_config import get_logger
from common.llm.openai_client import generate_chat
from common.llm.widget_schemas import create_widget_improvement_schema
from react_compiler.lib import sanitize_widget_title_for_component_name

logger = get_logger(__name__)

DEFAULT_MODEL = "gpt-5-nano"

class WidgetImprover:
    CANNED_PROMPTS = {
        'refactor': {
            'name': 'Refactor Code',
            'prompt': '''Refactor the provided React widget code to improve its structure, readability, and maintainability.
Focus on:
- Component decomposition: Break down the widget into smaller, reusable components.
- State management: Ensure efficient and clear state management.
- Prop drilling: Minimize prop drilling by using context or state management libraries if necessary.
- Code organization: Group related logic and styles.
- Readability: Use clear variable names and consistent formatting.

Ensure the refactored code maintains the exact same functionality and public API as the original widget.'''
        },
        'improve_ui': {
            'name': 'Improve User Interface',
            'prompt': '''Enhance the User Interface (UI) of this React widget:
- Modernize the look and feel.
- Improve visual hierarchy and layout.
- Ensure consistent spacing and alignment.
- Use appropriate color schemes.
- Add subtle animations or transitions for a better user experience.
- Make sure the UI is intuitive and easy to use.

The widget should look professional and visually appealing, while maintaining its core functionality.'''
        },
        'add_testing': {
            'name': 'Add Unit and Integration Tests',
            'prompt': '''Add comprehensive unit and integration tests for the provided React widget using a popular testing framework like Jest and React Testing Library.
- Unit Tests: Test individual components and utility functions in isolation.
- Integration Tests: Test the interaction between different components and the widget's overall behavior.
- Mocking: Mock external dependencies and API calls as needed.
- Test coverage: Aim for high test coverage to ensure reliability.

The tests should verify that the widget functions as expected and handles various scenarios correctly.'''
        },
        'improve_reactivity': {
            'name': 'Improve Reactivity and State Management',
            'prompt': '''Optimize the reactivity and state management of this React widget:
- Efficiently handle state updates to prevent unnecessary re-renders.
- Use appropriate React hooks (useState, useEffect, useContext, useReducer, useCallback, useMemo).
- Consider state management libraries like Zustand or Redux Toolkit for complex state.
- Ensure that derived state is calculated efficiently.
- Implement patterns like lifting state up or context API to manage shared state.

The goal is to make the widget more performant and easier to manage.'''
        },
        'add_error_handling': {
            'name': 'Add Robust Error Handling',
            'prompt': '''Implement robust error handling for this React widget:
- Gracefully handle errors during data fetching, component rendering, or user interactions.
- Display user-friendly error messages.
- Implement error boundaries for critical components.
- Log errors for debugging purposes.
- Consider fallback UI states for error conditions.

Ensure the widget remains stable and provides a good user experience even when errors occur.'''
        },
        'improve_state_logic': {
            'name': 'Improve State Logic',
            'prompt': '''Refine the state management logic within this React widget for better clarity and efficiency.
- Simplify complex state updates.
- Ensure state transitions are predictable.
- Use immutability principles for state updates.
- Consider using `useReducer` for more complex state machines.
- Organize state related to different features.

The aim is to make the state management more understandable and less prone to bugs.'''
        },
        'enhance_user_feedback': {
            'name': 'Enhance User Feedback',
            'prompt': '''Improve user feedback mechanisms within this React widget:
- Provide visual cues for user actions (e.g., loading spinners, success messages, button states).
- Clearly indicate the status of operations.
- Use tooltips or helper text for complex interactions.
- Ensure feedback is timely and relevant to the user's actions.

The widget should clearly communicate what is happening to the user.'''
        },
        'add_types': {
            'name': 'Add TypeScript Types',
            'prompt': '''Convert this JavaScript React widget to TypeScript and add comprehensive type definitions.
- Define types for props, state, and event handlers.
- Use TypeScript features like interfaces, types, generics, and enums.
- Ensure type safety throughout the component.
- Leverage utility types for common patterns.

The goal is to improve code quality, catch potential errors early, and enhance maintainability.'''
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
        data_file: Optional[str] = None,
        additional_files: Optional[Dict[str, str]] = None,
        target_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Improve an existing React widget based on a prompt, potentially updating multiple files.

        :param current_code: The current widget code
        :param improvement_prompt: What improvements to make
        :param model: LLM model to use
        :param data_file: Optional current data file content
        :param additional_files: Optional dictionary of other files to consider for context or modification
        :return: Dict containing success status, improved code, improved data file, error message, and usage stats.
        """
        try:
            # Default to modifying main_code if no target_files specified (backward compatibility)
            if not target_files:
                target_files = ['main_code']
                
            selected_model = "gpt-5-mini" if use_advanced_model else "gpt-5-nano"
            logger.info(f"Using model: {selected_model} for widget improvement")

            # Prepare context and prompt for the LLM
            full_prompt = self._build_improvement_prompt(
                current_code, prompt, widget_title, data_file, additional_files, target_files
            )
            logger.info(f"Improving widget code for '{widget_title}' with prompt: {full_prompt[:100]}...")

            try:
                encoding = tiktoken.get_encoding("cl100k_base")
                input_tokens = len(encoding.encode(full_prompt))
            except Exception as e:
                logger.warning(f"Failed to calculate input tokens with tiktoken: {e}")
                input_tokens = 0

            max_tokens = max(2048, int(input_tokens * 1.25) + 500)
            
            # Determine if we should include data_file in schema
            include_data_file = (
                'data_file' in target_files or
                'create_data_file' in target_files or
                bool(data_file)
            )

            # Use dynamic schema based on target files
            improvement_schema = create_widget_improvement_schema(include_data_file=include_data_file)

            # Make the API call
            response = generate_chat(
                prompt=full_prompt,
                model=selected_model,
                json_schema=improvement_schema,
                brief=False,
                max_tokens=int(max_tokens),
            )

            if not response.structured_data:
                return {
                    'success': False,
                    'error': 'No response from AI model',
                    'improved_code': current_code,
                    'improved_data_file': data_file,
                    'improved_additional_files': additional_files,
                    'usage_stats': response.usage.to_dict() if response.usage else {}
                }

            # Extract from structured response
            structured_data = response.structured_data
            
            # Only update files that were explicitly targeted for improvement
            if 'main_code' in target_files:
                improved_code = structured_data.get('main_code', current_code)
            else:
                improved_code = current_code  # Keep original if not targeted
            
            # Handle data file based on target files
            if 'data_file' in target_files or 'create_data_file' in target_files:
                improved_data_file = structured_data.get('data_file', data_file)
            else:
                improved_data_file = data_file  # Keep original if not targeted
            
            improved_additional_files = additional_files or {}  # Keep original additional files

            logger.info(f"Finished improving widget code for '{widget_title}'. Target files: {target_files}")
            return {
                'success': True,
                'improved_code': improved_code,
                'improved_data_file': improved_data_file,
                'improved_additional_files': improved_additional_files,
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
                'improved_additional_files': additional_files,
                'usage_stats': {}
            }

    def _build_improvement_prompt(self, current_code: str, improvement_prompt: str, widget_title: str, data_file: Optional[str] = None, additional_files: Optional[Dict[str, str]] = None, target_files: Optional[List[str]] = None) -> str:
        """Build the full prompt for widget improvement, including additional files."""
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

        if additional_files:
            for filename, content in additional_files.items():
                prompt_parts.append(f"CONTENT OF ADDITIONAL FILE ({filename}):\n" + content)

        target_files_instruction = ""
        if target_files:
            target_files_instruction = f"\nTARGET FILES TO MODIFY: {', '.join(target_files)}\nIMPORTANT: Only modify the files listed above. Do not change other files unless absolutely necessary for the improvement to work.\n"

        prompt_parts.extend([
            f"""
{target_files_instruction}
INSTRUCTIONS:
1. Analyze the current widget code and understand its functionality.
2. Apply the requested improvements while maintaining existing functionality.
3. Use the provided CSS variables and classes where appropriate.
4. Ensure the code is clean, well-commented, and follows React best practices.
5. Make sure the component name matches the widget title (spaces removed).
6. If multiple files were provided, ensure changes are consistent across them.

IMPORTANT: 
- Keep all existing functionality intact.
- Use modern React patterns (hooks, functional components).
- Ensure the code is production-ready.
- Test that all imports are available (React, lucide-react icons, etc.).

Provide the improved files in the structured JSON format requested. 
- If main_code is in the target files, provide the improved main_code. If not, the original will be preserved.
- If data_file or create_data_file is in the target files, provide the improved data_file. If not, the original will be preserved.
- Only return content for files that were actually modified according to the target files list.
"""
        ])
        return "\n".join(prompt_parts)

    def _extract_code_and_data_from_response(self, response: str) -> Tuple[str, str, Dict[str, str]]:
        """Extract React code, data file, and other files from AI response."""
        import re

        code_content = ""
        data_content = ""
        additional_files_content = {}

        # Regex to find code blocks with optional language specifier (jsx, js, react, ts, tsx)
        # and also capture the filename if provided before the code block
        # Pattern breakdown:
        # (?:^|\n)              : Non-capturing group for start of line or newline
        # ([\w-]+\.(?:jsx|js|tsx|ts))? : Optional filename capture (word characters, hyphen, dot, extension)
        # \s*                   : Optional whitespace
        # ```(?:javascript|jsx|react|js|typescript|ts|tsx)?\n : Code block start with optional language
        # (.*?)                 : Non-greedy capture of the code content
        # \n```                 : Code block end
        # re.DOTALL             : Make '.' match newline characters
        # re.MULTILINE          : Make '^' and '$' match start/end of lines

        # First, try to extract the main component code
        code_block_pattern = r'CODE:\n*```(?:javascript|jsx|react|js|typescript|ts|tsx)?\n(.*?)\n```'
        code_match = re.search(code_block_pattern, response, re.DOTALL | re.IGNORECASE)
        if code_match:
            code_content = code_match.group(1).strip()

        # Then, extract the data file content
        data_block_pattern = r'DATA:\n*```json?\n?(.*?)\n*```?'
        data_match = re.search(data_block_pattern, response, re.DOTALL | re.IGNORECASE)
        if data_match:
            data_content = data_match.group(1).strip()

        # Extract any other specified files
        # This regex looks for a filename followed by a code block
        # It assumes filenames are provided on their own line before the code block
        other_files_pattern = r'^([\w-]+\.(?:jsx|js|tsx|ts|css|json|md)):\s*\n```(?:javascript|jsx|react|js|typescript|ts|tsx|css|json|md)?\n(.*?)\n```'
        other_files_matches = re.findall(other_files_pattern, response, re.DOTALL | re.MULTILINE)

        for filename, content in other_files_matches:
            # Avoid overwriting if the main code or data content was already parsed
            if filename.lower() == 'code' or filename.lower() == 'data':
                continue
            additional_files_content[filename] = content.strip()

        # Fallback for main code if 'CODE:' block is missing but code-like content exists
        if not code_content:
            lines = response.split('\n')
            code_lines = []
            in_code_block = False
            for line in lines:
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    if in_code_block and ('javascript' in line or 'jsx' in line or 'react' in line):
                        continue # Skip the ```jsx line itself if it's the start
                    elif not in_code_block and line.strip() == '```':
                        continue # Skip the closing ``` line

                if in_code_block:
                    code_lines.append(line)
                elif not code_content and ('import React' in line or 'const ' in line or 'function ' in line or 'export default' in line or line.strip().startswith('<')):
                    # If not in a code block, but line looks like React code, start capturing
                    code_content = line + "\n"
                    in_code_block = True # Assume the rest might be code until a ``` is found

            if code_lines and not code_content.endswith('\n'.join(code_lines).strip()):
                 code_content += '\n'.join(code_lines).strip()

            code_content = code_content.strip()


        # Fallback for data if 'DATA:' block is missing but JSON-like content exists
        if not data_content:
            data_section_match = re.search(r'DATA:\n*```json?\n?(.*?)\n*```?', response, re.DOTALL | re.IGNORECASE)
            if data_section_match:
                data_content = data_section_match.group(1).strip()
            else:
                # Very basic fallback: if response contains JSON structure and no other code blocks were identified
                if re.search(r'\{.*\}', response, re.DOTALL) and not any(ext in response for ext in ['.jsx', '.js', '.tsx', '.ts', '.css', '.md']):
                    try:
                        import json
                        json.loads(response.strip())
                        data_content = response.strip()
                    except json.JSONDecodeError:
                        pass # Not valid JSON

        return code_content, data_content, additional_files_content

    def get_canned_prompts(self) -> Dict[str, Dict[str, str]]:
        """Get available canned improvement prompts."""
        return self.CANNED_PROMPTS.copy()

# Create default instance
widget_improver = WidgetImprover()