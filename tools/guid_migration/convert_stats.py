#!/usr/bin/env python3
"""
Core conversion logic for converting stats files from wordKey to GUID format.

This module handles the conversion of both regular JSON and GZIP JSON files,
translating all wordKey entries to GUID format while preserving all metadata.
"""

import gzip
import json
import os
import re
import sys
from typing import Dict, Any, Tuple

# Add project root to Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
sys.path.insert(0, PROJECT_ROOT)

from tools.guid_migration.build_guid_mapping import get_mapping_table


def normalize_word_key(word_key: str) -> str:
    """
    Normalize a word key to lowercase for case-insensitive lookup.

    This handles keys like "Aš Galiu-I Can" -> "aš galiu-i can"
    """
    return word_key.lower().strip()


class ConversionStats:
    """Track conversion statistics."""

    def __init__(self):
        self.total_words = 0
        self.converted_words = 0
        self.unmapped_words = 0
        self.unmapped_keys = []

    def add_converted(self):
        self.total_words += 1
        self.converted_words += 1

    def add_unmapped(self, word_key: str):
        self.total_words += 1
        self.unmapped_words += 1
        self.unmapped_keys.append(word_key)

    def get_unmapped_ratio(self) -> float:
        """Get ratio of unmapped words to total words."""
        if self.total_words == 0:
            return 0.0
        return self.unmapped_words / self.total_words

    def __str__(self):
        return (f"Conversion Stats: {self.converted_words}/{self.total_words} converted, "
                f"{self.unmapped_words} unmapped ({self.get_unmapped_ratio():.1%})")


