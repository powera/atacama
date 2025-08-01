from .models import (
    Base,
    Email,
    Quote,
    User,
    Message,
    MessageType,
    ReactWidget,
    Article,
    email_quotes
)

# Import database module
from .database import (
    Database,
    DatabaseError,
    db
)

# Import message-related functions
from .messages import (
    get_user_email_domain,
    check_admin_approval,
    check_channel_access,
    get_user_allowed_channels,
    check_message_access,
    get_message_by_id,
    get_message_chain,
    get_filtered_messages,
    get_domain_filtered_messages
)

# Import quote-related functions and constants
from .quotes import (
    QUOTE_TYPES,
    QuoteExtractionError,
    QuoteValidationError,
    generate_quote_metadata,
    validate_quote,
    save_quotes,
    get_quotes_by_type,
    search_quotes,
    update_quote,
    delete_quote
)

from .users import (
    get_or_create_user,
)

__all__ = [
    # Database models
    'Base', 'Email', 'Quote', 'User', 'Message', 'MessageType', 'ReactWidget', 'Article', 'email_quotes',
    
    # Database functionality
    'Database', 'DatabaseError', 'db',
    
    # Message functions
    'get_user_email_domain', 'check_admin_approval', 'check_channel_access', 'get_user_allowed_channels',
    'check_message_access', 'get_message_by_id', 'get_message_chain', 'get_filtered_messages', 'get_domain_filtered_messages',
    
    # Quote functions and constants
    'QUOTE_TYPES', 'QuoteExtractionError', 'QuoteValidationError', 'generate_quote_metadata', 'validate_quote',
    'save_quotes', 'get_quotes_by_type', 'search_quotes', 'update_quote', 'delete_quote',
    
    # User functions
    'get_or_create_user',
]