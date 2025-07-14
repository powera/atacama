"""Shared data and utilities for the Trakaido Lithuanian language learning module."""

import re
from flask import Blueprint

from common.base.logging_config import get_logger

from typing import List, Optional, Union, Dict

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


from data.trakaido_wordlists.lang_lt.wordlists import get_all_word_pairs_flat, all_words, levels

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