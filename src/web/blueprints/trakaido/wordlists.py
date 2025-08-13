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
    "GET /api/trakaido/lithuanian/wordlists": "Get wordlists with optional corpus and level filtering (includes alternatives and GUIDs, CGI params: corpus, level)"
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

# Noun corpus to level ranges mapping (used for backward compatibility and fallback)
NOUN_CORPUS_LEVEL_RANGES = {
    'nouns_one': range(1, 4),    # levels 1-3
    'nouns_two': range(4, 8),    # levels 4-7
    'nouns_three': range(8, 12), # levels 8-11
    'nouns_four': range(12, 17), # levels 12-16
    'nouns_five': range(17, 21),  # levels 17-20
    'nouns_six': range(21, 25)   # levels 21-24 (also used as fallback for dynamic overflow)
}

# Helper function to map noun levels to corpus names
def get_noun_corpus_name(level_name: str) -> str:
    """
    Map noun level names to corpus names for API consistency.
    
    :param level_name: The level name (e.g., "level_1")
    :return: Corpus name (e.g., "nouns_one")
    """
    if not level_name.startswith('level_'):
        return level_name
    
    try:
        level_num = int(level_name.split('_')[1])
        if 1 <= level_num <= 3:
            return "nouns_one"
        elif 4 <= level_num <= 7:
            return "nouns_two"
        elif 8 <= level_num <= 11:
            return "nouns_three"
        elif 12 <= level_num <= 16:
            return "nouns_four"
        elif 17 <= level_num <= 20:
            return "nouns_five"
        else:
            return level_name
    except (ValueError, IndexError):
        return level_name

# Dynamic corpus mapping cache
_dynamic_corpus_cache = {}

def get_dynamic_corpus_name(level_name: str, group_name: str) -> str:
    """
    Get the dynamic corpus name for a group based on its level and previous occurrences.
    
    If a group appears in multiple levels, each occurrence gets assigned to a progressively
    higher corpus level to avoid conflicts. Uses nouns_six as fallback for overflow.
    
    :param level_name: The level name (e.g., "level_10")
    :param group_name: The group name (e.g., "food_drink")
    :return: Dynamic corpus name (e.g., "nouns_four")
    """
    global _dynamic_corpus_cache
    
    if not level_name.startswith('level_'):
        return level_name
    
    # Initialize cache if empty
    if not _dynamic_corpus_cache:
        _build_dynamic_corpus_cache()
    
    # Return cached result
    cache_key = f"{level_name}:{group_name}"
    return _dynamic_corpus_cache.get(cache_key, get_noun_corpus_name(level_name))

def _build_dynamic_corpus_cache():
    """
    Build the dynamic corpus mapping cache by analyzing all groups across levels.
    
    This function scans all levels to find groups that appear multiple times and assigns
    them to different corpus levels to avoid conflicts.
    """
    global _dynamic_corpus_cache
    _dynamic_corpus_cache = {}
    
    # Track group occurrences: group_name -> [(level_num, level_name), ...]
    group_occurrences = {}
    
    # Scan all levels to find group occurrences
    for level_num in range(1, 25):  # Extended range to handle potential overflow
        level_name = f"level_{level_num}"
        if level_name in all_words:
            for group_name in all_words[level_name].keys():
                if group_name not in group_occurrences:
                    group_occurrences[group_name] = []
                group_occurrences[group_name].append((level_num, level_name))
    
    # Corpus names in order of preference
    corpus_names = ["nouns_one", "nouns_two", "nouns_three", "nouns_four", "nouns_five", "nouns_six"]
    
    # Assign corpus names to groups
    for group_name, occurrences in group_occurrences.items():
        # Sort occurrences by level number
        occurrences.sort(key=lambda x: x[0])
        
        if len(occurrences) == 1:
            # Single occurrence - use default mapping
            level_num, level_name = occurrences[0]
            default_corpus = get_noun_corpus_name(level_name)
            _dynamic_corpus_cache[f"{level_name}:{group_name}"] = default_corpus
        else:
            # Multiple occurrences - assign to different corpus levels
            for i, (level_num, level_name) in enumerate(occurrences):
                # Determine base corpus index from the first occurrence
                first_level_num = occurrences[0][0]
                base_corpus = get_noun_corpus_name(f"level_{first_level_num}")
                
                # Find base corpus index
                try:
                    base_index = corpus_names.index(base_corpus)
                except ValueError:
                    base_index = 0  # Default to nouns_one if not found
                
                # Assign corpus with offset
                target_index = base_index + i
                if target_index >= len(corpus_names):
                    # Fallback to nouns_six for overflow
                    assigned_corpus = "nouns_six"
                else:
                    assigned_corpus = corpus_names[target_index]
                
                _dynamic_corpus_cache[f"{level_name}:{group_name}"] = assigned_corpus

