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
    jsonify,
    g,
    abort
)
from sqlalchemy import select

from common.database import db
from common.models import Email
from common.channel_config import get_channel_manager, AccessLevel
from common.domain_config import get_domain_manager
from common.logging_config import get_logger

logger = get_logger(__name__)

feeds_bp = Blueprint('feeds', __name__)


@feeds_bp.route('/sitemap.xml')
def sitemap() -> Response:
    """
    Generate sitemap.xml containing all public URLs for the current domain.
    
    :return: XML response containing sitemap
    """
    channel_manager = get_channel_manager()
    domain_manager = get_domain_manager()
    current_domain = g.current_domain
    domain_config = domain_manager.get_domain_config(current_domain)
    
    with db.session() as db_session:
        messages = db_session.query(Email).order_by(Email.created_at.desc()).all()
        urls = []
        base_url = request.url_root.rstrip('/')
        
        urls.append({
            'loc': f"{base_url}/",
            'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
        })
        
        # Add public channel pages that are allowed on this domain
        for channel_name, config in channel_manager.channels.items():
            if (config.access_level == AccessLevel.PUBLIC and 
                domain_manager.is_channel_allowed(current_domain, channel_name)):
                urls.append({
                    'loc': f"{base_url}/stream/channel/{channel_name}",
                    'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
                })
        
        # Add public messages that are allowed on this domain
        for message in messages:
            config = channel_manager.get_channel_config(message.channel)
            if (config and config.access_level == AccessLevel.PUBLIC and 
                domain_manager.is_channel_allowed(current_domain, message.channel)):
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
    domain_manager = get_domain_manager()
    current_domain = g.current_domain
    domain_config = domain_manager.get_domain_config(current_domain)
    
    base_url = request.url_root.rstrip('/')
    site_title = domain_config.name or "Atacama"
    
    # Filter by channel if specified
    if channel:
        # Check if channel is allowed on this domain
        if not domain_manager.is_channel_allowed(current_domain, channel):
            return abort(404, f"Channel not available on this domain")
        
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
        
        # Filter for public messages that are allowed on this domain
        public_messages = []
        for message in messages:
            config = channel_manager.get_channel_config(message.channel)
            if (config and config.access_level == AccessLevel.PUBLIC and 
                domain_manager.is_channel_allowed(current_domain, message.channel)):
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
        feed_description = f"Recent messages from {site_title}"
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
    
    :param html_content: Original HTML content from processed message
    :return: Cleaned HTML suitable for RSS feeds
    """
    # Create a copy of the content to work with
    cleaned = html_content
    
    # Replace color blocks with their content or appropriate representation
    def expand_color_block(match):
        # Extract the content within the colorblock
        full_match = match.group(0)
        content_match = re.search(r'<span class="colortext-content">(.*?)</span>', full_match, re.DOTALL)
        sigil_match = re.search(r'<span class="sigil">(.*?)</span>', full_match, re.DOTALL)
        
        if content_match:
            # Get the color class
            color_class_match = re.search(r'class="colorblock color-(.*?)"', full_match)
            color_name = color_class_match.group(1) if color_class_match else "unknown"
            
            # Find the sigil for this color (emoji)
            sigil = ""
            if sigil_match:
                sigil = sigil_match.group(1)
            
            # Extract the content
            content = content_match.group(1)
            
            # Format as [color_name: content] with sigil
            return f"{sigil} {content}"
        return full_match
    
    # Replace colorblocks with their content
    cleaned = re.sub(r'<span class="colorblock.*?">.*?<span class="colortext-content">.*?</span>\s*</span>', 
                     expand_color_block, cleaned, flags=re.DOTALL)
    
    # Handle YouTube embeds
    def handle_youtube_embed(match):
        video_id_match = re.search(r'data-video-id="(.*?)"', match.group(0))
        if video_id_match:
            video_id = video_id_match.group(1)
            return f'<p><a href="https://www.youtube.com/watch?v={video_id}">YouTube Video: {video_id}</a></p>'
        return ''
    
    cleaned = re.sub(r'<span class="youtube-player".*?</span>', handle_youtube_embed, cleaned)
    
    # Handle Chinese annotations
    def handle_chinese_annotation(match):
        # Extract Chinese characters and any annotations
        chinese = match.group(0)
        pinyin_match = re.search(r'data-pinyin="(.*?)"', chinese)
        definition_match = re.search(r'data-definition="(.*?)"', chinese)
        
        # Extract the Chinese text
        text_match = re.search(r'>([^<]+)</span>', chinese)
        
        if text_match:
            text = text_match.group(1)
            annotations = []
            
            if pinyin_match:
                annotations.append(f"pinyin: {pinyin_match.group(1)}")
            if definition_match:
                annotations.append(f"def: {definition_match.group(1)}")
                
            if annotations:
                return f"{text} ({', '.join(annotations)})"
            return text
        return match.group(0)
    
    cleaned = re.sub(r'<span class="annotated-chinese".*?</span>', handle_chinese_annotation, cleaned)
    
    # Multi-line quotations
    def handle_mlq(match):
        # Extract the content from the MLQ
        content_match = re.search(r'<div class="mlq-content">(.*?)</div>', match.group(0), re.DOTALL)
        if content_match:
            return f'<blockquote>{content_match.group(1)}</blockquote>'
        return ''
    
    cleaned = re.sub(r'<div class="mlq">.*?<div class="mlq-content">.*?</div>\s*</div>', 
                     handle_mlq, cleaned, flags=re.DOTALL)
    
    return cleaned