import os
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Tuple, List, Optional

from common.logging_config import get_logger
logger = get_logger(__name__)

class WidgetBuilder:
    """Builds React widgets with proper bundling for browser use."""
    
    # Available packages that can be bundled
    AVAILABLE_PACKAGES = {
        'recharts': '^2.12.7',
        'lodash': '^4.17.21',
        'axios': '^1.6.0',
        'd3': '^7.8.5',
        'chart.js': '^4.4.1',
        'date-fns': '^3.0.0',
        'react-chartjs-2': '^5.2.0',
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
        'chart.js': 'Chart',
        'axios': 'axios',
        'date-fns': 'dateFns',
        'react-chartjs-2': 'ReactChartJS2',
        'lucide-react': 'lucideReact'
    }

    def __init__(self, build_dir: str = None):
        self.build_dir = build_dir or os.path.join(tempfile.gettempdir(), 'widget_builds')
        Path(self.build_dir).mkdir(parents=True, exist_ok=True)
        
        # Find system NPM and NPX paths
        self.npm_path = self._find_system_command('npm')
        self.npx_path = self._find_system_command('npx')
        
        if not self.npm_path:
            raise RuntimeError("npm not found in system PATH. Please install Node.js.")
        if not self.npx_path:
            raise RuntimeError("npx not found in system PATH. Please install Node.js.")
    
    def _find_system_command(self, command: str) -> Optional[str]:
        """Find the full path to a system command."""
        # Common locations for npm/npx
        common_paths = [
            f'/usr/bin/{command}',
            f'/usr/local/bin/{command}',
            f'/opt/node/bin/{command}',
            f'/opt/nodejs/bin/{command}',
            os.path.expanduser(f'~/.nvm/current/bin/{command}'),
        ]
        
        # Check common paths first
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                logger.info(f"Found {command} at: {path}")
                return path
        
        # Fallback to using which/whereis
        try:
            result = subprocess.run(['/usr/bin/which', command], 
                                  capture_output=True, text=True, check=True)
            path = result.stdout.strip()
            if path and os.path.exists(path):
                logger.info(f"Found {command} using which: {path}")
                return path
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Try whereis as last resort
        try:
            result = subprocess.run(['/usr/bin/whereis', command], 
                                  capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            # whereis output format: "command: /path/to/command"
            if ':' in output:
                paths = output.split(':', 1)[1].split()
                for path in paths:
                    if os.path.exists(path) and os.access(path, os.X_OK):
                        logger.info(f"Found {command} using whereis: {path}")
                        return path
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        logger.warning(f"Could not find {command} in system PATH")
        return None
    
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
            
            # Wrap the widget code to export it properly
            wrapped_code = f"""
{widget_code}

// Export the component
export default {widget_name};
"""
            
            with open(os.path.join(src_dir, 'widget.js'), 'w') as f:
                f.write(wrapped_code)
            
            # Install dependencies using full npm path
            logger.info(f"Installing dependencies for widget {widget_name}")
            subprocess.run([self.npm_path, 'install'], cwd=temp_dir, check=True, capture_output=True)
            
            # Build with webpack using full npx path
            logger.info(f"Building widget {widget_name}")
            subprocess.run([self.npx_path, 'webpack', '--mode', 'production'], cwd=temp_dir, check=True, capture_output=True)
            
            # Read the built bundle
            bundle_path = os.path.join(temp_dir, 'dist', 'widget.bundle.js')
            with open(bundle_path, 'r') as f:
                built_code = f.read()
            
            # Wrap final code to make it available
            external_deps_comment = f", External: {', '.join(external_dependencies)}" if external_dependencies else ""
            final_code = f"""
// Widget: {widget_name}
// Dependencies: {', '.join(dependencies) if dependencies else 'none'}
// External dependencies: {', '.join(external_dependencies) if external_dependencies else 'none'}
(function() {{
    {built_code}
    
    // Make the widget available globally
    window.{widget_name} = Widget_{widget_name}.default || Widget_{widget_name};
}})();
"""
            
            return True, final_code, ""
            
        except Exception as e:
            return False, "", str(e)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)