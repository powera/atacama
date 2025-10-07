#!/usr/bin/env python3
"""
Convert GUID suffixes from wireword format to wordstats format.

This script converts verb form suffixes in user stats from the wireword format
(e.g., V01_025_3sg_f_pres) to the wordstats format (e.g., V01_025_3s-f_pres).

Wireword format: {person}{sg|pl}_{m|f}_{tense}
  Examples: 1sg_pres, 3sg_m_past, 3pl_f_fut

Wordstats format: {person}{s|p}-{m|f}_{tense}
  Examples: 1s_pres, 3s-m_past, 3p-f_fut

Usage:
    python convert_wireword_to_wordstats.py --user-id 123 [--dry-run]
    python convert_wireword_to_wordstats.py --all-users [--dry-run]
"""

import argparse
import gzip
import json
import os
import re
import sys
from typing import Dict, Any, List, Tuple

# Add project root to Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import constants


def convert_wireword_suffix_to_wordstats(suffix: str) -> str:
    """
    Convert a wireword format suffix to wordstats format.

    Wireword format: {person}{sg|pl}_{m|f}_{tense}
    Wordstats format: {person}{s|p}-{m|f}_{tense}

    Examples:
        1sg_pres -> 1s_pres
        3sg_m_pres -> 3s-m_pres
        3pl_f_past -> 3p-f_past
        2pl_fut -> 2p_fut

    Args:
        suffix: The wireword format suffix

    Returns:
        The wordstats format suffix
    """
    # Pattern: {person}sg_{gender}_{tense} or {person}pl_{gender}_{tense} or {person}sg_{tense} or {person}pl_{tense}

    # First, handle cases with gender: 3sg_m_pres -> 3s-m_pres
    pattern_with_gender = r'^(\d)(sg|pl)_([mf])_(.+)$'
    match = re.match(pattern_with_gender, suffix)
    if match:
        person, number, gender, tense = match.groups()
        short_number = 's' if number == 'sg' else 'p'
        return f"{person}{short_number}-{gender}_{tense}"

    # Handle cases without gender: 1sg_pres -> 1s_pres
    pattern_without_gender = r'^(\d)(sg|pl)_(.+)$'
    match = re.match(pattern_without_gender, suffix)
    if match:
        person, number, tense = match.groups()
        short_number = 's' if number == 'sg' else 'p'
        return f"{person}{short_number}_{tense}"

    # If no match, return unchanged
    return suffix


def convert_guid_key(guid_key: str) -> str:
    """
    Convert a GUID key from wireword format to wordstats format.

    Examples:
        V01_025_3sg_f_pres -> V01_025_3s-f_pres
        N08_011 -> N08_011 (unchanged)

    Args:
        guid_key: The GUID key (possibly with wireword suffix)

    Returns:
        The GUID key with wordstats suffix (if applicable)
    """
    # Check if this is a verb form with suffix (has more than 2 underscore-separated parts)
    parts = guid_key.split('_')

    if len(parts) <= 2:
        # No suffix, return as-is
        return guid_key

    # Has suffix: base_suffix format like V01_025_3sg_f_pres
    # parts[0] = V01, parts[1] = 025, parts[2:] = suffix parts
    base = '_'.join(parts[:2])  # V01_025
    suffix = '_'.join(parts[2:])  # 3sg_f_pres

    converted_suffix = convert_wireword_suffix_to_wordstats(suffix)
    return f"{base}_{converted_suffix}"


class ConversionStats:
    """Track conversion statistics."""

    def __init__(self):
        self.total_keys = 0
        self.converted_keys = 0
        self.unchanged_keys = 0
        self.conversions = []  # List of (old_key, new_key) tuples

    def add_converted(self, old_key: str, new_key: str):
        self.total_keys += 1
        self.converted_keys += 1
        self.conversions.append((old_key, new_key))

    def add_unchanged(self):
        self.total_keys += 1
        self.unchanged_keys += 1

    def __str__(self):
        return (f"Conversion Stats: {self.converted_keys}/{self.total_keys} converted, "
                f"{self.unchanged_keys} unchanged")


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


def convert_stats_dict(stats_dict: Dict[str, Any], conversion_stats: ConversionStats,
                       dry_run: bool = False) -> Dict[str, Any]:
    """
    Convert a stats dictionary from wireword format to wordstats format.

    Args:
        stats_dict: Dictionary with "stats" key containing word stats
        conversion_stats: ConversionStats object to track progress
        dry_run: If True, log conversions; if False, perform silently

    Returns:
        Converted stats dictionary with wordstats format keys
    """
    if "stats" not in stats_dict:
        return stats_dict

    old_stats = stats_dict["stats"]
    new_stats = {}

    for old_key, word_stats in old_stats.items():
        new_key = convert_guid_key(old_key)

        if new_key != old_key:
            # Key was converted
            conversion_stats.add_converted(old_key, new_key)
            if dry_run:
                print(f"  {old_key} -> {new_key}")
        else:
            # Key unchanged
            conversion_stats.add_unchanged()

        # Check if we already have stats for this key (duplicate after conversion)
        if new_key in new_stats:
            # Merge with existing stats
            new_stats[new_key] = merge_word_stats(new_stats[new_key], word_stats)
        else:
            new_stats[new_key] = word_stats

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
                       dry_run: bool = False) -> Tuple[ConversionStats, bool]:
    """
    Convert a single stats file from wireword to wordstats format.

    Args:
        input_path: Path to input stats file
        output_path: Path to output stats file (defaults to input_path if None)
        dry_run: If True, don't write output file

    Returns:
        Tuple of (ConversionStats, success_boolean)
    """
    if output_path is None:
        output_path = input_path

    # Read input file
    try:
        stats_dict = read_stats_file(input_path)
    except Exception as e:
        print(f"Error reading {input_path}: {e}", file=sys.stderr)
        return ConversionStats(), False

    # Convert stats
    conversion_stats = ConversionStats()
    converted_dict = convert_stats_dict(stats_dict, conversion_stats, dry_run)

    # Write output file (unless dry-run)
    if not dry_run:
        try:
            write_stats_file(output_path, converted_dict)
        except Exception as e:
            print(f"Error writing {output_path}: {e}", file=sys.stderr)
            return conversion_stats, False

    return conversion_stats, True


