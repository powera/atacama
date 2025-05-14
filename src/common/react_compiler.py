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
        
        # Verify npm is actually executable
        self._verify_npm_installation()
    
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
    
    def _verify_npm_installation(self):
        """Verify that npm is properly installed and executable."""
        try:
            # Check if npm path exists
            if not os.path.exists(self.npm_path):
                raise RuntimeError(f"NPM path does not exist: {self.npm_path}")
            
            # Check if npm is executable
            if not os.access(self.npm_path, os.X_OK):
                raise RuntimeError(f"NPM is not executable: {self.npm_path}")
            
            # Try to run npm version
            result = subprocess.run([self.npm_path, '--version'], 
                                  capture_output=True, text=True, check=True)
            npm_version = result.stdout.strip()
            logger.info(f"NPM version: {npm_version}")
            
            # Try to run npx version
            result = subprocess.run([self.npx_path, '--version'], 
                                  capture_output=True, text=True, check=True)
            npx_version = result.stdout.strip()
            logger.info(f"NPX version: {npx_version}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to verify npm installation: {e}")
            logger.error(f"Stdout: {e.stdout}")
            logger.error(f"Stderr: {e.stderr}")
            raise RuntimeError(f"NPM verification failed: {e}")
        except Exception as e:
            logger.error(f"NPM verification error: {e}")
            raise
    
    def _get_npm_environment(self) -> dict:
        """Get a minimal, secure environment for running npm commands."""
        return {
            'HOME': os.path.expanduser('~'),
            'USER': os.environ.get('USER', 'atacama'),
            'PATH': '/usr/local/bin:/usr/bin:/bin',
            'NODE_ENV': 'production',
            # Only include what npm actually needs
            'LANG': os.environ.get('LANG', 'en_US.UTF-8'),
            'LC_ALL': os.environ.get('LC_ALL', 'C.UTF-8'),
        }
    
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
            logger.info(f"Installing dependencies for widget {widget_name} using npm at: {self.npm_path}")
            try:
                # Use minimal, secure environment for npm
                npm_env = self._get_npm_environment()
                
                result = subprocess.run([self.npm_path, 'install'], 
                                      cwd=temp_dir, 
                                      check=True, 
                                      capture_output=True, 
                                      text=True,
                                      env=npm_env)
                logger.debug(f"NPM install stdout: {result.stdout}")
            except subprocess.CalledProcessError as e:
                logger.error(f"NPM install failed with exit code {e.returncode}")
                logger.error(f"NPM install stderr: {e.stderr}")
                logger.error(f"NPM install stdout: {e.stdout}")
                raise
            
            # Build with webpack using full npx path
            logger.info(f"Building widget {widget_name} using npx at: {self.npx_path}")
            try:
                # Use same minimal environment
                result = subprocess.run([self.npx_path, 'webpack', '--mode', 'production'], 
                                      cwd=temp_dir, 
                                      check=True, 
                                      capture_output=True, 
                                      text=True,
                                      env=npm_env)
                logger.debug(f"Webpack build stdout: {result.stdout}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Webpack build failed with exit code {e.returncode}")
                logger.error(f"Webpack build stderr: {e.stderr}")
                logger.error(f"Webpack build stdout: {e.stdout}")
                raise
            
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