def clear_dynamic_corpus_cache():
    """Clear the dynamic corpus cache to force rebuilding on next access."""
    global _dynamic_corpus_cache
    _dynamic_corpus_cache = {}

def get_words_for_dynamic_corpus(corpus_name: str) -> list:
    """
    Get all words that belong to a specific dynamic corpus.
    
    :param corpus_name: The corpus name (e.g., "nouns_three")
    :return: List of enhanced word objects
    """
    if not corpus_name.startswith('nouns_'):
        return []
    
    # Initialize cache if needed
    if not _dynamic_corpus_cache:
        _build_dynamic_corpus_cache()
    
    words = []
    
    # Scan all levels to find words assigned to this corpus
    for level_num in range(1, 25):
        level_name = f"level_{level_num}"
        if level_name in all_words:
            for group_name, group_words in all_words[level_name].items():
                # Check if this group is assigned to the requested corpus
                assigned_corpus = get_dynamic_corpus_name(level_name, group_name)
                if assigned_corpus == corpus_name:
                    word_levels = find_word_levels(level_name, group_name)
                    for word_pair in group_words:
                        enhanced_word = word_pair.copy()
                        enhanced_word['corpus'] = corpus_name
                        enhanced_word['group'] = group_name
                        enhanced_word['levels'] = word_levels
                        words.append(enhanced_word)
    
    return words

