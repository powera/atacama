"""Wordlist API handlers for Lithuanian language learning."""

# Standard library imports
import os
import random
import re
from typing import Union

# Third-party imports
from flask import Response, abort, jsonify, request, send_file

# Local application imports
import constants
from .shared import *


##############################################################################

# API Documentation for wordlists endpoints
WORDLISTS_API_DOCS = {
    "GET /api/lithuanian/wordlists": "List all wordlist corpora",
    "GET /api/lithuanian/wordlists/_all": "Get all words from all corpora",
    "GET /api/lithuanian/wordlists/levels": "Get all learning levels with their corpus/group references",
    "GET /api/lithuanian/wordlists/search": "Search for words (params: english, lithuanian, corpus, group)",
    "GET /api/lithuanian/wordlists/{corpus}": "List all groups in a corpus in a nested structure",
    "GET /api/lithuanian/wordlists/{corpus}?group={group_name}": "Get words for a specific group in a corpus"
}

# API Routes for wordlists
@trakaido_bp.route('/api/lithuanian/wordlists')
def list_wordlist_corpora() -> Union[Response, tuple]:
    """
    List all available wordlist corpora.
    
    :return: JSON response with list of corpora
    """
    try:
        corpora = get_wordlist_corpora()
        return jsonify({"corpora": corpora})
    except Exception as e:
        logger.error(f"Error listing wordlist corpora: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/lithuanian/wordlists/search')
def search_words() -> Union[Response, tuple]:
    """
    Search for words in the wordlists.
    
    Query parameters:
    - english: Search term for English words
    - lithuanian: Search term for Lithuanian words
    - corpus: Filter by corpus
    - group: Filter by group (requires corpus)
    
    :return: JSON response with matching words
    """
    try:
        english_term = request.args.get('english', '').lower()
        lithuanian_term = request.args.get('lithuanian', '').lower()
        corpus = request.args.get('corpus')
        group = request.args.get('group')
        
        if not english_term and not lithuanian_term:
            return jsonify({"error": "At least one search term (english or lithuanian) is required"}), 400
        
        # Get all words or filtered by corpus/group
        if corpus:
            words = get_words_by_corpus(corpus, group)
        else:
            words = get_all_word_pairs_flat()
        
        # Filter by search terms
        results = []
        for word in words:
            english_match = not english_term or english_term in word['english'].lower()
            lithuanian_match = not lithuanian_term or lithuanian_term in word['lithuanian'].lower()
            
            if english_match and lithuanian_match:
                results.append(word)
        
        return jsonify({
            "query": {
                "english": english_term,
                "lithuanian": lithuanian_term,
                "corpus": corpus,
                "group": group
            },
            "results": results,
            "count": len(results)
        })
    except Exception as e:
        logger.error(f"Error searching words: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/<corpus>')
def list_groups_in_corpus(corpus: str) -> Union[Response, tuple]:
    """
    List all groups in a corpus in a nested structure, or return words for a specific group.
    
    :param corpus: The corpus name
    :return: JSON response with groups in a nested structure or words for a specific group
    """
    try:
        groups = get_groups(corpus)
        if not groups:
            return jsonify({"error": f"Corpus '{corpus}' not found"}), 404
        
        # Check if a specific group is requested via query parameter
        requested_group = request.args.get('group')
        
        if requested_group:
            # Return words for the specific group
            words = get_words_by_corpus(corpus, requested_group)
            if not words:
                return jsonify({"error": f"Group '{requested_group}' not found in corpus '{corpus}'"}), 404
            
            return jsonify({
                "corpus": corpus,
                "group": requested_group,
                "words": words
            })
        
        # Return all groups in a nested structure
        result = {
            "corpus": corpus,
            "groups": {}
        }
        
        # Create a nested structure with group names and their words
        for group_name in groups:
            result["groups"][group_name] = all_words[corpus][group_name]
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error listing groups for {corpus}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/_all')
def get_all_words() -> Union[Response, tuple]:
    """
    Get all words from all corpora and groups.
    
    :return: JSON response with all words
    """
    try:
        words = get_all_word_pairs_flat()
        return jsonify({"words": words})
    except Exception as e:
        logger.error(f"Error getting all words: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/levels')
def get_levels() -> Union[Response, tuple]:
    """
    Get all learning levels with their corpus/group references.
    
    :return: JSON response with levels data
    """
    try:
        return jsonify({"levels": levels})
    except Exception as e:
        logger.error(f"Error getting levels: {str(e)}")
        return jsonify({"error": str(e)}), 500