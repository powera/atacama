"""Blueprint for RSS feeds and sitemaps."""

import json
import html
import re
from datetime import datetime
from typing import Optional, List, Dict

from flask import (
    Blueprint, 
    request, 
    make_response,
    Response,
    render_template_string,
    jsonify
)
from sqlalchemy import select

from common.database import db
from common.models import Email
from common.channel_config import get_channel_manager, AccessLevel
from common.logging_config import get_logger

logger = get_logger(__name__)

feeds_bp = Blueprint('feeds', __name__)


@feeds_bp.route('/sitemap.xml')
def sitemap() -> Response:
    """
    Generate sitemap.xml containing all public URLs.
    
    :return: XML response containing sitemap
    """
    channel_manager = get_channel_manager()
    
    with db.session() as db_session:
        messages = db_session.query(Email).order_by(Email.created_at.desc()).all()
        urls = []
        base_url = request.url_root.rstrip('/')
        
        urls.append({
            'loc': f"{base_url}/",
            'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
        })
        
        # Add public channel pages
        for channel_name, config in channel_manager.channels.items():
            if config.access_level == AccessLevel.PUBLIC:
                urls.append({
                    'loc': f"{base_url}/stream/channel/{channel_name}",
                    'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
                })
        
        # Add public messages
        for message in messages:
            config = channel_manager.get_channel_config(message.channel)
            if config and config.access_level == AccessLevel.PUBLIC:
                urls.append({
                    'loc': f"{base_url}/messages/{message.id}",
                    'lastmod': message.created_at.strftime('%Y-%m-%d')
                })
        
        sitemap_xml = render_template_string('''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {%- for url in urls %}
    <url>
        <loc>{{ url.loc | e }}</loc>
        <lastmod>{{ url.lastmod }}</lastmod>
    </url>
    {%- endfor %}
</urlset>''', urls=urls)
        
        response = make_response(sitemap_xml)
        response.headers['Content-Type'] = 'application/xml'
        return response


@feeds_bp.route('/feed.xml')
@feeds_bp.route('/rss')
@feeds_bp.route('/channel/<path:channel>/feed.xml')
@feeds_bp.route('/<path:channel>.xml')
@feeds_bp.route('/feed-<path:channel>.xml')
def rss_feed(channel: Optional[str] = None) -> Response:
    """
    Generate RSS feed for public messages, optionally filtered by channel.
    
    :param channel: Optional channel name to filter by
    :return: XML response containing RSS feed
    """
    channel_manager = get_channel_manager()
    base_url = request.url_root.rstrip('/')
    site_title = "Atacama"
    
    # Filter by channel if specified
    if channel:
        config = channel_manager.get_channel_config(channel)
        if not config:
            return jsonify({'error': 'Channel not found'}), 404
        if config.access_level != AccessLevel.PUBLIC:
            return jsonify({'error': 'Channel is not public'}), 403
        site_title += f" - {config.get_display_name(channel)}"
        
    with db.session() as db_session:
        # Get recent public messages, optionally filtered by channel
        query = db_session.query(Email).order_by(Email.created_at.desc())
        
        if channel:
            query = query.filter(Email.channel == channel)
            
        messages = query.limit(20).all()
        
        # Filter for public messages
        public_messages = []
        for message in messages:
            config = channel_manager.get_channel_config(message.channel)
            if config and config.access_level == AccessLevel.PUBLIC:
                public_messages.append(message)
        
        # Process each message for RSS
        items = []
        for message in public_messages:
            # Convert HTML to RSS-friendly format
            content = clean_html_for_rss(message.processed_content)
            
            # Add author info if available
            author = ""
            if message.author:
                author = message.author.name
                
            items.append({
                'title': html.escape(message.subject or '(No Subject)'),
                'link': f"{base_url}/messages/{message.id}",
                'guid': f"{base_url}/messages/{message.id}",
                'pubDate': message.created_at.strftime('%a, %d %b %Y %H:%M:%S +0000'),
                'description': content,
                'author': html.escape(author) if author else None,
                'category': html.escape(message.channel)
            })
        
        # Prepare and render the RSS feed
        feed_description = "Recent messages from Atacama"
        if channel:
            feed_description += f" in the {channel} channel"
            
        rss_xml = render_template_string('''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel>
        <title>{{ title }}</title>
        <link>{{ link }}</link>
        <description>{{ description }}</description>
        <language>en-us</language>
        <lastBuildDate>{{ build_date }}</lastBuildDate>
        <atom:link href="{{ feed_link }}" rel="self" type="application/rss+xml" />
        
        {%- for item in items %}
        <item>
            <title>{{ item.title }}</title>
            <link>{{ item.link }}</link>
            <guid isPermaLink="true">{{ item.guid }}</guid>
            <pubDate>{{ item.pubDate }}</pubDate>
            <description>{{ item.description | safe }}</description>
            <content:encoded><![CDATA[{{ item.description | safe }}]]></content:encoded>
            <category>{{ item.category }}</category>
            {%- if item.author %}
            <author>{{ item.author }}</author>
            {%- endif %}
        </item>
        {%- endfor %}
    </channel>
</rss>''',
            title=site_title,
            link=f"{base_url}{'/stream/channel/' + channel if channel else ''}",
            description=feed_description,
            build_date=datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000'),
            feed_link=request.url,
            items=items
        )
        
        response = make_response(rss_xml)
        response.headers['Content-Type'] = 'application/rss+xml'
        return response


