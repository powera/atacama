"""Blueprint for serving Lithuanian language learning resources."""

import os
import json
import random
import re
from typing import Dict, List, Optional, Union, Any

from flask import Blueprint, send_file, request, abort, Response, jsonify, g

from .shared import *

import constants  # for LITHUANIAN_AUDIO_DIR, DATA_DIR
from common.base.logging_config import get_logger
from web.decorators import require_auth, optional_auth
from data.trakaido_wordlists.lang_lt.wordlists import get_all_word_pairs_flat, all_words, levels
from data.trakaido_wordlists.lang_lt.declensions import (
    declensions, get_noun_declension, get_nouns_by_case, 
    CASE_NAMES, NOUN_KEYS
)
from data.trakaido_wordlists.lang_lt.verbs import (
    verbs_new
)

@trakaido_bp.route("/trakaido")
def trakaido_index() -> Response:
    """Serve the index page."""
    if os.path.exists(TRAKAIDO_PATH_PROD):
        # In production, serve the compiled index.html from the Trakaido repo
        return send_file(TRAKAIDO_PATH_PROD)
    return send_file(constants.WEB_DIR + "/static/trakaido.html")

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
            "wordlists": {
                "GET /api/lithuanian/wordlists": "List all wordlist corpora",
                "GET /api/lithuanian/wordlists/_all": "Get all words from all corpora",
                "GET /api/lithuanian/wordlists/levels": "Get all learning levels with their corpus/group references",
                "GET /api/lithuanian/wordlists/search": "Search for words (params: english, lithuanian, corpus, group)",
                "GET /api/lithuanian/wordlists/{corpus}": "List all groups in a corpus in a nested structure",
                "GET /api/lithuanian/wordlists/{corpus}?group={group_name}": "Get words for a specific group in a corpus"
            },
            "conjugations": {
                "GET /api/lithuanian/conjugations/corpuses": "List all available verb corpuses",
                "GET /api/lithuanian/conjugations": "Get all verb conjugations grouped by base verb (param: corpus, defaults to 'verbs_present')",
                "GET /api/lithuanian/conjugations/{verb}": "Get conjugation table for a specific verb (param: corpus, defaults to 'verbs_present')"
            },
            "declensions": {
                "GET /api/lithuanian/declensions": "Get all noun declensions",
                "GET /api/lithuanian/declensions/cases": "List all available cases",
                "GET /api/lithuanian/declensions/cases/{case_name}": "Get all nouns with their forms for a specific case",
                "GET /api/lithuanian/declensions/{noun}": "Get complete declension for a specific noun"
            },
            "audio": {
                "GET /api/lithuanian/audio/voices": "List all available voices",
                "GET /api/lithuanian/audio/{word}": "Get audio for a Lithuanian word (param: voice)"
            },
            "journeystats": {
                "GET /api/trakaido/journeystats/": "Get all journey stats for authenticated user",
                "PUT /api/trakaido/journeystats/": "Save all journey stats for authenticated user",
                "POST /api/trakaido/journeystats/word": "Update stats for a specific word",
                "GET /api/trakaido/journeystats/word/{wordKey}": "Get stats for a specific word"
            },
            "corpuschoices": {
                "GET /api/trakaido/corpuschoices/": "Get all corpus choices for authenticated user",
                "PUT /api/trakaido/corpuschoices/": "Save all corpus choices for authenticated user",
                "POST /api/trakaido/corpuschoices/corpus": "Update choices for a specific corpus",
                "GET /api/trakaido/corpuschoices/corpus/{corpus}": "Get choices for a specific corpus"
            },
            "userinfo": {
                "GET /api/trakaido/userinfo/": "Get user authentication status and basic info"
            }
        }
    }
    return jsonify(api_info)


