"""Language configuration management for Atacama."""

import os
from pathlib import Path
import tomli
from dataclasses import dataclass
from typing import Dict, List, Optional

import constants
from common.base.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class LanguageConfig:
    """Language configuration data structure."""
    name: str
    code: str
    subdomains: List[str]
    audio_dir_name: str
    character_set: str = ""

    def get_audio_dir(self) -> str:
        """
        Get the audio directory path for this language.

        :return: Path to the language's audio directory
        """
        base_dir = constants.get_trakaido_audio_base_dir()
        return os.path.join(base_dir, self.audio_dir_name)

class LanguageManager:
    """Manages language configuration and validation."""

    def __init__(self, config_path: str):
        """
        Initialize language manager with configuration file.

        :param config_path: Path to TOML configuration file
        """
        self.config_path = config_path
        self.languages: Dict[str, LanguageConfig] = {}
        self.subdomain_to_language: Dict[str, str] = {}  # Maps subdomains to language codes
        self.default_language = "lithuanian"
        self._load_config()

    def _load_config(self) -> None:
        """Load and validate language configuration from TOML file."""
        try:
            logger.info(f"Loading language configuration from {self.config_path}")
            with open(self.config_path, 'rb') as f:
                config = tomli.load(f)

            # Load default language
            defaults = config.get('defaults', {})
            self.default_language = defaults.get('default_language', 'lithuanian')

            # Load language configurations
            languages_config = config.get('languages', {})
            for language_key, settings in languages_config.items():
                self.languages[language_key] = LanguageConfig(
                    name=settings.get('name', language_key),
                    code=settings.get('code', language_key),
                    subdomains=settings.get('subdomains', []),
                    audio_dir_name=settings.get('audio_dir_name', language_key),
                    character_set=settings.get('character_set', '')
                )

                # Map each subdomain to this language
                for subdomain in settings.get('subdomains', []):
                    if subdomain in self.subdomain_to_language:
                        # Found duplicate subdomain
                        existing_language = self.subdomain_to_language[subdomain]
                        logger.error(f"Duplicate subdomain '{subdomain}' found in languages '{language_key}' and '{existing_language}'")
                        raise ValueError(f"Duplicate subdomain '{subdomain}' in multiple language configurations")
                    self.subdomain_to_language[subdomain] = language_key

            # Validate configuration
            self._validate_config()

            # Log successful initialization
            logger.info(f"Language configuration loaded successfully: {len(self.languages)} languages")
            for language_key, config in self.languages.items():
                logger.info(f"  Language '{language_key}': {config.name} ({config.code}), subdomains: {', '.join(config.subdomains)}")

        except Exception as e:
            logger.error(f"Error loading language configuration: {str(e)}")
            raise

    def _validate_config(self) -> None:
        """Validate language configuration for consistency."""
        if not self.languages:
            raise ValueError("No languages defined in configuration")

        if self.default_language not in self.languages:
            raise ValueError(f"Default language '{self.default_language}' not found in language list")

    def get_language_from_host(self, host: str) -> str:
        """
        Get language key for a host name based on subdomain.

        :param host: Host name from request
        :return: Language key from config, or default if not found
        """
        # Strip port from host if present
        if ':' in host:
            host = host.split(':', 1)[0]

        # Extract subdomain
        # Expected format: zh.example.com, fr.example.com, etc.
        parts = host.split('.')
        if len(parts) > 2:  # Has subdomain
            potential_subdomain = parts[0]
            if potential_subdomain in self.subdomain_to_language:
                language_key = self.subdomain_to_language[potential_subdomain]
                logger.debug(f"Subdomain match found: {potential_subdomain} -> {language_key}")
                return language_key

        # Fall back to default
        if host != "localhost" and len(parts) > 1:
            logger.debug(f"No language subdomain found for host: {host}, using default language")
        return self.default_language

    def get_language_config(self, language_key: str) -> LanguageConfig:
        """
        Get configuration for a language.

        :param language_key: Language key to get config for
        :return: Language configuration or default if not found
        """
        if language_key not in self.languages:
            logger.warning(f"Requested language '{language_key}' not found, using default")
            return self.languages[self.default_language]
        return self.languages[language_key]

    def get_all_language_keys(self) -> List[str]:
        """
        Get list of all configured language keys.

        :return: List of language keys
        """
        return list(self.languages.keys())

    def get_all_languages(self) -> Dict[str, LanguageConfig]:
        """
        Get all language configurations.

        :return: Dictionary of language configurations
        """
        return self.languages

# Default configuration file path
DEFAULT_CONFIG_PATH = Path(constants.CONFIG_DIR) / "languages.toml"

# Global language manager instance
_language_manager = None

def init_language_manager(config_path: Optional[str] = None) -> LanguageManager:
    """
    Initialize global language manager instance.

    :param config_path: Path to language configuration file
    :return: Language manager instance
    """
    global _language_manager
    config_path = config_path or DEFAULT_CONFIG_PATH
    logger.info(f"Initializing language manager with config path: {config_path}")
    _language_manager = LanguageManager(config_path)
    return _language_manager

def get_language_manager() -> LanguageManager:
    """
    Get global language manager instance.

    :return: Language manager instance
    :raises: RuntimeError if manager not initialized
    """
    global _language_manager
    if _language_manager is None:
        logger.info("Language manager not initialized, initializing with default config")
        _language_manager = LanguageManager(DEFAULT_CONFIG_PATH)
    return _language_manager
