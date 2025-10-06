#!/usr/bin/env python3
"""
Build GUID mapping from dictionary files.

This script parses all dictionary files in the trakaido_wordlists package
and creates a bidirectional mapping between wordKey format (lithuanian-english)
and GUID format (e.g., N02_001).
"""

import os
import sys
import json
from typing import Dict, List, Tuple

# Add project root to Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
sys.path.insert(0, PROJECT_ROOT)

# Dictionary directory location
DICTIONARY_DIR = os.path.join(PROJECT_ROOT, "data/trakaido_wordlists/lang_lt/generated/dictionary")

# Wireword JSON files
WIREWORD_VERBS_FILE = os.path.join(PROJECT_ROOT, "data/trakaido_wordlists/lang_lt/generated/wireword_verbs.json")
WIREWORD_NOUNS_FILE = os.path.join(PROJECT_ROOT, "data/trakaido_wordlists/lang_lt/generated/wireword_nouns.json")

# Legacy data files
PHRASES_FILE = os.path.join(PROJECT_ROOT, "data/trakaido_wordlists/lang_lt/phrases.py")
VERBS_FILE = os.path.join(PROJECT_ROOT, "data/trakaido_wordlists/lang_lt/verbs.py")
NOUNS_FILE = os.path.join(PROJECT_ROOT, "data/trakaido_wordlists/lang_lt/nouns.py")


def normalize_text(text: str) -> str:
    """Normalize text for consistent key generation."""
    # Strip whitespace and convert to lowercase
    text = text.strip().lower()
    # Remove parenthetical clarifications like "(fruit)" or "(color)"
    # Match patterns like " (something)" at the end
    import re
    text = re.sub(r'\s*\([^)]+\)\s*$', '', text)
    text = text.strip()
    return text


def generate_word_key(lithuanian: str, english: str) -> str:
    """Generate wordKey in the format: {lithuanian}-{english}"""
    return f"{normalize_text(lithuanian)}-{normalize_text(english)}"


def generate_word_key_variants(lithuanian: str, english: str) -> List[str]:
    """
    Generate multiple variants of wordKey to handle legacy formats.

    Returns list of possible keys, including:
    - Normalized version (no parentheses)
    - Original with parentheses preserved
    """
    keys = []

    # Primary normalized key (no parentheses)
    normalized_key = generate_word_key(lithuanian, english)
    keys.append(normalized_key)

    # Also add version with parentheses if they exist in original
    if '(' in english or '(' in lithuanian:
        lit_raw = lithuanian.strip().lower()
        eng_raw = english.strip().lower()
        keys.append(f"{lit_raw}-{eng_raw}")

    return keys


def extract_guid_from_dict(word_dict: Dict) -> Tuple[str, str, str, List[str], List[str]]:
    """
    Extract GUID and word information from a dictionary entry.

    Returns:
        Tuple of (guid, lithuanian, english, lithuanian_alternatives, english_alternatives)
    """
    guid = word_dict.get('guid', '')
    lithuanian = word_dict.get('lithuanian', '')
    english = word_dict.get('english', '')

    alternatives = word_dict.get('alternatives', {})
    lithuanian_alts = alternatives.get('lithuanian', [])
    english_alts = alternatives.get('english', [])

    return guid, lithuanian, english, lithuanian_alts, english_alts


def load_dictionary_file(filepath: str) -> Dict[str, str]:
    """
    Load a dictionary file and extract GUID mappings.

    Returns:
        Dict mapping wordKey -> GUID
    """
    mappings = {}

    # Read the file and execute it to get the word dictionaries
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Create a namespace to execute the file in
    namespace = {}
    try:
        exec(content, namespace)
    except Exception as e:
        print(f"Error loading {filepath}: {e}", file=sys.stderr)
        return mappings

    # Find all GUID entries (variables that start with N, V, P, etc. and contain '_')
    for var_name, var_value in namespace.items():
        if isinstance(var_value, dict) and 'guid' in var_value:
            guid, lithuanian, english, lit_alts, eng_alts = extract_guid_from_dict(var_value)

            if not guid or not lithuanian or not english:
                continue

            # Primary mapping - generate all variants
            for variant_key in generate_word_key_variants(lithuanian, english):
                if variant_key not in mappings:
                    mappings[variant_key] = guid

            # Add mappings for alternatives
            # Lithuanian alternatives with primary English
            for lit_alt in lit_alts:
                for variant_key in generate_word_key_variants(lit_alt, english):
                    if variant_key not in mappings:
                        mappings[variant_key] = guid

            # English alternatives with primary Lithuanian
            for eng_alt in eng_alts:
                for variant_key in generate_word_key_variants(lithuanian, eng_alt):
                    if variant_key not in mappings:
                        mappings[variant_key] = guid

            # All combinations of alternatives (if both exist)
            for lit_alt in lit_alts:
                for eng_alt in eng_alts:
                    for variant_key in generate_word_key_variants(lit_alt, eng_alt):
                        if variant_key not in mappings:
                            mappings[variant_key] = guid

    return mappings


