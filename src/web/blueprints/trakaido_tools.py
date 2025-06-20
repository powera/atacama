"""Blueprint for serving Lithuanian language learning resources."""

import os
import json
import random
import re
from typing import Dict, List, Optional, Union, Any

from flask import Blueprint, send_file, request, abort, Response, jsonify, g

import constants  # for LITHUANIAN_AUDIO_DIR, DATA_DIR
from common.base.logging_config import get_logger
from web.decorators import require_auth
from data.trakaido_wordlists.lang_lt.wordlists import get_all_word_pairs_flat, all_words
from data.trakaido_wordlists.lang_lt.declensions import (
    declensions, get_noun_declension, get_nouns_by_case, 
    CASE_NAMES, NOUN_KEYS
)
from data.trakaido_wordlists.lang_lt.verbs import (
    verbs_new
)

logger = get_logger(__name__)

trakaido_bp = Blueprint('trakaido', __name__)

LITHUANIAN_CHARS = "aąbcčdeęėfghiįyjklmnoprsštuųūvzž"


@trakaido_bp.route("/trakaido")
def trakaido_index() -> Response:
    """Serve the index page."""
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
            }
        }
    }
    return jsonify(api_info)


def get_available_voices() -> List[str]:
    """
    Get a list of available voice directories.
    
    :return: List of voice names (directory names)
    """
    try:
        if not os.path.exists(constants.LITHUANIAN_AUDIO_DIR):
            logger.error(f"Lithuanian audio directory not found: {constants.LITHUANIAN_AUDIO_DIR}")
            return []
        
        # Get all directories in the Lithuanian audio directory
        voices = [d for d in os.listdir(constants.LITHUANIAN_AUDIO_DIR) 
                 if os.path.isdir(os.path.join(constants.LITHUANIAN_AUDIO_DIR, d))]
        
        return voices
    except Exception as e:
        logger.error(f"Error getting Lithuanian voice directories: {str(e)}")
        return []

def sanitize_lithuanian_word(word: str) -> str:
    """
    Sanitize a Lithuanian word or phrase for use as a filename.
    
    Args:
        word: The Lithuanian word or phrase to sanitize
    
    Returns:
        Sanitized filename-safe version or empty string if invalid
    """
    word = word.strip().lower()
    
    # Replace spaces with underscores for multi-word phrases
    word_with_underscores = word.replace(' ', '_')
    
    # Allow all Lithuanian letters, basic Latin letters, and safe characters
    sanitized = re.sub(r'[^a-z' + LITHUANIAN_CHARS + r'\-_]', '', word_with_underscores)
    
    if not sanitized or len(sanitized) > 100:
        return ""
        
    return sanitized

def get_audio_file_path(word: str, voice: Optional[str] = None) -> Optional[str]:
    """
    Get the path to an audio file for the given word and voice.
    
    :param word: Lithuanian word to get audio for
    :param voice: Optional voice name to use, if None a random voice will be selected
    :return: Path to the audio file or None if not found
    """
    try:
        voices = get_available_voices()
        if not voices:
            logger.error("No Lithuanian voice directories found")
            return None
        
        # If no voice specified, choose a random one
        selected_voice = voice if voice in voices else random.choice(voices)
        
        word_filename = sanitize_lithuanian_word(word)

        # Construct the file path
        file_path = os.path.join(constants.LITHUANIAN_AUDIO_DIR, selected_voice, f"{word_filename}.mp3")
        
        # Check if the file exists
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return None
        
        return file_path
    except Exception as e:
        logger.error(f"Error getting audio file path for word '{word}': {str(e)}")
        return None

# Wordlist related functions
def get_wordlist_corpora() -> List[str]:
    """
    Get a list of all wordlist corpora.
    
    :return: List of corpus names
    """
    try:
        corpora = list(all_words.keys())
        logger.debug(f"Found {len(corpora)} wordlist corpora: {', '.join(corpora)}")
        return corpora
    except Exception as e:
        logger.error(f"Error getting wordlist corpora: {str(e)}")
        return []

def get_groups(corpus: str) -> List[str]:
    """
    Get a list of groups for a given corpus.
    
    :param corpus: The corpus name
    :return: List of group names
    """
    try:
        if corpus not in all_words:
            logger.error(f"Corpus not found: {corpus}")
            return []
        
        groups = list(all_words[corpus].keys())
        logger.debug(f"Found {len(groups)} groups for {corpus}: {', '.join(groups)}")
        return groups
    except Exception as e:
        logger.error(f"Error getting groups for {corpus}: {str(e)}")
        return []

def get_words_by_corpus(corpus: str, group: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Get words for a specific corpus and optional group.
    
    :param corpus: The corpus name
    :param group: Optional group name
    :return: List of word pairs
    """
    try:
        if corpus not in all_words:
            logger.error(f"Corpus not found: {corpus}")
            return []
        
        if group:
            if group not in all_words[corpus]:
                logger.error(f"Group {group} not found in corpus {corpus}")
                return []
            return all_words[corpus][group]
        
        # If no group specified, return all words from all groups in this corpus
        result = []
        for grp, words in all_words[corpus].items():
            result.extend(words)
        return result
    except Exception as e:
        logger.error(f"Error getting words for corpus {corpus}, group {group}: {str(e)}")
        return []

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
    

# API Routes for audio
@trakaido_bp.route('/api/lithuanian/audio/voices')
def list_voices() -> Union[Response, tuple]:
    """
    List all available Lithuanian voices.
    
    :return: JSON response with list of voices
    """
    try:
        voices = get_available_voices()
        return jsonify({"voices": voices})
    except Exception as e:
        logger.error(f"Error listing Lithuanian voices: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/audio/<word>')
def serve_lithuanian_audio(word: str) -> Union[Response, tuple]:
    """
    Serve a Lithuanian audio file for the given word.
    
    :param word: Lithuanian word to get audio for
    :return: Audio file response or error
    """
    try:
        # Get the voice parameter from the request, if provided
        voice = request.args.get('voice')
        
        # Get the audio file path
        file_path = get_audio_file_path(word, voice)
        if not file_path:
            return abort(404, f"Audio for '{word}' not found")
        
        # Serve the audio file
        return send_file(file_path, mimetype='audio/mpeg')
    except Exception as e:
        logger.error(f"Error serving Lithuanian audio for word '{word}': {str(e)}")
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
