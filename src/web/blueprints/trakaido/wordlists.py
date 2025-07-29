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
    "GET /api/lithuanian/wordlists/_all": "Get all words from all corpora (includes alternatives)",
    "GET /api/lithuanian/wordlists/levels": "Get all learning levels with their corpus/group references",
    "GET /api/lithuanian/wordlists/search": "Search for words including alternatives (params: english, lithuanian, corpus, group)",
    "GET /api/lithuanian/wordlists/{corpus}": "List all groups in a corpus in a nested structure (includes alternatives)",
    "GET /api/lithuanian/wordlists/{corpus}?group={group_name}": "Get words for a specific group in a corpus (includes alternatives)",
    "GET /api/trakaido/lithuanian/wordlists": "Get wordlists with optional corpus and level filtering (includes alternatives, CGI params: corpus, level)"
}

# NEW API

# Helper function to optimize word data by removing empty fields
def optimize_word_data(word: dict) -> dict:
    """
    Optimize word data by removing empty alternatives and other unnecessary fields.
    
    :param word: Word dictionary to optimize
    :return: Optimized word dictionary
    """
    optimized = word.copy()
    
    # Remove empty alternatives
    if 'alternatives' in optimized:
        alternatives = optimized['alternatives']
        if (not alternatives.get('english') and not alternatives.get('lithuanian')):
            del optimized['alternatives']
        else:
            # Keep alternatives but remove empty lists
            cleaned_alternatives = {}
            if alternatives.get('english'):
                cleaned_alternatives['english'] = alternatives['english']
            if alternatives.get('lithuanian'):
                cleaned_alternatives['lithuanian'] = alternatives['lithuanian']
            optimized['alternatives'] = cleaned_alternatives
    
    # Remove empty metadata fields
    if 'metadata' in optimized:
        metadata = optimized['metadata']
        if not any(metadata.values()) or metadata == {}:
            del optimized['metadata']
        else:
            # Remove empty metadata subfields
            cleaned_metadata = {}
            for key, value in metadata.items():
                if value or value == 0:  # Keep 0 values but not empty strings/lists
                    cleaned_metadata[key] = value
            if cleaned_metadata:
                optimized['metadata'] = cleaned_metadata
            else:
                del optimized['metadata']
    
    return optimized

# Helper function to find which level(s) a word belongs to based on corpus and group
def find_word_levels(corpus: str, group: str) -> list:
    """
    Find which level(s) a word belongs to based on its corpus and group.
    
    :param corpus: The corpus name
    :param group: The group name
    :return: List of level names that contain this corpus/group combination
    """
    word_levels = []
    for level_name, level_items in levels.items():
        for level_item in level_items:
            if level_item["corpus"] == corpus and level_item["group"] == group:
                word_levels.append(level_name)
                break  # Each level can only contain a corpus/group combination once
    return word_levels

# Helper function to get all word pairs in a flat structure (basic format for backward compatibility)
def get_words_by_level(level_name: str) -> list:
    """
    Get all words for a specific level with basic fields only.
    
    This function provides backward compatibility for existing API endpoints.
    
    :param level_name: The level name (e.g., "level_1")
    :return: List of word objects with basic fields only
    """
    if level_name not in levels:
        return []
    
    level_words = []
    for level_item in levels[level_name]:
        corpus = level_item["corpus"]
        group = level_item["group"]
        
        if corpus in all_words and group in all_words[corpus]:
            # Extract only basic fields for backward compatibility
            for word_pair in all_words[corpus][group]:
                basic_word = {
                    'english': word_pair['english'],
                    'lithuanian': word_pair['lithuanian']
                }
                level_words.append(basic_word)
    
    return level_words