def clean_html_for_rss(html_content: str) -> str:
    """
    Clean HTML content for RSS feeds by handling color tags and other formatting.
    
    This implementation uses a more robust approach to handle nested tags
    without relying on BeautifulSoup to minimize dependencies.
    
    :param html_content: Original HTML content from processed message
    :return: Cleaned HTML suitable for RSS feeds
    """
    # Create a copy of the content to work with
    cleaned = html_content
    
    # Step 1: Process colorblocks - use a two-phase approach
    # First, extract the content and sigil together
    def process_colorblock(match):
        block = match.group(0)
        sigil = ""
        content = ""
        
        # Extract sigil
        sigil_match = re.search(r'<span class="sigil">(.*?)</span>', block)
        if sigil_match:
            sigil = sigil_match.group(1)
            
        # Extract content
        content_match = re.search(r'<span class="colortext-content">(.*?)</span>', block, re.DOTALL)
        if content_match:
            content = content_match.group(1)
            
        # Create a simplified representation with sigil and content
        return f'<span class="rss-cleaned">{sigil} {content}</span>'
    
    # Process color blocks
    pattern = r'<span class="colorblock.*?">.*?<span class="colortext-content">.*?</span>\s*</span>'
    cleaned = re.sub(pattern, process_colorblock, cleaned, flags=re.DOTALL)
    
    # Step 2: Handle inline color blocks (like <span class="color-red">...)
    def process_inline_color(match):
        block = match.group(0)
        content = re.sub(r'<[^>]*>', '', block)  # Strip HTML tags to get text content
        return content
    
    pattern = r'<span class="color-[^"]*">[^<]*</span>'
    cleaned = re.sub(pattern, process_inline_color, cleaned)
    
    # Step 3: Handle YouTube embeds
    def process_youtube(match):
        block = match.group(0)
        video_id_match = re.search(r'data-video-id="([^"]*)"', block)
        if video_id_match:
            video_id = video_id_match.group(1)
            return f'<p><a href="https://www.youtube.com/watch?v={video_id}">YouTube Video: {video_id}</a></p>'
        return ''
    
    # Find youtube players and replace them
    pattern = r'<span class="youtube-player"[^>]*>[^<]*</span>'
    cleaned = re.sub(pattern, process_youtube, cleaned)
    
    # Also handle the container
    pattern = r'<span class="colorblock youtube-embed-container">.*?</span>'
    cleaned = re.sub(pattern, process_youtube, cleaned, flags=re.DOTALL)
    
    # Step 4: Handle Chinese annotations
    def process_chinese(match):
        block = match.group(0)
        text_match = re.search(r'>([^<]+)</span>', block)
        if not text_match:
            return block
            
        text = text_match.group(1)
        
        pinyin = ""
        pinyin_match = re.search(r'data-pinyin="([^"]*)"', block)
        if pinyin_match:
            pinyin = pinyin_match.group(1)
            
        definition = ""
        definition_match = re.search(r'data-definition="([^"]*)"', block)
        if definition_match:
            definition = definition_match.group(1)
            
        result = text
        annotations = []
        if pinyin:
            annotations.append(f"pinyin: {pinyin}")
        if definition:
            annotations.append(f"def: {definition}")
            
        if annotations:
            result = f"{text} ({', '.join(annotations)})"
            
        return result
    
    pattern = r'<span class="annotated-chinese"[^>]*>[^<]*</span>'
    cleaned = re.sub(pattern, process_chinese, cleaned)
    
    # Step 5: Handle multi-line quotations
    def process_mlq(match):
        block = match.group(0)
        content_match = re.search(r'<div class="mlq-content">(.*?)</div>', block, re.DOTALL)
        if content_match:
            content = content_match.group(1)
            # Keep any HTML formatting within the content but wrap in blockquote
            return f'<blockquote>{content}</blockquote>'
        return ''
    
    pattern = r'<div class="mlq">.*?<div class="mlq-content">.*?</div>\s*</div>'
    cleaned = re.sub(pattern, process_mlq, cleaned, flags=re.DOTALL)
    
    # Step 6: Clean up any remaining "rss-cleaned" spans
    cleaned = re.sub(r'<span class="rss-cleaned">(.*?)</span>', r'\1', cleaned)
    
    # Step 7: Clean up any remaining button/control elements
    cleaned = re.sub(r'<button[^>]*>.*?</button>', '', cleaned, flags=re.DOTALL)
    
    # Step 8: Handle literal text blocks
    pattern = r'<span class="literal-text">(.*?)</span>'
    cleaned = re.sub(pattern, r'<code>\1</code>', cleaned)
    
    # Convert double line breaks to paragraph markers for better RSS display
    cleaned = re.sub(r'<br\s*/?>\s*<br\s*/?>', '</p><p>', cleaned)
    
    # Ensure content is wrapped in paragraphs for RSS readers
    if not cleaned.strip().startswith('<'):
        cleaned = f'<p>{cleaned}</p>'
    
    return cleaned