def get_all_user_ids() -> List[str]:
    """Get all user IDs from the trakaido data directory."""
    trakaido_dir = os.path.join(constants.DATA_DIR, "trakaido")

    if not os.path.exists(trakaido_dir):
        return []

    user_ids = []
    for entry in os.listdir(trakaido_dir):
        user_path = os.path.join(trakaido_dir, entry)
        if os.path.isdir(user_path) and entry.isdigit():
            user_ids.append(entry)

    return sorted(user_ids, key=int)


def get_user_stats_files(user_id: str) -> List[str]:
    """
    Get all stats files for a user that need conversion.

    Returns:
        List of file paths
    """
    user_dir = os.path.join(constants.DATA_DIR, "trakaido", user_id)
    daily_dir = os.path.join(user_dir, "daily")

    files = []

    # Main journey stats file
    lithuanian_file = os.path.join(user_dir, "lithuanian.json")
    if os.path.exists(lithuanian_file):
        files.append(lithuanian_file)

    # Daily snapshot files
    if os.path.exists(daily_dir):
        for filename in os.listdir(daily_dir):
            # Match current/yesterday snapshots (both .json and .json.gz)
            if (filename.endswith('_current.json') or
                filename.endswith('_yesterday.json') or
                filename.endswith('_current.json.gz') or
                filename.endswith('_yesterday.json.gz')):
                files.append(os.path.join(daily_dir, filename))

    return sorted(files)


def convert_user(user_id: str, dry_run: bool = False) -> bool:
    """
    Convert all stats files for a single user.

    Args:
        user_id: User ID to convert
        dry_run: If True, don't actually modify files

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Converting user {user_id} (dry_run={dry_run})")
    print(f"{'='*60}")

    stats_files = get_user_stats_files(user_id)

    if not stats_files:
        print(f"No stats files found for user {user_id}")
        return True

    print(f"Found {len(stats_files)} files to convert")

    # Track overall statistics
    total_keys = 0
    total_converted = 0
    failed_files = []

    # Convert each file
    for filepath in stats_files:
        filename = os.path.basename(filepath)
        print(f"\nProcessing: {filename}")

        stats, success = convert_stats_file(filepath, dry_run=dry_run)

        if not success:
            print(f"  FAILED: {filename}")
            failed_files.append(filename)
            continue

        # Accumulate stats
        total_keys += stats.total_keys
        total_converted += stats.converted_keys

        print(f"  {stats}")

        # Show sample conversions in dry-run mode
        if dry_run and stats.conversions:
            print(f"  Sample conversions:")
            for old_key, new_key in stats.conversions[:5]:
                print(f"    {old_key} -> {new_key}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Conversion Summary for user {user_id}")
    print(f"{'='*60}")
    print(f"Total files processed: {len(stats_files)}")
    print(f"Files failed: {len(failed_files)}")
    print(f"Total keys: {total_keys}")
    print(f"Converted: {total_converted}")

    if failed_files:
        print(f"\nFailed files:")
        for filename in failed_files:
            print(f"  - {filename}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Convert Trakaido stats from wireword to wordstats format'
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--user-id', type=str, help='User ID to convert')
    group.add_argument('--all-users', action='store_true', help='Convert all users')

    parser.add_argument('--dry-run', action='store_true',
                        help='Perform dry run without modifying files')

    args = parser.parse_args()

    # Determine which users to convert
    if args.all_users:
        user_ids = get_all_user_ids()
        if not user_ids:
            print("No users found in trakaido data directory")
            return 1
        print(f"Found {len(user_ids)} users to convert: {', '.join(user_ids)}")
    else:
        user_ids = [args.user_id]

    # Convert each user
    failed_users = []
    for user_id in user_ids:
        success = convert_user(user_id, dry_run=args.dry_run)
        if not success:
            failed_users.append(user_id)

    # Final summary
    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"Users processed: {len(user_ids)}")
    print(f"Users succeeded: {len(user_ids) - len(failed_users)}")
    print(f"Users failed: {len(failed_users)}")

    if failed_users:
        print(f"\nFailed users: {', '.join(failed_users)}")
        return 1

    if args.dry_run:
        print("\n** DRY RUN COMPLETE - No files were modified **")
    else:
        print("\n** CONVERSION COMPLETE **")

    return 0


if __name__ == '__main__':
    sys.exit(main())