def extract_verb_conjugations(tense="present_tense") -> Dict[str, List[Dict[str, str]]]:
    """
    Extract verb conjugations from the per-verb data tables and group them by base verb.
    
    :param tense: The tense to extract ('present_tense', 'past_tense', 'future')
    :return: Dictionary mapping base verbs to their conjugation lists
    """
    try:
        conjugations = {}
        
        # Define the standard order for conjugation forms
        person_order = ["1s", "2s", "3s-m", "3s-f", "3s-n", "1p", "2p", "3p-m", "3p-f"]
        
        # Iterate through all verbs in the new data structure
        for infinitive, verb_data in verbs_new.items():
            if tense not in verb_data:
                continue
                
            # Extract the base verb from the English translation
            english_infinitive = verb_data.get("english", "")
            base_verb = english_infinitive.replace("to ", "") if english_infinitive.startswith("to ") else infinitive
            
            # Create conjugation list for this verb
            verb_conjugations = []
            tense_data = verb_data[tense]
            
            # Process conjugations in the standard order
            for person_key in person_order:
                if person_key in tense_data:
                    conjugation_entry = {
                        "english": tense_data[person_key]["english"],
                        "lithuanian": tense_data[person_key]["lithuanian"],
                        "infinitive": infinitive,
                        "tense": tense,
                        "person": person_key
                    }
                    verb_conjugations.append(conjugation_entry)
            
            # Store conjugations using the base verb as key
            conjugations[base_verb] = verb_conjugations
        
        logger.debug(f"Extracted {len(conjugations)} verb conjugation sets for tense '{tense}'")
        return conjugations
    
    except Exception as e:
        logger.error(f"Error extracting verb conjugations: {str(e)}")
        return {}

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
                "username": getattr(g.user, 'username', None) if hasattr(g.user, 'username') else None
            }
            
            # Check if user has existing files
            if user_id:
                try:
                    journey_stats_path = get_journey_stats_file_path(str(user_id))
                    corpus_choices_path = get_corpus_choices_file_path(str(user_id))
                    
                    response_data["has_journey_stats_file"] = os.path.exists(journey_stats_path)
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


