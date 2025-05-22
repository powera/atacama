"""Tests for the domain_config module functionality."""

import unittest
import tempfile
import os
from pathlib import Path
import tomli
import tomli_w
from unittest.mock import patch, MagicMock

from common.config.domain_config import (
    ThemeConfig,
    DomainConfig,
    DomainManager,
    init_domain_manager,
    get_domain_manager
)

class TestThemeConfig(unittest.TestCase):
    """Test suite for ThemeConfig class."""
    
    def test_theme_config_initialization(self):
        """Test basic initialization of ThemeConfig."""
        theme = ThemeConfig(
            name="test_theme",
            css_files=["style.css", "custom.css"]
        )
        
        self.assertEqual(theme.name, "test_theme")
        self.assertEqual(theme.css_files, ["style.css", "custom.css"])
        self.assertEqual(theme.layout, "default")  # Default value
        self.assertFalse(theme.banner)  # Default value
    
    def test_theme_config_with_custom_values(self):
        """Test initialization with custom layout and banner values."""
        theme = ThemeConfig(
            name="custom_theme",
            css_files=["theme.css"],
            layout="two_column",
            banner=True
        )
        
        self.assertEqual(theme.name, "custom_theme")
        self.assertEqual(theme.css_files, ["theme.css"])
        self.assertEqual(theme.layout, "two_column")
        self.assertTrue(theme.banner)
    
    def test_theme_config_with_empty_css_files(self):
        """Test initialization with empty css_files list."""
        theme = ThemeConfig(
            name="minimal_theme",
            css_files=[]
        )
        
        self.assertEqual(theme.name, "minimal_theme")
        self.assertEqual(theme.css_files, [])
        self.assertEqual(theme.layout, "default")
        self.assertFalse(theme.banner)
    
    def test_theme_config_equality(self):
        """Test equality comparison of ThemeConfig objects."""
        theme1 = ThemeConfig(
            name="test_theme",
            css_files=["style.css"],
            layout="default",
            banner=False
        )
        
        theme2 = ThemeConfig(
            name="test_theme",
            css_files=["style.css"],
            layout="default",
            banner=False
        )
        
        theme3 = ThemeConfig(
            name="different_theme",
            css_files=["style.css"],
            layout="default",
            banner=False
        )
        
        # Dataclasses implement __eq__ by default
        self.assertEqual(theme1, theme2)
        self.assertNotEqual(theme1, theme3)

class TestDomainConfig(unittest.TestCase):
    """Test suite for DomainConfig class."""
    
    def test_domain_config_initialization(self):
        """Test basic initialization of DomainConfig."""
        domain = DomainConfig(
            name="test_domain",
            channels=["public", "private"],
            theme="default"
        )
        
        self.assertEqual(domain.name, "test_domain")
        self.assertEqual(domain.channels, ["public", "private"])
        self.assertEqual(domain.theme, "default")
        self.assertIsNone(domain.description)
        self.assertIsNone(domain.domains)
    
    def test_domain_config_with_optional_values(self):
        """Test initialization with optional values."""
        domain = DomainConfig(
            name="full_domain",
            channels=["public"],
            theme="custom",
            description="Test domain with all fields",
            domains=["example.com", "www.example.com"]
        )
        
        self.assertEqual(domain.name, "full_domain")
        self.assertEqual(domain.channels, ["public"])
        self.assertEqual(domain.theme, "custom")
        self.assertEqual(domain.description, "Test domain with all fields")
        self.assertEqual(domain.domains, ["example.com", "www.example.com"])
    
    def test_allows_all_channels_property(self):
        """Test allows_all_channels property with empty and non-empty channels list."""
        # Domain with specific channels
        domain_restricted = DomainConfig(
            name="restricted",
            channels=["public", "private"],
            theme="default"
        )
        self.assertFalse(domain_restricted.allows_all_channels)
        
        # Domain allowing all channels
        domain_all = DomainConfig(
            name="all_channels",
            channels=[],
            theme="default"
        )
        self.assertTrue(domain_all.allows_all_channels)
    
    def test_channel_allowed_method(self):
        """Test channel_allowed method with various scenarios."""
        # Domain with specific channels
        domain_restricted = DomainConfig(
            name="restricted",
            channels=["public", "private"],
            theme="default"
        )
        
        self.assertTrue(domain_restricted.channel_allowed("public"))
        self.assertTrue(domain_restricted.channel_allowed("private"))
        self.assertFalse(domain_restricted.channel_allowed("admin"))
        
        # Domain allowing all channels
        domain_all = DomainConfig(
            name="all_channels",
            channels=[],
            theme="default"
        )
        
        self.assertTrue(domain_all.channel_allowed("public"))
        self.assertTrue(domain_all.channel_allowed("private"))
        self.assertTrue(domain_all.channel_allowed("admin"))
        self.assertTrue(domain_all.channel_allowed("any_channel"))

