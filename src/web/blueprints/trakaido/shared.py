"""Shared data and utilities for the Trakaido Lithuanian language learning module."""

# Standard library imports
import os
import re
from typing import Dict, List, Optional, Union

# Third-party imports
from flask import Blueprint

# Local application imports
import constants
from common.base.logging_config import get_logger
from data.trakaido_wordlists.lang_lt.wordlists import all_words, get_all_word_pairs_flat, levels

# Create the blueprint that will be used by all trakaido modules
trakaido_bp = Blueprint('trakaido', __name__)

# Lithuanian character set for validation and sanitization
LITHUANIAN_CHARS = "aąbcčdeęėfghiįyjklmnoprsštuųūvzž"

# Production path for the Trakaido React app
TRAKAIDO_PATH_PROD = "/home/atacama/trakaido_react/build/index.html"

# Shared logger
logger = get_logger(__name__)


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


def ensure_user_data_dir(user_id: str) -> str:
    """
    Ensure the user's data directory exists.
    
    :param user_id: The user's database ID
    :return: Path to the user's data directory
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id))
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir


# Wordlist related functions
def get_wordlist_corpora() -> List[str]:
    """
    Get a list of all wordlist corpora.
    
    :return: List of corpus names
    """
    try:
        corpora = list(all_words.keys())
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