# New unified API endpoint
@trakaido_bp.route('/api/trakaido/lithuanian/wordlists')
def get_wordlists() -> Union[Response, tuple]:
    """
    Get wordlists with optional filtering by corpus or level.
    
    Query parameters:
    - corpus: Filter by specific corpus (e.g., "nouns_one")
    - level: Filter by specific level (e.g., "level_1")
    
    Default behavior: Returns all words from all corpora and groups.
    
    :return: JSON response with words in enhanced format
    """
    try:
        corpus = request.args.get('corpus')
        level = request.args.get('level')
        
        # Determine which words to return based on parameters
        if level:
            # Filter by level - use enhanced format
            words = get_words_by_level_enhanced(level)
            if not words:
                return jsonify({"error": f"Level '{level}' not found"}), 404
            
            # Add level information to each word and optimize
            optimized_words = []
            for word in words:
                word_levels = find_word_levels(word['corpus'], word['group'])
                word['levels'] = word_levels
                optimized_words.append(optimize_word_data(word))
            
            return jsonify({
                "level": level,
                "words": optimized_words,
                "count": len(optimized_words)
            })
        
        elif corpus:
            # Filter by corpus - use enhanced format
            if corpus not in all_words:
                return jsonify({"error": f"Corpus '{corpus}' not found"}), 404
            
            # Get all words from all groups in this corpus with enhanced format
            corpus_words = []
            for group_name, group_words in all_words[corpus].items():
                word_levels = find_word_levels(corpus, group_name)
                for word_pair in group_words:
                    enhanced_word = word_pair.copy()
                    enhanced_word['corpus'] = corpus
                    enhanced_word['group'] = group_name
                    enhanced_word['levels'] = word_levels
                    corpus_words.append(optimize_word_data(enhanced_word))
            
            return jsonify({
                "corpus": corpus,
                "words": corpus_words,
                "count": len(corpus_words)
            })
        
        else:
            # Default: return all words with enhanced format including levels
            all_words_flat = get_all_word_pairs_flat()
            # Add level information to each word and optimize
            optimized_words = []
            for word in all_words_flat:
                word_levels = find_word_levels(word['corpus'], word['group'])
                word['levels'] = word_levels
                optimized_words.append(optimize_word_data(word))
            
            return jsonify({
                "words": optimized_words,
                "count": len(optimized_words)
            })
    
    except Exception as e:
        logger.error(f"Error getting wordlists: {str(e)}")
        return jsonify({"error": str(e)}), 500

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
        
        # Get all words with enhanced format (includes alternatives)
        if corpus:
            # For corpus filtering, we need to get enhanced format
            if corpus not in all_words:
                words = []
            elif group:
                if group not in all_words[corpus]:
                    words = []
                else:
                    # Get words for specific group with enhanced format
                    words = []
                    for word_pair in all_words[corpus][group]:
                        enhanced_word = word_pair.copy()
                        enhanced_word['corpus'] = corpus
                        enhanced_word['group'] = group
                        words.append(enhanced_word)
            else:
                # Get all words from all groups in this corpus with enhanced format
                words = []
                for group_name, group_words in all_words[corpus].items():
                    for word_pair in group_words:
                        enhanced_word = word_pair.copy()
                        enhanced_word['corpus'] = corpus
                        enhanced_word['group'] = group_name
                        words.append(enhanced_word)
        else:
            words = get_all_word_pairs_flat()
        
        # Filter by search terms (including alternatives)
        results = []
        for word in words:
            english_match = False
            lithuanian_match = False
            
            if not english_term:
                english_match = True
            else:
                # Check main english word
                if english_term in word['english'].lower():
                    english_match = True
                # Check english alternatives
                elif 'alternatives' in word and 'english' in word['alternatives']:
                    for alt in word['alternatives']['english']:
                        if english_term in alt.lower():
                            english_match = True
                            break
            
            if not lithuanian_term:
                lithuanian_match = True
            else:
                # Check main lithuanian word
                if lithuanian_term in word['lithuanian'].lower():
                    lithuanian_match = True
                # Check lithuanian alternatives
                elif 'alternatives' in word and 'lithuanian' in word['alternatives']:
                    for alt in word['alternatives']['lithuanian']:
                        if lithuanian_term in alt.lower():
                            lithuanian_match = True
                            break
            
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
            # Return words for the specific group with enhanced format (including alternatives)
            if requested_group not in all_words[corpus]:
                return jsonify({"error": f"Group '{requested_group}' not found in corpus '{corpus}'"}), 404
            
            enhanced_words = []
            for word_pair in all_words[corpus][requested_group]:
                enhanced_word = word_pair.copy()
                enhanced_word['corpus'] = corpus
                enhanced_word['group'] = requested_group
                enhanced_words.append(enhanced_word)
            
            return jsonify({
                "corpus": corpus,
                "group": requested_group,
                "words": enhanced_words
            })
        
        # Return all groups in a nested structure (basic format for backward compatibility)
        result = {
            "corpus": corpus,
            "groups": {}
        }
        
        # Create a nested structure with group names and their words (enhanced format with alternatives)
        for group_name in groups:
            enhanced_words = []
            for word_pair in all_words[corpus][group_name]:
                enhanced_word = word_pair.copy()
                enhanced_word['corpus'] = corpus
                enhanced_word['group'] = group_name
                enhanced_words.append(enhanced_word)
            result["groups"][group_name] = enhanced_words
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error listing groups for {corpus}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/_all')
def get_all_words() -> Union[Response, tuple]:
    """
    Get all words from all corpora and groups with enhanced format (including alternatives).
    
    :return: JSON response with all words in enhanced format
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