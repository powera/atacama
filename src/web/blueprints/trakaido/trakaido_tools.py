"""Blueprint for serving Lithuanian language learning resources."""

# Standard library imports
import json
import os
import re
from typing import Any, Dict, List, Optional, Union

# Third-party imports
from flask import Blueprint, Response, abort, g, jsonify, request, send_file

# Local application imports
import constants
from web.decorators import optional_auth, require_auth
from .shared import *
from .userstats import user_has_activity_stats, USERSTATS_API_DOCS
from .userconfig import get_corpus_choices_file_path, CORPUSCHOICES_API_DOCS, LEVELPROGRESSION_API_DOCS
from .audio import AUDIO_API_DOCS

##############################################################################

USERINFO_API_DOCS = {
    "GET /api/trakaido/userinfo/": "Get user authentication status and basic info"
}

@trakaido_bp.route('/api/lithuanian')
def lithuanian_api_index() -> Response:
    """
    Provide an overview of the Lithuanian API endpoints.
    
    :return: JSON response with API information
    """
    api_info = {
        "name": "Lithuanian Language Learning API",
        "version": "1.0.0",
        "endpoints": {
            "audio": AUDIO_API_DOCS,
            "userstats": USERSTATS_API_DOCS,
            "corpuschoices": CORPUSCHOICES_API_DOCS,
            "levelprogression": LEVELPROGRESSION_API_DOCS,
            "userinfo": USERINFO_API_DOCS
        }
    }
    return jsonify(api_info)


@trakaido_bp.route('/api/trakaido/userinfo/')
@optional_auth
def get_user_info() -> Response:
    """
    Get user authentication status and basic information.
    
    This endpoint returns whether the user is logged in and can save
    journey stats and corpus choices. Used for app customization.
    
    :return: JSON response with user authentication status
    """
    try:
        # Check if user is authenticated by looking at the global context
        # The specific implementation depends on how authentication is handled
        is_authenticated = hasattr(g, 'user') and g.user is not None
        
        response_data = {
            "authenticated": is_authenticated,
            "can_save_journey_stats": is_authenticated,
            "can_save_corpus_choices": is_authenticated,
            "has_journey_stats_file": False,
            "has_corpus_choice_file": False
        }
        
        # If user is authenticated, add basic user info and check for existing files
        if is_authenticated:
            user_id = getattr(g.user, 'id', None) if hasattr(g.user, 'id') else None
            
            response_data["user"] = {
                "id": user_id,
                "username": getattr(g.user, 'username', None) if hasattr(g.user, 'username') else None,
                "email": getattr(g.user, 'email', None) if hasattr(g.user, 'email') else None
            }
            
            # Check if user has existing files
            if user_id:
                try:
                    language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
                    has_journey_stats = user_has_activity_stats(str(user_id), language)
                    corpus_choices_path = get_corpus_choices_file_path(str(user_id), language)

                    response_data["has_journey_stats_file"] = has_journey_stats
                    response_data["has_corpus_choice_file"] = os.path.exists(corpus_choices_path)
                except Exception as file_check_error:
                    logger.warning(f"Error checking user files for user {user_id}: {str(file_check_error)}")
                    # Keep defaults (False) if file check fails
        
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        return jsonify({
            "authenticated": False,
            "can_save_journey_stats": False,
            "can_save_corpus_choices": False,
            "has_journey_stats_file": False,
            "has_corpus_choice_file": False,
            "error": "Unable to determine authentication status"
        })
