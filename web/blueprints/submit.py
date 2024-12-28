from flask import Blueprint, request, render_template, url_for, redirect
from sqlalchemy.orm import joinedload
import logging
from typing import List

from common.database import setup_database
Session, db_success = setup_database()

from common.models import Email
from common.colorscheme import ColorScheme
from .auth import require_auth

submit_bp = Blueprint('submit', __name__)

@submit_bp.route('/submit', methods=['POST'])
def submit_message():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400

    message = data['message']
    # Process the message here
    return jsonify({'status': 'Message received', 'message': message}), 200


@submit_bp.route('/process', methods=['POST'])
@require_auth
def process_message() -> tuple[Dict[str, Any], int]:
    """API endpoint to process and store messages."""
    try:
        data = request.get_json()
        
        if not data or 'subject' not in data or 'content' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        session = Session()
        
        # Process content with enhanced features
        processed_content = color_processor.process_content(
            data['content'],
            llm_annotations=data.get('llm_annotations')
        )
        
        # Create message object
        message = Email(
            subject=data['subject'],
            content=data['content'],
            processed_content=processed_content,
            llm_annotations=json.dumps(data.get('llm_annotations', {}))
        )
        
        # Handle message chain if parent_id is provided
        if 'parent_id' in data:
            parent = session.query(Email).get(data['parent_id'])
            if parent:
                message.parent = parent
        
        # Extract and save quotes
        quotes = extract_quotes(data['content'])
        save_quotes(quotes, message, session)
        
        session.add(message)
        session.commit()
        
        logger.info(f"Processed message with subject: {data['subject']}")
        
        return jsonify({
            'id': message.id,
            'processed_content': processed_content,
            'view_url': url_for('get_message', message_id=message.id)
        }), 201
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()



@submit_bp.route('/submit', methods=['GET', 'POST'])
@require_auth
def submit_form():
    """Handle message submission via HTML form."""
    if request.method == 'POST':
        try:
            subject = request.form.get('subject', '')
            content = request.form.get('content', '')
            parent_id = request.form.get('parent_id')
            
            if not subject or not content:
                return render_template('submit.html', error='Subject and content are required')
                
            session = Session()
            processed_content = color_processor.process_content(content)
            
            message = Email(
                subject=subject,
                content=content,
                processed_content=processed_content,
            )
            
            # Handle message chain if parent_id is provided
            if parent_id and parent_id.strip():
                try:
                    parent_id = int(parent_id)
                    parent = session.query(Email).get(parent_id)
                    if parent:
                        message.parent = parent
                    else:
                        logger.warning(f"Parent message {parent_id} not found")
                except ValueError:
                    logger.warning(f"Invalid parent_id format: {parent_id}")
            
            # Extract and save quotes
            quotes = extract_quotes(content)
            save_quotes(quotes, message, session)
            
            session.add(message)
            session.commit()
            
            view_url = url_for('get_message', message_id=message.id)
            return render_template('submit.html', success=True, view_url=view_url)
            
        except Exception as e:
            logger.error(f"Error processing form submission: {str(e)}")
            return render_template('submit.html', error=str(e))
            
        finally:
            session.close()
        # END of processing submission of message by POST
            
    # Get recent messages for the dropdown
    session = Session()
    try:
        recent_messages = session.query(Email).order_by(
            Email.created_at.desc()
        ).limit(50).all()
    except Exception as e:
        logger.error(f"Error fetching recent messages: {str(e)}")
        recent_messages = []
    finally:
        session.close()
    return render_template('submit.html', recent_messages=recent_messages)

