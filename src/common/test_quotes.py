import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from web.blueprints.quotes import (
    extract_quotes,
    validate_quote,
    save_quotes,
    get_quotes_by_type,
    search_quotes,
    update_quote,
    delete_quote,
    QuoteExtractionError,
    QuoteValidationError,
    QUOTE_TYPES
)

class TestQuoteExtraction(unittest.TestCase):
    """Test quote extraction functionality."""
    
    def test_extract_yellow_tags(self):
        """Test extracting quotes from yellow tags."""
        content = "<yellow>Test quote"
        quotes = extract_quotes(content)
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["text"], "Test quote")
        self.assertEqual(quotes[0]["quote_type"], "reference")
    
    def test_multiple_quotes(self):
        """Test extracting multiple quotes of different types."""
        content = (
            '<yellow>First quote\n'
            '<quote>"Second quote" - Author\n'
            '<yellow>Third quote'
        )
        quotes = extract_quotes(content)
        self.assertEqual(len(quotes), 3)
        
    def test_invalid_content(self):
        """Test handling of invalid content."""
        with self.assertRaises(QuoteExtractionError):
            extract_quotes(None)

class TestQuoteValidation(unittest.TestCase):
    """Test quote validation functionality."""
    
    def test_valid_quote(self):
        """Test validation of valid quote data."""
        quote_data = {
            "text": "Test quote",
            "quote_type": "personal",
            "author": "Test Author"
        }
        is_valid, error = validate_quote(quote_data)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
    def test_missing_text(self):
        """Test validation with missing text."""
        quote_data = {
            "quote_type": "personal",
            "author": "Test Author"
        }
        is_valid, error = validate_quote(quote_data)
        self.assertFalse(is_valid)
        self.assertIn("required", error)
        
    def test_text_too_long(self):
        """Test validation with text exceeding length limit."""
        quote_data = {
            "text": "x" * 1001,
            "quote_type": "personal"
        }
        is_valid, error = validate_quote(quote_data)
        self.assertFalse(is_valid)
        self.assertIn("maximum length", error)
        
    def test_invalid_quote_type(self):
        """Test validation with invalid quote type."""
        quote_data = {
            "text": "Test quote",
            "quote_type": "invalid_type"
        }
        is_valid, error = validate_quote(quote_data)
        self.assertFalse(is_valid)
        self.assertIn("Invalid quote type", error)

class TestQuoteManagement(unittest.TestCase):
    """Test quote management functionality."""
    
    def setUp(self):
        """Set up test database session and mock objects."""
        self.session = Mock(spec=Session)
        self.email = Mock()
        self.email.quotes = []
    
    def test_save_new_quote(self):
        """Test saving a new quote."""
        quote_data = {
            "text": "Test quote",
            "quote_type": "personal",
            "author": "Test Author"
        }
        
        # Mock database query for existing quote
        self.session.query().filter().first.return_value = None
        
        save_quotes([quote_data], self.email, self.session)
        
        # Verify quote was added to email
        self.assertEqual(len(self.email.quotes), 1)
        self.assertEqual(self.email.quotes[0].text, "Test quote")
        
    def test_save_existing_quote(self):
        """Test saving a quote that already exists."""
        quote_data = {
            "text": "Test quote",
            "quote_type": "personal"
        }
        
        # Mock existing quote
        existing_quote = Mock()
        existing_quote.text = "Test quote"
        self.session.query().filter().first.return_value = existing_quote
        
        save_quotes([quote_data], self.email, self.session)
        
        # Verify existing quote was used
        self.assertEqual(len(self.email.quotes), 1)
        self.assertEqual(self.email.quotes[0], existing_quote)
        
    def test_get_quotes_by_type(self):
        """Test retrieving quotes filtered by type."""
        # Mock query results
        mock_quotes = [Mock(), Mock()]
        self.session.query().filter().order_by().all.return_value = mock_quotes
        
        result = get_quotes_by_type(self.session, "personal")
        self.assertEqual(result, mock_quotes)
        
    def test_search_quotes(self):
        """Test searching quotes."""
        # Mock query results
        mock_quotes = [Mock(), Mock()]
        self.session.query().filter().order_by().all.return_value = mock_quotes
        
        result = search_quotes(self.session, "test")
        self.assertEqual(result, mock_quotes)
        
    def test_update_quote(self):
        """Test updating an existing quote."""
        # Mock existing quote
        existing_quote = Mock()
        self.session.query().get.return_value = existing_quote
        
        quote_data = {
            "text": "Updated quote",
            "quote_type": "personal"
        }
        
        result = update_quote(self.session, 1, quote_data)
        self.assertEqual(result, existing_quote)
        self.assertEqual(existing_quote.text, "Updated quote")
        
    def test_delete_quote(self):
        """Test deleting a quote."""
        # Mock existing quote
        existing_quote = Mock()
        self.session.query().get.return_value = existing_quote
        
        result = delete_quote(self.session, 1)
        self.assertTrue(result)
        self.session.delete.assert_called_once_with(existing_quote)

if __name__ == '__main__':
    unittest.main()