class DomainManagerTestBase(unittest.TestCase):
    """Base class for domain manager tests with shared setup."""
    
    @classmethod
    def setUpClass(cls):
        """Create temporary config file for all tests."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.config_path = os.path.join(cls.temp_dir, "test_domains.toml")
        
        # Sample valid configuration
        cls.valid_config = {
            "themes": {
                "default": {
                    "name": "Default Theme",
                    "css_files": ["default.css"],
                    "layout": "default",
                    "banner": False
                },
                "custom": {
                    "name": "Custom Theme",
                    "css_files": ["custom.css", "extra.css"],
                    "layout": "two_column",
                    "banner": True
                }
            },
            "domains": {
                "default": {
                    "name": "Default Domain",
                    "channels": [],
                    "theme": "default",
                    "description": "Default domain configuration"
                },
                "restricted": {
                    "name": "Restricted Domain",
                    "channels": ["public", "private"],
                    "theme": "custom",
                    "description": "Domain with restricted channels",
                    "domains": ["restricted.example.com", "www.restricted.example.com"]
                }
            }
        }
        
        # Write valid config
        with open(cls.config_path, "wb") as f:
            tomli_w.dump(cls.valid_config, f)
            
    @classmethod
    def tearDownClass(cls):
        """Clean up temporary files."""
        try:
            os.unlink(cls.config_path)
            os.rmdir(cls.temp_dir)
        except Exception:
            pass

class TestDomainManager(DomainManagerTestBase):
    """Test DomainManager configuration loading and validation."""
    
    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        manager = DomainManager(self.config_path)
        
        # Check themes loaded correctly
        self.assertEqual(len(manager.themes), 2)
        self.assertIn("default", manager.themes)
        self.assertIn("custom", manager.themes)
        
        # Check domains loaded correctly
        self.assertEqual(len(manager.domains), 2)
        self.assertIn("default", manager.domains)
        self.assertIn("restricted", manager.domains)
        
        # Check host to domain mapping
        self.assertEqual(len(manager.host_to_domain), 2)
        self.assertEqual(manager.host_to_domain["restricted.example.com"], "restricted")
        self.assertEqual(manager.host_to_domain["www.restricted.example.com"], "restricted")
    
    def test_validate_config_no_domains(self):
        """Test validation fails when no domains are defined."""
        # Create config with no domains
        invalid_config = {
            "themes": self.valid_config["themes"],
            "domains": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.toml', delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name
        
        try:
            with self.assertRaises(ValueError) as context:
                DomainManager(invalid_path)
            self.assertIn("No domains defined", str(context.exception))
        finally:
            os.unlink(invalid_path)
    
    def test_validate_config_missing_default_domain(self):
        """Test validation fails when default domain is missing."""
        # Create config with no default domain
        invalid_config = {
            "themes": self.valid_config["themes"],
            "domains": {
                "custom": self.valid_config["domains"]["restricted"]
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.toml', delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name
        
        try:
            with self.assertRaises(ValueError) as context:
                DomainManager(invalid_path)
            self.assertIn("Default domain 'default' not found", str(context.exception))
        finally:
            os.unlink(invalid_path)
    
    def test_validate_config_invalid_theme_reference(self):
        """Test validation fails when domain references non-existent theme."""
        # Create a separate config for this test to avoid conflicts
        invalid_config = {
            "themes": {
                "default": {
                    "name": "Default Theme",
                    "css_files": ["default.css"],
                    "layout": "default",
                    "banner": False
                }
            },
            "domains": {
                "default": {
                    "name": "Default Domain",
                    "channels": [],
                    "theme": "nonexistent_theme",  # Invalid theme reference
                    "description": "Default domain configuration"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.toml', delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name
        
        try:
            with self.assertRaises(ValueError) as context:
                DomainManager(invalid_path)
            self.assertIn("Theme 'nonexistent_theme' referenced by domain 'default' not found", str(context.exception))
        finally:
            os.unlink(invalid_path)
    
    def test_duplicate_hostname(self):
        """Test validation fails when duplicate hostnames are found."""
        # Create a separate config for this test to avoid conflicts
        invalid_config = {
            "themes": {
                "default": {
                    "name": "Default Theme",
                    "css_files": ["default.css"],
                    "layout": "default",
                    "banner": False
                }
            },
            "domains": {
                "default": {
                    "name": "Default Domain",
                    "channels": [],
                    "theme": "default"
                },
                "domain1": {
                    "name": "Domain 1",
                    "channels": [],
                    "theme": "default",
                    "domains": ["duplicate.example.com"]
                },
                "domain2": {
                    "name": "Domain 2",
                    "channels": [],
                    "theme": "default",
                    "domains": ["duplicate.example.com"]  # Duplicate hostname
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.toml', delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name
        
        try:
            with self.assertRaises(ValueError) as context:
                DomainManager(invalid_path)
            self.assertIn("Duplicate hostname", str(context.exception))
        finally:
            os.unlink(invalid_path)
    
    def test_get_domain_for_host_direct_match(self):
        """Test get_domain_for_host with direct hostname match."""
        manager = DomainManager(self.config_path)
        
        # Direct match
        self.assertEqual(
            manager.get_domain_for_host("restricted.example.com"),
            "restricted"
        )
    
    def test_get_domain_for_host_with_www(self):
        """Test get_domain_for_host with and without www prefix."""
        manager = DomainManager(self.config_path)
        
        # With www prefix when registered with www
        self.assertEqual(
            manager.get_domain_for_host("www.restricted.example.com"),
            "restricted"
        )
    
    def test_get_domain_for_host_with_www_prefix(self):
        """Test get_domain_for_host with www prefix when domain is registered without it."""
        # Create a separate config for this test
        config_with_non_www = {
            "themes": {
                "default": {
                    "name": "Default Theme",
                    "css_files": ["default.css"],
                    "layout": "default",
                    "banner": False
                }
            },
            "domains": {
                "default": {
                    "name": "Default Domain",
                    "channels": [],
                    "theme": "default"
                },
                "non_www": {
                    "name": "Non-WWW Domain",
                    "channels": [],
                    "theme": "default",
                    "domains": ["example.org"]  # Without www
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.toml', delete=False) as f:
            tomli_w.dump(config_with_non_www, f)
            non_www_path = f.name
        
        try:
            manager = DomainManager(non_www_path)
            
            # Test with www when registered without
            self.assertEqual(
                manager.get_domain_for_host("www.example.org"),
                "non_www"
            )
        finally:
            os.unlink(non_www_path)
    
    def test_get_domain_for_host_with_port(self):
        """Test get_domain_for_host with hostname containing port."""
        manager = DomainManager(self.config_path)
        
        # Hostname with port
        self.assertEqual(
            manager.get_domain_for_host("restricted.example.com:8080"),
            "restricted"
        )
    
    def test_get_domain_for_host_legacy_match(self):
        """Test get_domain_for_host with legacy domain key match."""
        # Create a separate config for this test to avoid conflicts
        legacy_config = {
            "themes": {
                "default": {
                    "name": "Default Theme",
                    "css_files": ["default.css"],
                    "layout": "default",
                    "banner": False
                }
            },
            "domains": {
                "default": {
                    "name": "Default Domain",
                    "channels": [],
                    "theme": "default"
                },
                "example.net": {
                    "name": "Legacy Domain",
                    "channels": [],
                    "theme": "default"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.toml', delete=False) as f:
            tomli_w.dump(legacy_config, f)
            legacy_path = f.name
        
        try:
            manager = DomainManager(legacy_path)
            
            # Legacy match (domain key is the hostname)
            self.assertEqual(
                manager.get_domain_for_host("example.net"),
                "example.net"
            )
        finally:
            os.unlink(legacy_path)
    
    def test_get_domain_for_host_default_fallback(self):
        """Test get_domain_for_host falls back to default domain."""
        manager = DomainManager(self.config_path)
        
        # Unknown hostname falls back to default
        self.assertEqual(
            manager.get_domain_for_host("unknown.example.com"),
            "default"
        )
    
    def test_get_domain_config(self):
        """Test get_domain_config returns correct configuration."""
        manager = DomainManager(self.config_path)
        
        # Get existing domain
        domain_config = manager.get_domain_config("restricted")
        self.assertEqual(domain_config.name, "Restricted Domain")
        self.assertEqual(domain_config.theme, "custom")
        
        # Get non-existent domain (falls back to default)
        domain_config = manager.get_domain_config("nonexistent")
        self.assertEqual(domain_config.name, "Default Domain")
        self.assertEqual(domain_config.theme, "default")
    
    def test_get_theme_config(self):
        """Test get_theme_config returns correct configuration."""
        manager = DomainManager(self.config_path)
        
        # Get existing theme
        theme_config = manager.get_theme_config("custom")
        self.assertEqual(theme_config.name, "Custom Theme")
        self.assertEqual(theme_config.css_files, ["custom.css", "extra.css"])
        self.assertEqual(theme_config.layout, "two_column")
        self.assertTrue(theme_config.banner)
        
        # Get non-existent theme (falls back to default)
        theme_config = manager.get_theme_config("nonexistent")
        self.assertEqual(theme_config.name, "Default Theme")
        self.assertEqual(theme_config.css_files, ["default.css"])
    
    def test_get_allowed_channels(self):
        """Test get_allowed_channels returns correct channel list."""
        manager = DomainManager(self.config_path)
        
        # Domain with restricted channels
        channels = manager.get_allowed_channels("restricted")
        self.assertEqual(channels, ["public", "private"])
        
        # Domain allowing all channels
        channels = manager.get_allowed_channels("default")
        self.assertIsNone(channels)
    
    def test_is_channel_allowed(self):
        """Test is_channel_allowed returns correct permission."""
        manager = DomainManager(self.config_path)
        
        # Domain with restricted channels
        self.assertTrue(manager.is_channel_allowed("restricted", "public"))
        self.assertTrue(manager.is_channel_allowed("restricted", "private"))
        self.assertFalse(manager.is_channel_allowed("restricted", "admin"))
        
        # Domain allowing all channels
        self.assertTrue(manager.is_channel_allowed("default", "public"))
        self.assertTrue(manager.is_channel_allowed("default", "private"))
        self.assertTrue(manager.is_channel_allowed("default", "admin"))

class TestDomainManagerSingleton(DomainManagerTestBase):
    """Test global domain manager instance handling."""
    
    def test_init_domain_manager(self):
        """Test initialization of global domain manager instance."""
        # Clear any existing instance
        import common.config.domain_config
        common.config.domain_config._domain_manager = None
        
        # Initialize with config
        manager1 = init_domain_manager(self.config_path)
        self.assertIsNotNone(manager1)
        
        # Should return the same instance
        manager2 = get_domain_manager()
        self.assertIs(manager1, manager2)
    
    def test_get_domain_manager_auto_init(self):
        """Test get_domain_manager auto-initializes if needed."""
        # Clear any existing instance
        import common.config.domain_config
        common.config.domain_config._domain_manager = None
        
        # Mock DEFAULT_CONFIG_PATH to use our test config
        with patch('common.config.domain_config.DEFAULT_CONFIG_PATH', Path(self.config_path)):
            # Should auto-initialize
            manager = get_domain_manager()
            self.assertIsNotNone(manager)
            self.assertIsInstance(manager, DomainManager)
            
            # Second call should return same instance
            manager2 = get_domain_manager()
            self.assertIs(manager, manager2)
    
    def test_reinitialize_domain_manager(self):
        """Test that reinitializing domain manager creates a new instance."""
        # Clear any existing instance
        import common.config.domain_config
        common.config.domain_config._domain_manager = None
        
        # Initialize with config
        manager1 = init_domain_manager(self.config_path)
        # Convert both to strings for comparison to avoid Path vs string issues
        self.assertEqual(str(manager1.config_path), str(self.config_path))
        
        # Initialize again with a different config (should create a new instance)
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.toml', delete=False) as f:
            tomli_w.dump(self.valid_config, f)
            another_config_path = f.name
            
        try:
            manager2 = init_domain_manager(another_config_path)
            
            # Should be a different instance with the new config path
            self.assertIsNot(manager1, manager2)
            self.assertEqual(str(manager2.config_path), str(another_config_path))
            
            # get_domain_manager should now return the new instance
            manager3 = get_domain_manager()
            self.assertIs(manager2, manager3)
        finally:
            os.unlink(another_config_path)

if __name__ == '__main__':
    unittest.main()