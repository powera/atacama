import os
import json
import subprocess
import tempfile
import shutil
import re
from pathlib import Path
from typing import Dict, Tuple, List, Optional

import constants
from common.base.logging_config import get_logger
logger = get_logger(__name__)

# Hack - to ensure that the PATH is set correctly for subprocess calls
env = os.environ.copy()
env['PATH'] = '/usr/local/bin:/usr/bin:/bin:' + env.get('PATH', '')

class WidgetBuilder:
    """Builds React widgets with proper bundling for browser use."""
    
    # Available packages that can be bundled
    AVAILABLE_PACKAGES = {
        'recharts': '^2.12.7',
        'lodash': '^4.17.21',
        'axios': '^1.6.0',
        'd3': '^7.8.5',
        'date-fns': '^3.0.0',
        'lucide-react': '^0.263.1',
    }
    
    # Default external packages
    DEFAULT_EXTERNAL_PACKAGES = {
        'react': 'React',
        'react-dom': 'ReactDOM'
    }
    
    # Additional known external package mappings
    EXTERNAL_PACKAGE_MAPPINGS = {
        'recharts': 'Recharts',
        'lodash': '_',
        'd3': 'd3',
        'axios': 'axios',
        'date-fns': 'dateFns',
        'lucide-react': 'LucideReact'
    }

    def __init__(self, build_dir: str = None):
        self.build_dir = build_dir or os.path.join(tempfile.gettempdir(), 'widget_builds')
        Path(self.build_dir).mkdir(parents=True, exist_ok=True)
        
        # Load built-in hooks from files
        self.BUILT_IN_HOOKS = self._load_built_in_hooks()
    
    def _load_built_in_hooks(self) -> Dict[str, str]:
        """
        Load built-in hooks from the react_compiler directory.
        
        :return: Dictionary mapping hook names to their source code
        """
        hooks = {}
        
        # Define hook file mappings
        hook_files = {
            'useFullscreen': 'useFullscreen.js',
            'useGlobalSettings': 'useGlobalSettings.js'
        }
        
        # Get the directory where this file is located
        react_compiler_dir = Path(constants.REACT_COMPILER_JS_DIR)
        
        for hook_name, filename in hook_files.items():
            hook_file_path = react_compiler_dir / filename
            try:
                if hook_file_path.exists():
                    with open(hook_file_path, 'r') as f:
                        hooks[hook_name] = f.read()
                    logger.info(f"Loaded built-in hook: {hook_name} from {filename}")
                else:
                    logger.warning(f"Hook file not found: {hook_file_path}")
            except Exception as e:
                logger.error(f"Error loading hook {hook_name} from {filename}: {e}")
        
        return hooks
    
    def _detect_hook_imports(self, widget_code: str) -> List[str]:
        """
        Detect imports of built-in hooks from widget code.
        
        :param widget_code: The widget source code
        :return: List of hook names that need to be created
        """
        hooks_needed = []
        
        # Look for imports like: import { useFullscreen } from './useFullscreen';
        # or: import useFullscreen from './useFullscreen';
        import_patterns = [
            r'import\s+{\s*([^}]+)\s*}\s+from\s+[\'"]\.\/([^\'\"]*)[\'"]',
            r'import\s+(\w+)\s+from\s+[\'"]\.\/([^\'\"]*)[\'"]'
        ]
        
        for pattern in import_patterns:
            matches = re.findall(pattern, widget_code)
            for match in matches:
                if len(match) == 2:
                    hook_names, file_name = match
                    
                    # Handle named imports vs default imports
                    if pattern == import_patterns[0]:  # Named import pattern
                        # Extract hook names from { useFullscreen, otherHook }
                        hook_names = hook_names.strip()
                        for hook in hook_names.split(','):
                            hook = hook.strip()
                            if hook in self.BUILT_IN_HOOKS:
                                hooks_needed.append(hook)
                    else:  # Default import pattern
                        # Check if file_name corresponds to a built-in hook
                        clean_file_name = file_name.replace('.js', '').replace('.jsx', '')
                        if clean_file_name in self.BUILT_IN_HOOKS:
                            hooks_needed.append(clean_file_name)
        
        return list(set(hooks_needed))  # Remove duplicates
    
    def _create_hook_files(self, temp_dir: str, hooks_needed: List[str]) -> None:
        """
        Create hook files in the temp directory.
        
        :param temp_dir: Temporary build directory
        :param hooks_needed: List of hook names to create
        """
        src_dir = os.path.join(temp_dir, 'src')
        
        for hook_name in hooks_needed:
            if hook_name in self.BUILT_IN_HOOKS:
                hook_file_path = os.path.join(src_dir, f'{hook_name}.js')
                with open(hook_file_path, 'w') as f:
                    f.write(self.BUILT_IN_HOOKS[hook_name])
                logger.info(f"Created built-in hook file: {hook_name}.js")
            else:
                logger.warning(f"Requested hook '{hook_name}' not found in built-in hooks")
    
    def _handle_exports(self, widget_code: str, widget_name: str) -> str:
        """
        Handle export statements in widget code intelligently.
        
        :param widget_code: The original widget code
        :param widget_name: Expected name of the widget component
        :return: Code with proper export statement
        """
        # Remove any trailing whitespace/newlines for cleaner processing
        code = widget_code.strip()
        
        # Patterns to detect existing exports
        export_patterns = [
            # export default ComponentName;
            (r'export\s+default\s+(\w+)\s*;?\s*$', 'simple'),
            # export default function ComponentName() {...}
            (r'export\s+default\s+function\s+(\w+)\s*\([^)]*\)\s*\{', 'function'),
            # export default () => {...}
            (r'export\s+default\s+\([^)]*\)\s*=>\s*\{', 'arrow'),
            # export default class ComponentName {...}
            (r'export\s+default\s+class\s+(\w+)\s*\{', 'class'),
            # export { ComponentName as default };
            (r'export\s+\{\s*(\w+)\s+as\s+default\s*\}\s*;?\s*$', 'named'),
            # module.exports = ComponentName;
            (r'module\.exports\s*=\s*(\w+)\s*;?\s*$', 'commonjs')
        ]
        
        has_export = False
        exported_name = None
        export_type = None
        
        # Check if there's already an export
        for pattern, pattern_type in export_patterns:
            match = re.search(pattern, code, re.MULTILINE | re.DOTALL)
            if match:
                has_export = True
                export_type = pattern_type
                if match.groups() and pattern_type != 'arrow':
                    exported_name = match.group(1)
                logger.info(f"Found existing export: {exported_name or 'anonymous'} (type: {export_type})")
                break
        
        if has_export:
            if exported_name and exported_name != widget_name:
                # Replace the exported component name with the expected widget name
                logger.info(f"Replacing exported component name '{exported_name}' with '{widget_name}'")
                
                # First, replace the component definition name
                if export_type == 'function':
                    # Handle export default function ComponentName() pattern
                    code = re.sub(rf'export\s+default\s+function\s+{re.escape(exported_name)}\s*\(',
                                f'export default function {widget_name}(', code)
                else:
                    # Handle other component definition patterns
                    component_def_patterns = [
                        (rf'function\s+{re.escape(exported_name)}\s*\(', f'function {widget_name}('),
                        (rf'const\s+{re.escape(exported_name)}\s*=', f'const {widget_name} ='),
                        (rf'let\s+{re.escape(exported_name)}\s*=', f'let {widget_name} ='),
                        (rf'var\s+{re.escape(exported_name)}\s*=', f'var {widget_name} ='),
                        (rf'class\s+{re.escape(exported_name)}\s*\{{', f'class {widget_name} {{'),
                    ]
                    
                    for old_pattern, new_replacement in component_def_patterns:
                        code = re.sub(old_pattern, new_replacement, code)
                    
                    # Replace the export statement (except for function exports which were already handled)
                    if export_type != 'function':
                        for pattern, _ in export_patterns:
                            if re.search(pattern, code, re.MULTILINE | re.DOTALL):
                                code = re.sub(pattern, f'export default {widget_name};', code)
                                break
            
            # If the export is already correct, just return the code as-is
            return code
        else:
            # No existing export, add one
            logger.info(f"No existing export found, adding export for {widget_name}")
            return f"{code}\n\n// Export the component\nexport default {widget_name};"
    
    def build_widget(self, widget_code: str, widget_name: str, dependencies: List[str] = None, external_dependencies: List[str] = None) -> Tuple[bool, str, str]:
        """
        Build a widget with webpack to create a browser-ready bundle.
        
        :param widget_code: The widget source code
        :param widget_name: Name of the widget
        :param dependencies: List of dependencies to include (e.g., ['recharts', 'lodash'])
        :param external_dependencies: List of dependencies to treat as external (not bundled)
        :return: Tuple of (success, built_code, error_message)
        """
        dependencies = dependencies or []
        external_dependencies = external_dependencies or []
        temp_dir = tempfile.mkdtemp(dir=self.build_dir)
        
        try:
            # Detect hooks needed for this widget
            hooks_needed = self._detect_hook_imports(widget_code)
            if hooks_needed:
                logger.info(f"Detected built-in hooks needed: {', '.join(hooks_needed)}")
            
            # Build package.json with only required dependencies
            package_json = {
                "name": f"widget-{widget_name}",
                "version": "1.0.0",
                "private": True,
                "dependencies": {
                    "react": "^18.0.0",
                    "react-dom": "^18.0.0"
                },
                "devDependencies": {
                    "@babel/core": "^7.0.0",
                    "@babel/preset-env": "^7.0.0",
                    "@babel/preset-react": "^7.0.0",
                    "babel-loader": "^9.0.0",
                    "webpack": "^5.0.0",
                    "webpack-cli": "^5.0.0"
                }
            }
            
            # Add only requested dependencies
            all_dependencies = set(dependencies + external_dependencies)
            for dep in all_dependencies:
                if dep in self.AVAILABLE_PACKAGES:
                    package_json["dependencies"][dep] = self.AVAILABLE_PACKAGES[dep]
                else:
                    logger.warning(f"Unknown dependency requested: {dep}")
            
            with open(os.path.join(temp_dir, 'package.json'), 'w') as f:
                json.dump(package_json, f, indent=2)
            
            # Build externals configuration
            externals = self.DEFAULT_EXTERNAL_PACKAGES.copy()
            for dep in external_dependencies:
                if dep in self.EXTERNAL_PACKAGE_MAPPINGS:
                    externals[dep] = self.EXTERNAL_PACKAGE_MAPPINGS[dep]
                else:
                    # Use PascalCase as default for unknown packages
                    externals[dep] = ''.join(word.capitalize() for word in dep.split('-'))
                    logger.warning(f"Using default external name '{externals[dep]}' for dependency '{dep}'")
            
            # Create webpack.config.js
            webpack_config = f"""
const path = require('path');

module.exports = {{
    entry: './src/widget.js',
    output: {{
        path: path.resolve(__dirname, 'dist'),
        filename: 'widget.bundle.js',
        library: 'Widget_{widget_name}',
        libraryTarget: 'umd',
    }},
    module: {{
        rules: [
            {{
                test: /\\.jsx?$/,
                exclude: /node_modules/,
                use: {{
                    loader: 'babel-loader',
                    options: {{
                        presets: ['@babel/preset-env', '@babel/preset-react']
                    }}
                }}
            }}
        ]
    }},
    externals: {json.dumps(externals)},
    resolve: {{
        extensions: ['.js', '.jsx']
    }},
    optimization: {{
        minimize: true
    }}
}};
"""
            
            with open(os.path.join(temp_dir, 'webpack.config.js'), 'w') as f:
                f.write(webpack_config)
            
            # Create .babelrc
            babel_config = {
                "presets": ["@babel/preset-env", "@babel/preset-react"]
            }
            
            with open(os.path.join(temp_dir, '.babelrc'), 'w') as f:
                json.dump(babel_config, f, indent=2)
            
            # Create src directory and write widget code
            src_dir = os.path.join(temp_dir, 'src')
            os.makedirs(src_dir)
            
            # Create hook files if needed
            if hooks_needed:
                self._create_hook_files(temp_dir, hooks_needed)
                logger.info(f"Created {len(hooks_needed)} hook files for widget {widget_name}")
            
            # Handle exports intelligently
            wrapped_code = self._handle_exports(widget_code, widget_name)
            
            with open(os.path.join(src_dir, 'widget.js'), 'w') as f:
                f.write(wrapped_code)
            
            # Install dependencies - use --include=dev to ensure dev dependencies are installed
            logger.info(f"Installing dependencies for widget {widget_name}")
            install_result = subprocess.run(['npm', 'install', '--include=dev'], 
                                            env=env,
                                            cwd=temp_dir, 
                                            capture_output=True, 
                                            text=True)
            
            if install_result.returncode != 0:
                logger.error(f"npm install failed: {install_result.stderr}")
                return False, "", f"npm install failed: {install_result.stderr}"
            
            # Build with webpack
            logger.info(f"Building widget {widget_name}")
            build_result = subprocess.run(['npx', 'webpack', '--mode', 'production'], 
                                          env=env,
                                          cwd=temp_dir, 
                                          capture_output=True, 
                                          text=True)
            
            if build_result.returncode != 0:
                logger.error(f"webpack build failed: {build_result.stderr}")
                logger.info(f"Build output: {build_result.stdout}")
                return False, "", f"webpack build failed: {build_result.stderr}"
            
            # Read the built bundle
            bundle_path = os.path.join(temp_dir, 'dist', 'widget.bundle.js')
            with open(bundle_path, 'r') as f:
                built_code = f.read()
            
            # Wrap final code to make it available
            hooks_comment = f", Built-in hooks: {', '.join(hooks_needed)}" if hooks_needed else ""
            final_code = f"""
// Widget: {widget_name}
// Dependencies: {', '.join(dependencies) if dependencies else 'none'}
// External dependencies: {', '.join(external_dependencies) if external_dependencies else 'none'}{hooks_comment}
(function() {{
    {built_code}
    
    // Make the widget available globally
    window.{widget_name} = Widget_{widget_name}.default || Widget_{widget_name};
}})();
"""
            
            return True, final_code, ""
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed: {e.stderr}"
            logger.error(error_msg)
            return False, "", error_msg
        except Exception as e:
            logger.error(f"Error building widget: {str(e)}")
            return False, "", str(e)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def check_react_libraries(self, code):
        """
        Checks a React code fragment for library usage.
        
        Args:
            code (str): The React code to analyze
            
        Returns:
            dict: Analysis results with used libraries and their components
        """
        # Target libraries to check for
        target_libraries = [
            'recharts',
            'lodash', 
            'd3', 
            'axios', 
            'date-fns', 
            'lucide-react'
        ]
        
        # Find all import statements
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]*)/?.*?[\'"]'
        imports = re.findall(import_pattern, code)
        
        # Process imports to get base library names
        found_libraries = []
        other_libraries = []
        built_in_hooks = []
        
        for imp in imports:
            # Handle relative imports (hooks)
            if imp.startswith('./') or imp.startswith('../'):
                hook_name = imp.replace('./', '').replace('../', '').replace('.js', '').replace('.jsx', '')
                if hook_name in self.BUILT_IN_HOOKS:
                    built_in_hooks.append(hook_name)
                continue
                
            # Handle path imports like 'recharts/lib/something'
            base_lib = imp.split('/')[0]
            
            if base_lib in target_libraries and base_lib not in found_libraries:
                found_libraries.append(base_lib)
            elif (base_lib not in ['react', 'react-dom'] and 
                not base_lib.startswith('.') and 
                base_lib not in other_libraries):
                other_libraries.append(base_lib)
        
        # Generate warnings
        warnings = []
        if other_libraries:
            warnings.append(f"Found {len(other_libraries)} non-target libraries: {', '.join(other_libraries)}")
        
        return {
            'target_libraries': found_libraries,
            'other_libraries': other_libraries,
            'built_in_hooks': built_in_hooks,
            'warnings': warnings
        }
