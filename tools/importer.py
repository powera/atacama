#!/usr/bin/python3
"""WordPress XML export importer for Atacama."""

import argparse
import os
import sys
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
import json

# Add the src directory to the path so we can import from the project
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

import constants
from common.database import db
from common.models import Email, User
from common.channel_config import get_channel_manager, AccessLevel
from common.logging_config import get_logger, configure_logging
from common.openai_client import generate_chat, generate_text
import aml_parser.lexer
import aml_parser.parser
import aml_parser.html_generator

# Initialize system for database access
constants.init_production()
configure_logging()
logger = get_logger(__name__)

# Namespaces used in WordPress XML
WP_NAMESPACES = {
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'wp': 'http://wordpress.org/export/1.2/',
    'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}

# Dictionary to map old formatting to Atacama tags
TAG_MAPPING = {
    # Map WordPress tags to Atacama color tags
    '/xantham': '<xantham>',
    '/red': '<red>',
    '/orange': '<orange>',
    '/yellow': '<yellow>',
    '/quote': '<quote>',
    '/green': '<green>',
    '/teal': '<teal>',
    '/blue': '<blue>',
    '/violet': '<violet>',
    '/music': '<music>',
    '/mogue': '<mogue>',
    '/gray': '<gray>',
    '/grey': '<gray>',
    '/hazel': '<hazel>',
}

# Sensitive topics that should default to private
SENSITIVE_TOPICS = [
    "sex", "sexual", "drugs", "politics", "religion", "controversial", 
    "private", "personal", "sensitive", "nsfw", "adult", "opinion"
]

def strip_numeric_suffix(tag: str) -> str:
    """
    Remove any trailing numbers from tag names.
    
    :param tag: The original tag
    :return: Tag with numeric suffix removed
    """
    return re.sub(r'(\D+)\d+$', r'\1', tag)

def clean_gutenberg_blocks(content: str) -> str:
    """
    Clean WordPress Gutenberg blocks from content.
    
    :param content: Original post content with Gutenberg blocks
    :return: Cleaned content
    """
    # Remove WordPress Gutenberg comment blocks
    content = re.sub(r'<!-- wp:.*?-->', '', content)
    content = re.sub(r'<!-- /wp:.*?-->', '', content)
    
    # Convert HTML paragraphs to plain text paragraphs
    content = re.sub(r'<p>(.*?)</p>', r'\1\n\n', content)
    
    # Remove other common HTML tags
    content = re.sub(r'</?[a-z][^>]*>', '', content)
    
    # Fix double newlines
    content = re.sub(r'\n{3,}', '\n\n', content)
   
    # Replace "more" tag with Atacama equivalent
    content = re.sub(r'<!--\s*more\s*-->', '--MORE--', content)

    # Trim whitespace
    content = content.strip()
    
    return content

def normalize_tags(content: str) -> str:
    """
    Normalize tag formats from WordPress to Atacama format.
    
    :param content: Original post content
    :return: Content with normalized tags
    """
    # First clean Gutenberg blocks
    content = clean_gutenberg_blocks(content)
    
    # hack for mogue324
    content = content.replace("mogue324", "mogue")
    # Replace old-style tags with Atacama color tags
    for old_tag, new_tag in TAG_MAPPING.items():
        content = content.replace(old_tag, new_tag)
    
    # Remove any trailing numbers from tags
    def repl(match):
        tag_name = match.group(1)
        normalized = strip_numeric_suffix(tag_name)
        return f"<{normalized}>"
    
    content = re.sub(r'<(\w+\d+)>', repl, content)
    
    return content

def determine_channel_by_content(title: str, content: str, categories: List[str], tags: List[str]) -> str:
    """
    Determine appropriate channel based on post content and metadata.
    
    :param title: Post title
    :param content: Post content
    :param categories: Post categories
    :param tags: Post tags
    :return: Channel name to use
    """
    # Get available channels
    channel_manager = get_channel_manager()
    available_channels = channel_manager.get_channel_names()
    
    # Try to use LLM for channel determination
    try:
        prompt = f"""
        Analyze this blog post and determine the most appropriate channel category from the following options:
        {', '.join(available_channels)}
        
        Post Title: {title}
        Categories: {', '.join(categories)}
        Tags: {', '.join(tags)}
        
        Content snippet: {content[:500]}...
        
        Select only one channel from the options provided. If none fit well, respond with either "private" (if the content 
        contains sensitive topics like sex, drugs, politics, controversial opinions, etc.) or "miscellaneous" (for general content).
        Respond with just the channel name, nothing else.
        """
        
        channel, _, _ = generate_chat(prompt)
        channel = channel.strip().lower()
        
        # Validate the returned channel
        if channel in available_channels:
            logger.info(f"LLM determined channel: {channel}")
            return channel
            
        # Check if content is sensitive for default fallback
        content_sample = content.lower()
        title_lower = title.lower()
        is_sensitive = any(topic in content_sample or topic in title_lower for topic in SENSITIVE_TOPICS)
        
        if is_sensitive:
            logger.info("Content contains sensitive topics, defaulting to private channel")
            return "private"
        else:
            if "miscellaneous" in available_channels:
                return "miscellaneous"
            else:
                return channel_manager.default_channel
                
    except Exception as e:
        logger.error(f"Error determining channel: {str(e)}")
        # Fall back to default channel
        return channel_manager.default_channel

def handle_indented_text(content: str) -> str:
    """
    Convert WordPress indented text to appropriate Atacama format.
    
    :param content: Original post content
    :return: Content with converted indentation formatting
    """
    # Find indented blocks (wrapped in <blockquote> or with multiple spaces)
    indented_pattern = re.compile(r'<blockquote>(.*?)</blockquote>', re.DOTALL)
    
    def convert_to_mlq(match):
        text = match.group(1).strip()
        paragraphs = re.split(r'\n\s*\n', text)
        return f'```.mlq\n{chr(10).join(paragraphs)}\n```'
    
    # Replace blockquotes with multi-line quotes
    content = indented_pattern.sub(convert_to_mlq, content)
    
    return content

def is_duplicate_post(title: str, content: str) -> bool:
    """
    Check if a post with similar title and content already exists.
    
    :param title: Post title
    :param content: Post content
    :return: True if duplicate detected, False otherwise
    """
    try:
        with db.session() as session:
            # Check for exact title match
            existing = session.query(Email).filter(Email.subject == title).first()
            if existing:
                logger.info(f"Post with title '{title}' already exists")
                return True
                
            # Check for content similarity (simplistic approach)
            # In a real implementation, you might want more sophisticated duplicate detection
            content_sample = content[:100]  # Use first 100 chars as fingerprint
            existing = session.query(Email).filter(Email.content.like(f"{content_sample}%")).first()
            if existing:
                logger.info(f"Post with similar content already exists: '{title}'")
                return True
                
            return False
    except Exception as e:
        logger.error(f"Error checking for duplicates: {str(e)}")
        return False

def import_post(
    title: str,
    content: str, 
    post_date: datetime,
    categories: List[str],
    tags: List[str],
    author_email: str,
    author_name: str,
    interactive: bool = False
) -> bool:
    """
    Import a WordPress post into Atacama.
    
    :param title: Post title
    :param content: Post content
    :param post_date: Original publication date
    :param categories: Post categories
    :param tags: Post tags
    :param author_email: Author's email
    :param author_name: Author's display name
    :param interactive: Whether to prompt for approval
    :return: True if import successful, False otherwise
    """
    try:
        # Normalize content
        normalized_content = normalize_tags(content)
        normalized_content = handle_indented_text(normalized_content)
        
        # Check for duplicates
        if is_duplicate_post(title, normalized_content):
            logger.warning(f"Skipping duplicate post: {title}")
            return False
            
        # Determine channel
        channel = determine_channel_by_content(title, normalized_content, categories, tags)
        
        # Interactive approval
        if interactive:
            print("\n" + "="*80)
            print(f"Post: {title}")
            print(f"Date: {post_date}")
            print(f"Channel: {channel}")
            print(f"Categories: {', '.join(categories)}")
            print(f"Tags: {', '.join(tags)}")
            print("-"*80)
            print(normalized_content[:500] + "..." if len(normalized_content) > 500 else normalized_content)
            print("-"*80)
            
            response = input("Import this post? (y/n/edit): ").lower()
            
            if response == 'n':
                logger.info(f"Skipping post by user request: {title}")
                return False
            elif response == 'edit':
                new_channel = input(f"Enter new channel (current: {channel}): ")
                if new_channel and new_channel in get_channel_manager().get_channel_names():
                    channel = new_channel
        
        # Create user record if needed
        with db.session() as session:
            # Create mock session user for get_or_create_user
            session_user = {"email": author_email, "name": author_name}
            from common.models import get_or_create_user
            user = get_or_create_user(session, session_user)
            
            # Create email post
            email = Email(
                subject=title,
                content=normalized_content,
                processed_content="",  # Will be processed by the system
                created_at=post_date,
                channel=channel,
                author_id=user.id
            )
            email.processed_content = aml_parser.html_generator.generate_html(
                aml_parser.parser.parse(aml_parser.lexer.tokenize(normalized_content)))

            session.add(email)
            session.commit()
            
            logger.info(f"Imported post: {title} (id: {email.id}, channel: {channel})")
            return True
            
    except Exception as e:
        logger.error(f"Error importing post '{title}': {str(e)}")
        return False

def parse_wordpress_xml(xml_file: str, interactive: bool = False) -> Tuple[int, int]:
    """
    Parse WordPress XML export and import posts.
    
    :param xml_file: Path to WordPress XML export file
    :param interactive: Whether to prompt for approval of each post
    :return: Tuple of (successful_imports, total_posts)
    """
    try:
        logger.info(f"Parsing WordPress XML file: {xml_file}")
        
        # Parse the XML file
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Find the channel element
        channel = root.find('channel')
        if not channel:
            logger.error("Invalid WordPress XML: No channel element found")
            return 0, 0
            
        # Find all item elements (posts)
        items = channel.findall('item')
        
        successful_imports = 0
        total_posts = 0
        
        # Process each post
        for item in items:
            # Check if this is a post (not a page or attachment)
            post_type = item.find('./wp:post_type', WP_NAMESPACES)
            if post_type is None or post_type.text != 'post':
                logger.info("Skipping non-post item")
                continue
                
            # Get post status
            status = item.find('./wp:status', WP_NAMESPACES)
            if status is None or status.text != 'publish':
                logger.info("Skipping unpublished post")
                continue
                
            total_posts += 1
            
            # Extract post details
            title_elem = item.find('title')
            title = title_elem.text if title_elem is not None else "Untitled"
            
            content_elem = item.find('./content:encoded', WP_NAMESPACES)
            content = content_elem.text if content_elem is not None else ""
            
            # Extract post date
            pub_date = item.find('pubDate')
            if pub_date is not None and pub_date.text:
                try:
                    post_date = datetime.strptime(pub_date.text, '%a, %d %b %Y %H:%M:%S %z')
                except ValueError:
                    post_date = datetime.utcnow()
            else:
                post_date = datetime.utcnow()
                
            # Extract categories and tags
            categories = []
            tags = []
            
            for cat in item.findall('category'):
                domain = cat.get('domain', '')
                if domain == 'category':
                    categories.append(cat.text)
                elif domain == 'post_tag':
                    tags.append(cat.text)
                    
            # Extract author info
            creator = item.find('./dc:creator', WP_NAMESPACES)
            author_name = creator.text if creator is not None else "Unknown"
            
            # Use a default email or extract it if available
            author_email = f"{author_name.lower().replace(' ', '.')}@imported.local"
            
            # Import the post
            if import_post(
                title=title,
                content=content,
                post_date=post_date,
                categories=categories,
                tags=tags,
                author_email=author_email,
                author_name=author_name,
                interactive=interactive
            ):
                successful_imports += 1
                
        logger.info(f"Import complete. Imported {successful_imports} of {total_posts} posts.")
        return successful_imports, total_posts
        
    except Exception as e:
        logger.error(f"Error parsing WordPress XML: {str(e)}")
        return 0, 0

def main():
    """Main entry point for the WordPress importer tool."""
    parser = argparse.ArgumentParser(description='Import WordPress XML export into Atacama')
    parser.add_argument('xml_file', help='Path to WordPress XML export file')
    parser.add_argument('--interactive', '-i', action='store_true', help='Enable interactive mode with approval for each post')
    args = parser.parse_args()
    
    if not os.path.isfile(args.xml_file):
        print(f"Error: File not found: {args.xml_file}")
        return 1
        
    print(f"Starting WordPress import from: {args.xml_file}")
    print(f"Interactive mode: {'Enabled' if args.interactive else 'Disabled'}")
    
    successful, total = parse_wordpress_xml(args.xml_file, args.interactive)
    
    print(f"Import complete. Successfully imported {successful} of {total} posts.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