def load_wireword_verbs() -> Dict[str, str]:
    """
    Load wireword verbs JSON and create mappings for all grammatical forms.

    Maps conjugated forms like "aš mokau-I teach" to GUID with form suffix (e.g., V01_017_1sg_pres).

    Returns:
        Dict mapping wordKey -> GUID with form suffix
    """
    mappings = {}

    if not os.path.exists(WIREWORD_VERBS_FILE):
        return mappings

    try:
        with open(WIREWORD_VERBS_FILE, 'r', encoding='utf-8') as f:
            verbs_data = json.load(f)

        for verb_entry in verbs_data:
            base_guid = verb_entry.get('guid')
            base_lithuanian = verb_entry.get('base_lithuanian', '')
            base_english = verb_entry.get('base_english', '')
            grammatical_forms = verb_entry.get('grammatical_forms', {})

            if not base_guid:
                continue

            # Map the infinitive form (base form)
            if base_lithuanian and base_english:
                for variant_key in generate_word_key_variants(base_lithuanian, base_english):
                    if variant_key not in mappings:
                        mappings[variant_key] = base_guid

            # Map each grammatical form
            # formKey follows pattern: {person}{number}_{gender}_{tense}
            # Examples: 1sg_pres, 3sg_m_past, 2pl_fut
            for form_key, form_data in grammatical_forms.items():
                lithuanian = form_data.get('lithuanian', '')
                english = form_data.get('english', '')

                if not lithuanian or not english:
                    continue

                # Create GUID with form suffix: V01_017_1sg_pres
                guid_with_form = f"{base_guid}_{form_key}"

                # Generate word key variants for this conjugated form
                for variant_key in generate_word_key_variants(lithuanian, english):
                    if variant_key not in mappings:
                        mappings[variant_key] = guid_with_form

        print(f"Loaded {len(mappings)} verb form mappings from wireword_verbs.json", file=sys.stderr)

    except Exception as e:
        print(f"Error loading wireword verbs: {e}", file=sys.stderr)

    return mappings


def load_legacy_file(filepath: str) -> Dict[str, str]:
    """
    Load legacy phrases/verbs/nouns files that don't have GUIDs.

    These will map to themselves (wordKey -> wordKey) so they pass through unchanged.
    """
    mappings = {}

    if not os.path.exists(filepath):
        return mappings

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        namespace = {}
        exec(content, namespace)

        # Look for dictionaries with lists of word entries
        for var_name, var_value in namespace.items():
            if isinstance(var_value, dict):
                # phrases_one, verbs_one, etc.
                for category_data in var_value.values():
                    if isinstance(category_data, list):
                        for entry in category_data:
                            if isinstance(entry, dict) and 'english' in entry and 'lithuanian' in entry:
                                eng = entry['english']
                                lit = entry['lithuanian']

                                # Generate key variants
                                for key in generate_word_key_variants(lit, eng):
                                    # Map to itself (no GUID available)
                                    if key not in mappings:
                                        mappings[key] = key
    except Exception as e:
        print(f"Error loading legacy file {filepath}: {e}", file=sys.stderr)

    return mappings


def build_mapping_table() -> Dict[str, str]:
    """
    Build complete mapping table from all dictionary files.

    Returns:
        Dict mapping wordKey -> GUID (or wordKey -> wordKey for legacy entries)
    """
    mapping_table = {}

    # Process GUID-based dictionary files
    if os.path.exists(DICTIONARY_DIR):
        for filename in sorted(os.listdir(DICTIONARY_DIR)):
            if filename.endswith('_dictionary.py'):
                filepath = os.path.join(DICTIONARY_DIR, filename)
                print(f"Processing {filename}...", file=sys.stderr)

                file_mappings = load_dictionary_file(filepath)

                # Check for conflicts
                for word_key, guid in file_mappings.items():
                    if word_key in mapping_table and mapping_table[word_key] != guid:
                        print(f"Warning: Conflicting mapping for '{word_key}': "
                              f"{mapping_table[word_key]} vs {guid}", file=sys.stderr)
                    mapping_table[word_key] = guid

    # Process wireword verbs (with grammatical forms)
    print(f"Processing wireword_verbs.json...", file=sys.stderr)
    verb_mappings = load_wireword_verbs()
    for word_key, guid in verb_mappings.items():
        if word_key in mapping_table and mapping_table[word_key] != guid:
            print(f"Warning: Conflicting mapping for '{word_key}': "
                  f"{mapping_table[word_key]} vs {guid}", file=sys.stderr)
        mapping_table[word_key] = guid

    # Process legacy files (phrases, verbs without GUIDs)
    for legacy_file in [PHRASES_FILE, VERBS_FILE]:
        if os.path.exists(legacy_file):
            filename = os.path.basename(legacy_file)
            print(f"Processing legacy {filename}...", file=sys.stderr)

            legacy_mappings = load_legacy_file(legacy_file)

            for word_key, value in legacy_mappings.items():
                # Only add if not already in mapping (GUIDs take precedence)
                if word_key not in mapping_table:
                    mapping_table[word_key] = value

    print(f"\nBuilt mapping table with {len(mapping_table)} entries", file=sys.stderr)
    return mapping_table


def get_mapping_table() -> Dict[str, str]:
    """
    Get the GUID mapping table (cached for performance).

    Returns:
        Dict mapping wordKey -> GUID
    """
    if not hasattr(get_mapping_table, '_cache'):
        get_mapping_table._cache = build_mapping_table()
    return get_mapping_table._cache


if __name__ == '__main__':
    # Build and display mapping table
    mapping = build_mapping_table()

    print("\n=== Sample Mappings ===")
    for i, (word_key, guid) in enumerate(sorted(mapping.items())[:10]):
        print(f"{word_key} -> {guid}")

    print(f"\nTotal mappings: {len(mapping)}")
