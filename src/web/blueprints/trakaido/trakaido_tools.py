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
from data.trakaido_wordlists.lang_lt.declensions import (
    CASE_NAMES,
    NOUN_KEYS,
    declensions,
    get_noun_declension,
    get_nouns_by_case
)
from data.trakaido_wordlists.lang_lt.verbs import verbs_new
from data.trakaido_wordlists.lang_lt.wordlists import all_words, get_all_word_pairs_flat, levels
from web.decorators import optional_auth, require_auth
from .shared import *
from .userstats import user_has_activity_stats, USERSTATS_API_DOCS
from .userconfig import get_corpus_choices_file_path, CORPUSCHOICES_API_DOCS
from .wordlists import WORDLISTS_API_DOCS
from .audio import AUDIO_API_DOCS

##############################################################################

# API Documentation for endpoints in this file
CONJUGATIONS_API_DOCS = {
    "GET /api/lithuanian/conjugations/corpuses": "List all available verb corpuses",
    "GET /api/lithuanian/conjugations": "Get all verb conjugations grouped by base verb (param: corpus, defaults to 'verbs_present')",
    "GET /api/lithuanian/conjugations/{verb}": "Get conjugation table for a specific verb (param: corpus, defaults to 'verbs_present')"
}

DECLENSIONS_API_DOCS = {
    "GET /api/lithuanian/declensions": "Get all noun declensions",
    "GET /api/lithuanian/declensions/cases": "List all available cases",
    "GET /api/lithuanian/declensions/cases/{case_name}": "Get all nouns with their forms for a specific case",
    "GET /api/lithuanian/declensions/{noun}": "Get complete declension for a specific noun"
}

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
            "wordlists": WORDLISTS_API_DOCS,
            "conjugations": CONJUGATIONS_API_DOCS,
            "declensions": DECLENSIONS_API_DOCS,
            "audio": AUDIO_API_DOCS,
            "userstats": USERSTATS_API_DOCS,
            "corpuschoices": CORPUSCHOICES_API_DOCS,
            "userinfo": USERINFO_API_DOCS
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
                    journey_stats_path = user_has_activity_stats(str(user_id))
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