def merge_word_stats(stats1: Dict[str, Any], stats2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two word stats dictionaries when duplicates are found.

    Strategy:
    - Add numeric counters (correct, incorrect)
    - Take latest timestamp (lastSeen, lastCorrectAnswer, lastIncorrectAnswer)
    - Keep boolean flags (exposed)
    """
    merged = {}

    # Get all keys from both stats
    all_keys = set(stats1.keys()) | set(stats2.keys())

    for key in all_keys:
        val1 = stats1.get(key)
        val2 = stats2.get(key)

        if val1 is None:
            merged[key] = val2
        elif val2 is None:
            merged[key] = val1
        elif isinstance(val1, dict) and isinstance(val2, dict):
            # Merge stat type dictionaries (e.g., multipleChoice)
            merged[key] = {}
            for subkey in set(val1.keys()) | set(val2.keys()):
                subval1 = val1.get(subkey, 0)
                subval2 = val2.get(subkey, 0)
                # Add counters
                merged[key][subkey] = subval1 + subval2
        elif isinstance(val1, bool) or isinstance(val2, bool):
            # For booleans, use OR (exposed=True if either is True)
            merged[key] = val1 or val2
        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            # For timestamps and other numbers, take the max (latest)
            merged[key] = max(val1, val2)
        else:
            # Default: prefer val2 (most recent)
            merged[key] = val2

    return merged


def is_guid_format(key: str) -> bool:
    """
    Check if a key is already in GUID format (e.g., N01_005, V01_017).

    GUID format: starts with letter(s), contains underscore, ends with digits.
    Examples: N01_005, V01_017, P03_042
    """
    import re
    return bool(re.match(r'^[A-Z]+\d+_\d+$', key))


def convert_stats_dict(stats_dict: Dict[str, Any], mapping_table: Dict[str, str],
                       conversion_stats: ConversionStats, dry_run: bool = False) -> Dict[str, Any]:
    """
    Convert a stats dictionary from wordKey format to GUID format.

    Args:
        stats_dict: Dictionary with "stats" key containing word stats
        mapping_table: Dict mapping wordKey -> GUID
        conversion_stats: ConversionStats object to track progress
        dry_run: If True, log unmapped words; if False, skip silently

    Returns:
        Converted stats dictionary with GUID keys
    """
    if "stats" not in stats_dict:
        return stats_dict

    old_stats = stats_dict["stats"]
    new_stats = {}

    for word_key, word_stats in old_stats.items():
        # If already in GUID format, keep as-is
        if is_guid_format(word_key):
            if word_key in new_stats:
                # Merge with existing stats
                new_stats[word_key] = merge_word_stats(new_stats[word_key], word_stats)
            else:
                new_stats[word_key] = word_stats
            conversion_stats.add_converted()
        else:
            # Normalize for case-insensitive lookup
            normalized_key = normalize_word_key(word_key)

            if normalized_key in mapping_table:
                # Convert to GUID
                guid = mapping_table[normalized_key]

                # Check if we already have stats for this GUID (duplicate)
                if guid in new_stats:
                    # Merge with existing stats
                    new_stats[guid] = merge_word_stats(new_stats[guid], word_stats)
                else:
                    new_stats[guid] = word_stats

                conversion_stats.add_converted()
            else:
                # Unmapped word
                conversion_stats.add_unmapped(word_key)
                if dry_run:
                    print(f"  [UNMAPPED] {word_key}")

    return {"stats": new_stats}


def read_stats_file(filepath: str) -> Dict[str, Any]:
    """
    Read a stats file (JSON or GZIP).

    Args:
        filepath: Path to the stats file

    Returns:
        Parsed stats dictionary
    """
    if filepath.endswith('.gz'):
        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
            return json.load(f)
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


def write_stats_file(filepath: str, stats_dict: Dict[str, Any]):
    """
    Write a stats file (JSON or GZIP).

    Args:
        filepath: Path to the output stats file
        stats_dict: Stats dictionary to write
    """
    if filepath.endswith('.gz'):
        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            json.dump(stats_dict, f, indent=2, ensure_ascii=False)
    else:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(stats_dict, f, indent=2, ensure_ascii=False)


def convert_stats_file(input_path: str, output_path: str = None,
                       dry_run: bool = False, max_unmapped_ratio: float = 0.20) -> Tuple[ConversionStats, bool]:
    """
    Convert a single stats file from wordKey to GUID format.

    Args:
        input_path: Path to input stats file
        output_path: Path to output stats file (defaults to input_path if None)
        dry_run: If True, don't write output file
        max_unmapped_ratio: Maximum ratio of unmapped words allowed (default 0.20 = 20%)

    Returns:
        Tuple of (ConversionStats, success_boolean)
    """
    if output_path is None:
        output_path = input_path

    # Get mapping table
    mapping_table = get_mapping_table()

    # Read input file
    try:
        stats_dict = read_stats_file(input_path)
    except Exception as e:
        print(f"Error reading {input_path}: {e}", file=sys.stderr)
        return ConversionStats(), False

    # Convert stats
    conversion_stats = ConversionStats()
    converted_dict = convert_stats_dict(stats_dict, mapping_table, conversion_stats, dry_run)

    # Check unmapped ratio
    unmapped_ratio = conversion_stats.get_unmapped_ratio()
    if unmapped_ratio > max_unmapped_ratio:
        print(f"ERROR: Too many unmapped words ({unmapped_ratio:.1%}) in {input_path}",
              file=sys.stderr)
        print(f"  Unmapped words: {conversion_stats.unmapped_words}/{conversion_stats.total_words}",
              file=sys.stderr)
        print(f"  Threshold: {max_unmapped_ratio:.1%}", file=sys.stderr)
        return conversion_stats, False

    # Write output file (unless dry-run)
    if not dry_run:
        try:
            write_stats_file(output_path, converted_dict)
        except Exception as e:
            print(f"Error writing {output_path}: {e}", file=sys.stderr)
            return conversion_stats, False

    return conversion_stats, True


if __name__ == '__main__':
    # Test conversion on a sample file
    if len(sys.argv) < 2:
        print("Usage: python convert_stats.py <stats_file> [--dry-run]")
        sys.exit(1)

    input_file = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    print(f"Converting {input_file} (dry_run={dry_run})...")
    stats, success = convert_stats_file(input_file, dry_run=dry_run)

    print(f"\n{stats}")
    if not success:
        print("Conversion FAILED")
        sys.exit(1)
    else:
        print("Conversion succeeded")
