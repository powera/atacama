"""Split Email into Dispatch and Frame with content separation.

Revision ID: f42a81d93e15
Revises: bb8ea83c83cf
Create Date: 2025-01-08

This migration splits the Email model into Dispatch and Frame models,
using horizontal rules (----) to separate content into frames.
"""

from typing import List, Tuple
import re
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'f42a81d93e15'
down_revision = 'bb8ea83c83cf'
branch_labels = None
depends_on = None

def split_content(content: str, processed_content: str) -> List[Tuple[str, str]]:
    """Split content and processed_content at horizontal rules."""
    # Split raw content
    raw_parts = re.split(r'\n[ \t]*----[ \t]*\n', content)
    
    # Split processed content at <hr> tags
    processed_parts = re.split(r'<hr/?>', processed_content)
    
    # Ensure both lists have same length
    # If processed_content has fewer parts, pad with empty strings
    while len(processed_parts) < len(raw_parts):
        processed_parts.append('')
    
    # If processed_content has more parts, truncate
    processed_parts = processed_parts[:len(raw_parts)]
    
    return list(zip(raw_parts, processed_parts))

def upgrade():
    # Create frames table
    op.create_table(
        'frames',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('processed_content', sa.Text(), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('dispatch_id', sa.Integer(), nullable=False),
        sa.Column('chinese_annotations', sa.Text(), nullable=True),
        sa.Column('llm_annotations', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create frame_quotes association table
    op.create_table(
        'frame_quotes',
        sa.Column('frame_id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['frame_id'], ['frames.id']),
        sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'])
    )
    
    # Create temporary connection for data migration
    conn = op.get_bind()
    
    # Migrate data from emails to dispatches and frames
    # First, rename emails table to dispatches
    op.rename_table('emails', 'dispatches')
    
    # Add frames foreign key constraint after data migration
    op.create_foreign_key(
        'fk_frames_dispatch',
        'frames', 'dispatches',
        ['dispatch_id'], ['id']
    )
    
    # Get all existing emails/dispatches
    dispatches = conn.execute(
        'SELECT id, content, processed_content, chinese_annotations, llm_annotations FROM dispatches'
    ).fetchall()
    
    # For each dispatch, split content into frames
    for dispatch in dispatches:
        frames = split_content(dispatch.content, dispatch.processed_content)
        
        # Insert frames
        for i, (content, processed_content) in enumerate(frames):
            conn.execute(
                'INSERT INTO frames (content, processed_content, dispatch_id, created_at, '
                'chinese_annotations, llm_annotations, tags) VALUES (%s, %s, %s, NOW(), %s, %s, %s)',
                [content, processed_content, dispatch.id, 
                 dispatch.chinese_annotations, dispatch.llm_annotations, []]
            )
    
    # Remove content columns from dispatches
    #op.drop_column('dispatches', 'content')  # keep raw content for now
    op.drop_column('dispatches', 'processed_content')
    op.drop_column('dispatches', 'chinese_annotations')
    op.drop_column('dispatches', 'llm_annotations')
    
    # Migrate email_quotes to frame_quotes
    # For each email-quote association, create frame-quote associations for all frames
    quote_assocs = conn.execute('SELECT * FROM email_quotes').fetchall()
    
    # Rename email_quotes to dispatch_quotes for reference
    op.rename_table('email_quotes', 'dispatch_quotes')
    
    # For each quote association
    for assoc in quote_assocs:
        # Get all frames for this dispatch
        frames = conn.execute(
            'SELECT id FROM frames WHERE dispatch_id = %s',
            [assoc.email_id]
        ).fetchall()
        
        # Create frame-quote associations
        for frame in frames:
            conn.execute(
                'INSERT INTO frame_quotes (frame_id, quote_id, created_at) '
                'VALUES (%s, %s, %s)',
                [frame.id, assoc.quote_id, assoc.created_at]
            )
    
    # Drop the old dispatch_quotes table
    op.drop_table('dispatch_quotes')

def downgrade():
    # This is a complex migration that fundamentally changes the data structure
    # A full downgrade would be risky and potentially lossy
    raise NotImplementedError("Downgrade not supported for this migration")