@trakaido_bp.route('/api/lithuanian/conjugations/corpuses')
def list_verb_corpuses() -> Union[Response, tuple]:
    """
    Get a list of available verb corpuses.
    
    :return: JSON response with available verb corpuses
    """
    try:
        all_corpora = get_wordlist_corpora()
        verb_corpora = [corpus for corpus in all_corpora if corpus.startswith('verbs_')]
        
        return jsonify({
            "verb_corpuses": verb_corpora,
            "count": len(verb_corpora)
        })
    except Exception as e:
        logger.error(f"Error getting verb corpuses: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/conjugations')
def get_verb_conjugations() -> Union[Response, tuple]:
    """
    Get all verb conjugations grouped by base verb.
    Supports optional 'tense' query parameter to specify which tense to use.
    Also supports legacy 'corpus' parameter for backward compatibility.
    
    :return: JSON response with verb conjugations
    """
    try:
        # Support both new 'tense' parameter and legacy 'corpus' parameter
        tense = request.args.get('tense')
        corpus = request.args.get('corpus')
        
        if tense:
            selected_tense = tense
        elif corpus:
            # Map legacy corpus names to tenses
            corpus_to_tense = {
                'verbs_present': 'present_tense',
                'verbs_past': 'past_tense', 
                'verbs_future': 'future'
            }
            selected_tense = corpus_to_tense.get(corpus, 'present_tense')
        else:
            selected_tense = 'present_tense'
        
        # Validate tense exists
        available_tenses = set()
        for verb_data in verbs_new.values():
            for key in verb_data.keys():
                if key != "english":
                    available_tenses.add(key)
        
        if selected_tense not in available_tenses:
            return jsonify({"error": f"Tense '{selected_tense}' not found. Available: {sorted(list(available_tenses))}"}), 404
        
        conjugations = extract_verb_conjugations(selected_tense)
        return jsonify({
            "tense": selected_tense,
            "conjugations": conjugations,
            "verbs": list(conjugations.keys()),
            "count": len(conjugations)
        })
    except Exception as e:
        logger.error(f"Error getting verb conjugations: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/conjugations/<verb>')
def get_specific_verb_conjugation(verb: str) -> Union[Response, tuple]:
    """
    Get conjugation for a specific verb.
    Supports optional 'tense' query parameter to specify which tense to use.
    Also supports legacy 'corpus' parameter for backward compatibility.
    
    :param verb: The base verb (e.g., "walk", "eat") or Lithuanian infinitive (e.g., "valgyti")
    :return: JSON response with conjugation table
    """
    try:
        # Support both new 'tense' parameter and legacy 'corpus' parameter
        tense = request.args.get('tense')
        corpus = request.args.get('corpus')
        
        if tense:
            selected_tense = tense
        elif corpus:
            # Map legacy corpus names to tenses
            corpus_to_tense = {
                'verbs_present': 'present_tense',
                'verbs_past': 'past_tense', 
                'verbs_future': 'future'
            }
            selected_tense = corpus_to_tense.get(corpus, 'present_tense')
        else:
            selected_tense = 'present_tense'
        
        # Validate tense exists
        available_tenses = set()
        for verb_data in verbs_new.values():
            for key in verb_data.keys():
                if key != "english":
                    available_tenses.add(key)
        
        if selected_tense not in available_tenses:
            return jsonify({"error": f"Tense '{selected_tense}' not found. Available: {sorted(list(available_tenses))}"}), 404
        
        # Try to find the verb by infinitive first, then by base verb
        verb_conjugation = None
        matched_infinitive = None
        
        # Check if the verb is a Lithuanian infinitive
        if verb in verbs_new and selected_tense in verbs_new[verb]:
            matched_infinitive = verb
            verb_data = verbs_new[verb]
            verb_conjugation = []
            
            person_order = ["1s", "2s", "3s-m", "3s-f", "3s-n", "1p", "2p", "3p-m", "3p-f"]
            tense_data = verb_data[selected_tense]
            
            for person_key in person_order:
                if person_key in tense_data:
                    conjugation_entry = {
                        "english": tense_data[person_key]["english"],
                        "lithuanian": tense_data[person_key]["lithuanian"],
                        "infinitive": matched_infinitive,
                        "tense": selected_tense,
                        "person": person_key
                    }
                    verb_conjugation.append(conjugation_entry)
        else:
            # Try to find by base verb (English)
            conjugations = extract_verb_conjugations(selected_tense)
            if verb in conjugations:
                verb_conjugation = conjugations[verb]
                # Find the infinitive for this base verb
                for infinitive, verb_data in verbs_new.items():
                    english_infinitive = verb_data.get("english", "")
                    base_verb = english_infinitive.replace("to ", "") if english_infinitive.startswith("to ") else infinitive
                    if base_verb == verb:
                        matched_infinitive = infinitive
                        break
        
        if not verb_conjugation:
            return jsonify({"error": f"Verb '{verb}' not found for tense '{selected_tense}'"}), 404
        
        return jsonify({
            "verb": verb,
            "infinitive": matched_infinitive,
            "tense": selected_tense,
            "conjugations": verb_conjugation
        })
    except Exception as e:
        logger.error(f"Error getting conjugation for verb '{verb}': {str(e)}")
        return jsonify({"error": str(e)}), 500
    
# Declension API endpoints

@trakaido_bp.route('/api/lithuanian/declensions')
def get_all_declensions() -> Union[Response, tuple]:
    """
    Get all noun declensions.
    
    :return: JSON response with all declension data
    """
    try:
        return jsonify({
            "declensions": declensions,
            "total_nouns": len(declensions),
            "available_nouns": NOUN_KEYS
        })
    except Exception as e:
        logger.error(f"Error getting all declensions: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/lithuanian/declensions/cases')
def list_cases() -> Union[Response, tuple]:
    """
    List all available cases.
    
    :return: JSON response with all case names
    """
    try:
        return jsonify({
            "cases": CASE_NAMES,
            "total_cases": len(CASE_NAMES)
        })
    except Exception as e:
        logger.error(f"Error listing cases: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/lithuanian/declensions/cases/<case_name>')
def get_nouns_for_case(case_name: str) -> Union[Response, tuple]:
    """
    Get all nouns with their forms for a specific case.
    
    :param case_name: Name of the case (nominative, genitive, etc.)
    :return: JSON response with nouns for the specified case
    """
    try:
        if case_name not in CASE_NAMES:
            return jsonify({
                "error": f"Invalid case name '{case_name}'. Available cases: {CASE_NAMES}"
            }), 400
        
        nouns_data = get_nouns_by_case(case_name)
        return jsonify({
            "case": case_name,
            "nouns": nouns_data,
            "total_nouns": len(nouns_data)
        })
    except Exception as e:
        logger.error(f"Error getting nouns for case '{case_name}': {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/lithuanian/declensions/<noun>')
def get_specific_noun_declension(noun: str) -> Union[Response, tuple]:
    """
    Get complete declension for a specific noun.
    
    :param noun: The nominative form of the noun
    :return: JSON response with complete declension data
    """
    try:
        declension_data = get_noun_declension(noun)
        if not declension_data:
            return jsonify({
                "error": f"Noun '{noun}' not found. Available nouns: {NOUN_KEYS}"
            }), 404
        
        return jsonify({
            "noun": noun,
            "declension": declension_data
        })
    except Exception as e:
        logger.error(f"Error getting declension for noun '{noun}': {str(e)}")
        return jsonify({"error": str(e)}), 500


# Journey Stats related functions
VALID_STAT_TYPES = {"multipleChoice", "listeningEasy", "listeningHard", "typing"}

def get_journey_stats_file_path(user_id: str) -> str:
    """
    Get the file path for a user's journey stats.
    
    :param user_id: The user's database ID
    :return: Path to the user's Lithuanian journey stats file
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id))
    return os.path.join(user_data_dir, "lithuanian.json")

def ensure_user_data_dir(user_id: str) -> str:
    """
    Ensure the user's data directory exists.
    
    :param user_id: The user's database ID
    :return: Path to the user's data directory
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id))
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir

def load_journey_stats(user_id: str) -> Dict[str, Any]:
    """
    Load journey stats for a user from their JSON file.
    
    :param user_id: The user's database ID
    :return: Dictionary containing the user's journey stats
    """
    try:
        stats_file = get_journey_stats_file_path(user_id)
        if not os.path.exists(stats_file):
            logger.debug(f"DEBUG: No stats file found for user {user_id}, returning empty stats")
            return {"stats": {}}
        
        with open(stats_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Filter out invalid stat types
        filtered_stats = {}
        if "stats" in data:
            for word_key, word_stats in data["stats"].items():
                filtered_word_stats = {}
                for stat_type, stat_data in word_stats.items():
                    if stat_type in VALID_STAT_TYPES or stat_type in ["exposed", "lastSeen"]:
                        filtered_word_stats[stat_type] = stat_data
                    else:
                        logger.debug(f"Filtering out invalid stat type '{stat_type}' for word '{word_key}'")
                filtered_stats[word_key] = filtered_word_stats
        
        return {"stats": filtered_stats}
    except Exception as e:
        logger.error(f"Error loading journey stats for user {user_id}: {str(e)}")
        return {"stats": {}}

def save_journey_stats(user_id: str, stats: Dict[str, Any]) -> bool:
    """
    Save journey stats for a user to their JSON file.
    
    :param user_id: The user's database ID
    :param stats: Dictionary containing the user's journey stats
    :return: True if successful, False otherwise
    """
    try:
        ensure_user_data_dir(user_id)
        stats_file = get_journey_stats_file_path(user_id)
        
        # Filter out invalid stat types before saving
        filtered_data = {"stats": {}}
        if "stats" in stats:
            for word_key, word_stats in stats["stats"].items():
                filtered_word_stats = {}
                for stat_type, stat_data in word_stats.items():
                    if stat_type in VALID_STAT_TYPES or stat_type in ["exposed", "lastSeen"]:
                        filtered_word_stats[stat_type] = stat_data
                    else:
                        logger.debug(f"Filtering out invalid stat type '{stat_type}' for word '{word_key}' before saving")
                filtered_data["stats"][word_key] = filtered_word_stats
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Successfully saved journey stats for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving journey stats for user {user_id}: {str(e)}")
        return False

def filter_word_stats(word_stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter word stats to include only valid stat types.
    
    :param word_stats: Raw word stats dictionary
    :return: Filtered word stats dictionary
    """
    filtered_stats = {}
    for stat_type, stat_data in word_stats.items():
        if stat_type in VALID_STAT_TYPES or stat_type in ["exposed", "lastSeen"]:
            filtered_stats[stat_type] = stat_data
        else:
            logger.debug(f"Filtering out invalid stat type '{stat_type}'")
    return filtered_stats


# Journey Stats API Routes
@trakaido_bp.route('/api/trakaido/journeystats/', methods=['GET'])
@require_auth
def get_all_journey_stats() -> Union[Response, tuple]:
    """
    Get all journey stats for the authenticated user.
    
    :return: JSON response with all journey stats
    """
    try:
        user_id = str(g.user.id)
        stats = load_journey_stats(user_id)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting all journey stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/trakaido/journeystats/', methods=['PUT'])
@require_auth
def save_all_journey_stats() -> Union[Response, tuple]:
    """
    Save all journey stats for the authenticated user.
    
    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()
        
        if not data or "stats" not in data:
            return jsonify({"error": "Invalid request body. Expected 'stats' field."}), 400
        
        success = save_journey_stats(user_id, data)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to save journey stats"}), 500
    except Exception as e:
        logger.error(f"Error saving all journey stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/trakaido/journeystats/word', methods=['POST'])
@require_auth
def update_word_stats() -> Union[Response, tuple]:
    """
    Update stats for a specific word for the authenticated user.
    
    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()
        
        if not data or "wordKey" not in data or "wordStats" not in data:
            return jsonify({"error": "Invalid request body. Expected 'wordKey' and 'wordStats' fields."}), 400
        
        word_key = data["wordKey"]
        word_stats = data["wordStats"]
        
        # Filter the word stats to include only valid types
        filtered_word_stats = filter_word_stats(word_stats)
        
        # Load existing stats
        all_stats = load_journey_stats(user_id)
        
        # Update the specific word stats
        all_stats["stats"][word_key] = filtered_word_stats
        
        # Save back to file
        success = save_journey_stats(user_id, all_stats)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to update word stats"}), 500
    except Exception as e:
        logger.error(f"Error updating word stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/trakaido/journeystats/word/<word_key>', methods=['GET'])
@require_auth
def get_word_stats(word_key: str) -> Union[Response, tuple]:
    """
    Get stats for a specific word for the authenticated user.
    
    :param word_key: The word key to get stats for
    :return: JSON response with word stats
    """
    try:
        user_id = str(g.user.id)
        all_stats = load_journey_stats(user_id)
        
        word_stats = all_stats["stats"].get(word_key, {})
        
        return jsonify({"wordStats": word_stats})
    except Exception as e:
        logger.error(f"Error getting word stats for '{word_key}': {str(e)}")
        return jsonify({"error": str(e)}), 500


# Corpus Choices related functions
def get_corpus_choices_file_path(user_id: str) -> str:
    """
    Get the file path for a user's corpus choices.
    
    :param user_id: The user's database ID
    :return: Path to the user's corpus choices file
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id))
    return os.path.join(user_data_dir, "corpuschoices.json")

def load_corpus_choices(user_id: str) -> Dict[str, Any]:
    """
    Load corpus choices for a user from their JSON file.
    
    :param user_id: The user's database ID
    :return: Dictionary containing the user's corpus choices
    """
    try:
        choices_file = get_corpus_choices_file_path(user_id)
        if not os.path.exists(choices_file):
            logger.debug(f"No corpus choices file found for user {user_id}, returning empty choices")
            return {"choices": {}}
        
        with open(choices_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Validate the structure - each corpus should map to a list of group names
        validated_choices = {}
        if "choices" in data and isinstance(data["choices"], dict):
            for corpus, groups in data["choices"].items():
                if isinstance(groups, list) and all(isinstance(group, str) for group in groups):
                    validated_choices[corpus] = groups
                else:
                    logger.warning(f"Invalid groups format for corpus '{corpus}' for user {user_id}, skipping")
        
        return {"choices": validated_choices}
    except Exception as e:
        logger.error(f"Error loading corpus choices for user {user_id}: {str(e)}")
        return {"choices": {}}

def save_corpus_choices(user_id: str, choices: Dict[str, Any]) -> bool:
    """
    Save corpus choices for a user to their JSON file.
    
    :param user_id: The user's database ID
    :param choices: Dictionary containing the user's corpus choices
    :return: True if successful, False otherwise
    """
    try:
        ensure_user_data_dir(user_id)
        choices_file = get_corpus_choices_file_path(user_id)
        
        # Validate the structure before saving
        validated_data = {"choices": {}}
        if "choices" in choices and isinstance(choices["choices"], dict):
            for corpus, groups in choices["choices"].items():
                if isinstance(groups, list) and all(isinstance(group, str) for group in groups):
                    validated_data["choices"][corpus] = groups
                else:
                    logger.warning(f"Invalid groups format for corpus '{corpus}', skipping")
        
        with open(choices_file, 'w', encoding='utf-8') as f:
            json.dump(validated_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Successfully saved corpus choices for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving corpus choices for user {user_id}: {str(e)}")
        return False

def validate_corpus_exists(corpus: str) -> bool:
    """
    Validate that a corpus exists in the available wordlist corpora.
    
    :param corpus: The corpus name to validate
    :return: True if corpus exists, False otherwise
    """
    try:
        available_corpora = get_wordlist_corpora()
        return corpus in available_corpora
    except Exception as e:
        logger.error(f"Error validating corpus '{corpus}': {str(e)}")
        return False

def validate_groups_in_corpus(corpus: str, groups: List[str]) -> List[str]:
    """
    Validate that groups exist in the specified corpus and return only valid ones.
    
    :param corpus: The corpus name
    :param groups: List of group names to validate
    :return: List of valid group names
    """
    try:
        if not validate_corpus_exists(corpus):
            logger.warning(f"Corpus '{corpus}' does not exist")
            return []
        
        available_groups = get_groups(corpus)
        valid_groups = [group for group in groups if group in available_groups]
        
        invalid_groups = [group for group in groups if group not in available_groups]
        if invalid_groups:
            logger.warning(f"Invalid groups for corpus '{corpus}': {invalid_groups}")
        
        return valid_groups
    except Exception as e:
        logger.error(f"Error validating groups for corpus '{corpus}': {str(e)}")
        return []


# Corpus Choices API Routes
@trakaido_bp.route('/api/trakaido/corpuschoices/', methods=['GET'])
@require_auth
def get_all_corpus_choices() -> Union[Response, tuple]:
    """
    Get all corpus choices for the authenticated user.
    
    :return: JSON response with all corpus choices
    """
    try:
        user_id = str(g.user.id)
        choices = load_corpus_choices(user_id)
        return jsonify(choices)
    except Exception as e:
        logger.error(f"Error getting all corpus choices: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/trakaido/corpuschoices/', methods=['PUT'])
@require_auth
def save_all_corpus_choices() -> Union[Response, tuple]:
    """
    Save all corpus choices for the authenticated user, replacing any existing choices.
    
    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()
        
        if not data or "choices" not in data:
            return jsonify({
                "success": False,
                "error": "Invalid request body. Expected 'choices' field.",
                "code": "INVALID_REQUEST"
            }), 400
        
        # Validate each corpus and its groups
        validated_choices = {"choices": {}}
        for corpus, groups in data["choices"].items():
            if not isinstance(groups, list):
                logger.warning(f"Invalid groups format for corpus '{corpus}', skipping")
                continue
                
            if validate_corpus_exists(corpus):
                valid_groups = validate_groups_in_corpus(corpus, groups)
                if valid_groups:  # Only store if there are valid groups
                    validated_choices["choices"][corpus] = valid_groups
            else:
                logger.warning(f"Corpus '{corpus}' does not exist, skipping")
        
        success = save_corpus_choices(user_id, validated_choices)
        if success:
            return jsonify({
                "success": True,
                "message": "Corpus choices saved successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save corpus choices",
                "code": "STORAGE_ERROR"
            }), 500
    except Exception as e:
        logger.error(f"Error saving all corpus choices: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "STORAGE_ERROR"
        }), 500

@trakaido_bp.route('/api/trakaido/corpuschoices/corpus', methods=['POST'])
@require_auth
def update_corpus_choices() -> Union[Response, tuple]:
    """
    Update the selected groups for a specific corpus.
    
    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()
        
        if not data or "corpus" not in data or "groups" not in data:
            return jsonify({
                "success": False,
                "error": "Invalid request body. Expected 'corpus' and 'groups' fields.",
                "code": "INVALID_REQUEST"
            }), 400
        
        corpus = data["corpus"]
        groups = data["groups"]
        
        if not isinstance(groups, list):
            return jsonify({
                "success": False,
                "error": "Groups must be an array of strings",
                "code": "INVALID_REQUEST"
            }), 400
        
        # Validate corpus exists
        if not validate_corpus_exists(corpus):
            return jsonify({
                "success": False,
                "error": f"Corpus '{corpus}' not found",
                "code": "CORPUS_NOT_FOUND"
            }), 400
        
        # Validate groups exist in corpus
        valid_groups = validate_groups_in_corpus(corpus, groups)
        
        # Load existing choices
        all_choices = load_corpus_choices(user_id)
        
        # Update the specific corpus choices
        if valid_groups:
            all_choices["choices"][corpus] = valid_groups
        elif corpus in all_choices["choices"]:
            # Remove corpus if no valid groups remain
            del all_choices["choices"][corpus]
        
        # Save back to file
        success = save_corpus_choices(user_id, all_choices)
        if success:
            return jsonify({
                "success": True,
                "message": "Corpus choices updated successfully",
                "corpus": corpus,
                "groups": valid_groups
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to update corpus choices",
                "code": "STORAGE_ERROR"
            }), 500
    except Exception as e:
        logger.error(f"Error updating corpus choices: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "STORAGE_ERROR"
        }), 500

@trakaido_bp.route('/api/trakaido/corpuschoices/corpus/<corpus>', methods=['GET'])
@require_auth
def get_corpus_choices(corpus: str) -> Union[Response, tuple]:
    """
    Get the selected groups for a specific corpus.
    
    :param corpus: The name of the corpus
    :return: JSON response with corpus choices
    """
    try:
        user_id = str(g.user.id)
        all_choices = load_corpus_choices(user_id)
        
        # Get groups for the specific corpus, or empty array if not found
        groups = all_choices["choices"].get(corpus, [])
        
        return jsonify({
            "corpus": corpus,
            "groups": groups
        })
    except Exception as e:
        logger.error(f"Error getting corpus choices for '{corpus}': {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "STORAGE_ERROR"
        }), 500
