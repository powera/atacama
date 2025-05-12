#!/usr/bin/env python3
"""Interactive function to regenerate processed content for emails with diff display and approval."""

import difflib
from typing import Optional
from sqlalchemy.orm import Session

from common.database import db
from common.models import Email
from parser.lexer import tokenize
from parser.parser import parse
from parser.html_generator import generate_html


def regenerate_email_content(
    email_id: int, 
    db_session: Optional[Session] = None,
    show_diff: bool = True,
    auto_approve: bool = False
) -> bool:
    """
    Regenerate the processed content for an email and optionally update the database.
    
    :param email_id: ID of the email to regenerate
    :param db_session: Optional database session (will create one if not provided)
    :param show_diff: Whether to display the diff between old and new content
    :param auto_approve: If True, automatically approve changes without prompting
    :return: True if the email was updated, False otherwise
    """
    # Handle database session
    if db_session is None:
        with db.session() as session:
            return regenerate_email_content(email_id, session, show_diff, auto_approve)
    
    # Fetch the email
    email = db_session.query(Email).filter_by(id=email_id).first()
    if not email:
        print(f"Error: Email with ID {email_id} not found")
        return False
    
    print(f"Regenerating content for email ID {email_id}: {email.subject or '(No Subject)'}")
    
    # Store the old processed content
    old_content = email.processed_content
    
    # Regenerate the content using the parser pipeline
    try:
        # Tokenize
        tokens = tokenize(email.content)
        
        # Parse
        ast = parse(iter(tokens))
        
        # Generate HTML
        new_content = generate_html(
            ast, 
            db_session=db_session, 
            message=email,
            truncated=False
        )
        
    except Exception as e:
        print(f"Error regenerating content: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check if content has changed
    if old_content == new_content:
        print("No changes in processed content")
        return False
    
    # Show diff if requested
    if show_diff:
        print("\n=== DIFF ===")
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile="old_content.html",
            tofile="new_content.html",
            lineterm=""
        )
        
        # Colorize diff output if terminal supports it
        try:
            import sys
            if sys.stdout.isatty():
                for line in diff:
                    if line.startswith('+'):
                        print(f"\033[92m{line}\033[0m", end='')  # Green
                    elif line.startswith('-'):
                        print(f"\033[91m{line}\033[0m", end='')  # Red
                    elif line.startswith('@'):
                        print(f"\033[95m{line}\033[0m", end='')  # Magenta
                    else:
                        print(line, end='')
            else:
                print(''.join(diff))
        except:
            print(''.join(diff))
        
        print("\n=== END DIFF ===\n")
    
    # Show statistics
    old_lines = len(old_content.splitlines())
    new_lines = len(new_content.splitlines())
    print(f"Statistics:")
    print(f"  Old content: {len(old_content)} chars, {old_lines} lines")
    print(f"  New content: {len(new_content)} chars, {new_lines} lines")
    print(f"  Change: {len(new_content) - len(old_content):+d} chars, {new_lines - old_lines:+d} lines")
    
    # Prompt for approval if not auto-approving
    if not auto_approve:
        print("\nDo you want to update the database with the new content?")
        response = input("Enter 'yes' or 'y' to confirm, anything else to cancel: ").strip().lower()
        
        if response not in ('yes', 'y'):
            print("Update cancelled")
            return False
    
    # Update the database
    try:
        email.processed_content = new_content
        db_session.commit()
        print(f"Successfully updated email ID {email_id}")
        return True
    except Exception as e:
        db_session.rollback()
        print(f"Error updating database: {e}")
        return False


def regenerate_multiple_emails(
    email_ids: list[int],
    show_diff: bool = False,
    auto_approve: bool = False
) -> tuple[int, int]:
    """
    Regenerate multiple emails in a batch.
    
    :param email_ids: List of email IDs to regenerate
    :param show_diff: Whether to show diffs for each email
    :param auto_approve: If True, automatically approve all changes
    :return: Tuple of (updated_count, total_count)
    """
    updated = 0
    total = len(email_ids)
    
    print(f"Processing {total} emails...")
    
    with db.session() as session:
        for i, email_id in enumerate(email_ids, 1):
            print(f"\n[{i}/{total}] Processing email ID {email_id}...")
            
            if regenerate_email_content(email_id, session, show_diff, auto_approve):
                updated += 1
            
            print(f"Progress: {updated} updated out of {i} processed")
    
    print(f"\nCompleted: {updated} emails updated out of {total} total")
    return updated, total


# Interactive helper functions for common use cases
def regenerate_recent_emails(limit: int = 10, auto_approve: bool = False):
    """
    Regenerate the most recent emails.
    
    :param limit: Number of recent emails to process
    :param auto_approve: If True, automatically approve all changes
    """
    with db.session() as session:
        emails = session.query(Email)\
            .order_by(Email.created_at.desc())\
            .limit(limit)\
            .all()
        
        email_ids = [email.id for email in emails]
        
    print(f"Found {len(email_ids)} recent emails")
    regenerate_multiple_emails(email_ids, show_diff=False, auto_approve=auto_approve)


def regenerate_by_channel(channel: str, auto_approve: bool = False):
    """
    Regenerate all emails in a specific channel.
    
    :param channel: Channel name
    :param auto_approve: If True, automatically approve all changes
    """
    with db.session() as session:
        emails = session.query(Email)\
            .filter_by(channel=channel)\
            .order_by(Email.created_at.desc())\
            .all()
        
        email_ids = [email.id for email in emails]
        
    print(f"Found {len(email_ids)} emails in channel '{channel}'")
    regenerate_multiple_emails(email_ids, show_diff=False, auto_approve=auto_approve)


if __name__ == "__main__":
    # Example usage when run directly
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python regenerate_email.py <email_id>")
        print("   or: python regenerate_email.py recent [limit]")
        print("   or: python regenerate_email.py channel <channel_name>")
        sys.exit(1)
    
    if sys.argv[1] == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        regenerate_recent_emails(limit)
    elif sys.argv[1] == "channel":
        if len(sys.argv) < 3:
            print("Error: channel name required")
            sys.exit(1)
        regenerate_by_channel(sys.argv[2])
    else:
        email_id = int(sys.argv[1])
        regenerate_email_content(email_id)