# Helper function to find which level(s) a word belongs to based on corpus and group
def find_word_levels(corpus: str, group: str) -> list:
    """
    Find which level(s) a word belongs to based on its corpus and group.
    
    :param corpus: The corpus name (could be level_X for nouns or verbs_/phrases_ for others)
    :param group: The group name
    :return: List of level names that contain this corpus/group combination
    """
    word_levels = []
    
    # Handle noun levels (corpus is level_X format)
    if corpus.startswith('level_'):
        word_levels.append(corpus)
    else:
        # Handle verbs and phrases using the levels configuration
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
    
    :return: JSON response with words in enhanced format including GUIDs
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
                # Map noun level corpus names to the new dynamic naming scheme
                original_corpus = word['corpus']
                if original_corpus.startswith('level_'):
                    word['corpus'] = get_dynamic_corpus_name(original_corpus, word['group'])
                
                word_levels = find_word_levels(original_corpus, word['group'])
                word['levels'] = word_levels
                optimized_words.append(optimize_word_data(word))
            
            return jsonify({
                "level": level,
                "words": optimized_words,
                "count": len(optimized_words)
            })
        
        elif corpus:
            # Filter by corpus - use enhanced format
            corpus_words = []
            
            # Handle noun corpus requests (nouns_one, nouns_two, etc.)
            if corpus.startswith('nouns_'):
                # Use dynamic corpus system to get words
                corpus_words_raw = get_words_for_dynamic_corpus(corpus)
                if not corpus_words_raw:
                    return jsonify({"error": f"Corpus '{corpus}' not found or has no words"}), 404
                
                # Optimize the words
                for word in corpus_words_raw:
                    corpus_words.append(optimize_word_data(word))
            else:
                # Handle other corpus types (verbs, phrases)
                if corpus not in all_words:
                    return jsonify({"error": f"Corpus '{corpus}' not found"}), 404
                
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
                # Map noun level corpus names to the new dynamic naming scheme
                original_corpus = word['corpus']
                if original_corpus.startswith('level_'):
                    word['corpus'] = get_dynamic_corpus_name(original_corpus, word['group'])
                
                word_levels = find_word_levels(original_corpus, word['group'])
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
            words = []
            
            # Handle noun corpus requests (nouns_one, nouns_two, etc.)
            if corpus.startswith('nouns_'):
                # Use dynamic corpus system to get words
                corpus_words = get_words_for_dynamic_corpus(corpus)
                if group:
                    # Filter by specific group
                    words = [word for word in corpus_words if word['group'] == group]
                else:
                    # Get all words from this corpus
                    words = corpus_words
            else:
                # Handle other corpus types (verbs, phrases)
                if corpus in all_words:
                    if group:
                        if group in all_words[corpus]:
                            # Get words for specific group with enhanced format
                            for word_pair in all_words[corpus][group]:
                                enhanced_word = word_pair.copy()
                                enhanced_word['corpus'] = corpus
                                enhanced_word['group'] = group
                                words.append(enhanced_word)
                    else:
                        # Get all words from all groups in this corpus with enhanced format
                        for group_name, group_words in all_words[corpus].items():
                            for word_pair in group_words:
                                enhanced_word = word_pair.copy()
                                enhanced_word['corpus'] = corpus
                                enhanced_word['group'] = group_name
                                words.append(enhanced_word)
        else:
            words = get_all_word_pairs_flat()
            # Map noun level corpus names to the new naming scheme for search results
            for word in words:
                if word['corpus'].startswith('level_'):
                    word['corpus'] = get_noun_corpus_name(word['corpus'])
        
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
        # Check if a specific group is requested via query parameter
        requested_group = request.args.get('group')
        
        # Handle noun corpus requests (nouns_one, nouns_two, etc.)
        if corpus.startswith('nouns_'):
            # Use dynamic corpus system to get words
            corpus_words = get_words_for_dynamic_corpus(corpus)
            if not corpus_words:
                return jsonify({"error": f"Corpus '{corpus}' not found or has no words"}), 404
            
            if requested_group:
                # Return words for the specific group
                group_words = [word for word in corpus_words if word['group'] == requested_group]
                
                if not group_words:
                    return jsonify({"error": f"Group '{requested_group}' not found in corpus '{corpus}'"}), 404
                
                return jsonify({
                    "corpus": corpus,
                    "group": requested_group,
                    "words": group_words
                })
            
            # Return all groups in a nested structure
            result = {
                "corpus": corpus,
                "groups": {}
            }
            
            # Group words by group name
            groups_dict = {}
            for word in corpus_words:
                group_name = word['group']
                if group_name not in groups_dict:
                    groups_dict[group_name] = []
                groups_dict[group_name].append(word)
            
            result["groups"] = groups_dict
            
            return jsonify(result)
        
        else:
            # Handle other corpus types (verbs, phrases)
            groups = get_groups(corpus)
            if not groups:
                return jsonify({"error": f"Corpus '{corpus}' not found"}), 404
            
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
        # Map noun level corpus names to the new dynamic naming scheme
        for word in words:
            if word['corpus'].startswith('level_'):
                word['corpus'] = get_dynamic_corpus_name(word['corpus'], word['group'])
        return jsonify({"words": words})
    except Exception as e:
        logger.error(f"Error getting all words: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/levels')
def get_levels() -> Union[Response, tuple]:
    """
    Get all learning levels with their corpus/group references.
    
    This includes both the verb/phrase mappings from levels.py and the noun data
    that's stored in per-level structures.
    
    :return: JSON response with levels data
    """
    try:
        # Start with the existing levels (verbs and phrases)
        enhanced_levels = {}
        
        # Process each level from 1 to 20
        for level_num in range(1, 21):
            level_name = f"level_{level_num}"
            level_items = []
            
            # Add verb/phrase mappings from levels.py if they exist
            if level_name in levels:
                level_items.extend(levels[level_name])
            
            # Add noun groups from per-level structure if they exist
            if level_name in all_words:
                for group_name in all_words[level_name].keys():
                    # Map the level_X corpus to the appropriate dynamic nouns_X corpus name
                    noun_corpus = get_dynamic_corpus_name(level_name, group_name)
                    level_items.append({
                        "corpus": noun_corpus,
                        "group": group_name
                    })
            
            enhanced_levels[level_name] = level_items
        
        return jsonify({"levels": enhanced_levels})
    except Exception as e:
        logger.error(f"Error getting levels: {str(e)}")
        return jsonify({"error": str(e)}), 500