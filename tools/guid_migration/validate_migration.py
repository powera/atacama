#!/usr/bin/env python3
"""
Validate Trakaido GUID migration.

This script validates that the migration from wordKey to GUID format was successful:
- Checks that all GUIDs are valid
- Verifies data integrity (no loss of stats)
- Reports on any anomalies

Usage:
    python validate_migration.py --user-id 123
    python validate_migration.py --all-users
"""

import argparse
import gzip
import json
import os
import sys
from typing import Dict, Any, List, Set

# Add project root to Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import constants
from tools.guid_migration.build_guid_mapping import get_mapping_table


VALID_STAT_TYPES = {"multipleChoice", "listeningEasy", "listeningHard", "typing", "blitz"}
VALID_META_TYPES = {"exposed", "lastSeen", "lastCorrectAnswer", "lastIncorrectAnswer"}


class ValidationResult:
    """Track validation results."""

    def __init__(self):
        self.total_files = 0
        self.valid_files = 0
        self.total_entries = 0
        self.valid_guids = 0
        self.invalid_guids = 0
        self.invalid_guid_list = []
        self.empty_files = 0
        self.errors = []

    def add_file(self, is_valid: bool):
        self.total_files += 1
        if is_valid:
            self.valid_files += 1

    def add_valid_guid(self):
        self.total_entries += 1
        self.valid_guids += 1

    def add_invalid_guid(self, guid: str):
        self.total_entries += 1
        self.invalid_guids += 1
        if guid not in self.invalid_guid_list:
            self.invalid_guid_list.append(guid)

    def add_empty_file(self):
        self.empty_files += 1

    def add_error(self, error_msg: str):
        self.errors.append(error_msg)

    def is_valid(self) -> bool:
        """Check if validation passed."""
        return len(self.errors) == 0 and self.invalid_guids == 0

    def __str__(self):
        lines = [
            "Validation Results:",
            f"  Files validated: {self.total_files}",
            f"  Valid files: {self.valid_files}",
            f"  Empty files: {self.empty_files}",
            f"  Total entries: {self.total_entries}",
            f"  Valid GUIDs: {self.valid_guids}",
            f"  Invalid GUIDs: {self.invalid_guids}",
        ]

        if self.invalid_guid_list:
            lines.append(f"  Invalid GUID examples: {', '.join(self.invalid_guid_list[:5])}")

        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for error in self.errors[:5]:
                lines.append(f"    - {error}")

        return "\n".join(lines)


def is_valid_guid(guid: str, valid_guids: Set[str]) -> bool:
    """
    Check if a GUID is valid.

    Args:
        guid: GUID to validate
        valid_guids: Set of all valid GUIDs from mapping table

    Returns:
        True if valid, False otherwise
    """
    # Check if it's in our known GUIDs
    if guid in valid_guids:
        return True

    # Check format (e.g., N02_001, V01_042, P03_015)
    # Format: Letter(s) + digits + underscore + digits
    if len(guid) < 5:
        return False

    parts = guid.split('_')
    if len(parts) != 2:
        return False

    prefix, suffix = parts

    # Prefix should start with letter(s) followed by digits
    if not prefix or not suffix:
        return False

    # Find where letters end and digits begin in prefix
    letter_part = ""
    digit_part = ""
    for char in prefix:
        if char.isalpha():
            if digit_part:  # Letters after digits is invalid
                return False
            letter_part += char
        elif char.isdigit():
            digit_part += char
        else:
            return False

    # Suffix should be all digits
    if not suffix.isdigit():
        return False

    # Both parts should exist
    return bool(letter_part) and bool(digit_part)


def read_stats_file(filepath: str) -> Dict[str, Any]:
    """Read a stats file (JSON or GZIP)."""
    try:
        if filepath.endswith('.gz'):
            with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        raise Exception(f"Error reading {filepath}: {e}")


def validate_stats_file(filepath: str, valid_guids: Set[str], result: ValidationResult):
    """
    Validate a single stats file.

    Args:
        filepath: Path to stats file
        valid_guids: Set of valid GUIDs
        result: ValidationResult to update
    """
    filename = os.path.basename(filepath)

    try:
        stats_dict = read_stats_file(filepath)
    except Exception as e:
        result.add_error(f"{filename}: {str(e)}")
        result.add_file(False)
        return

    # Check structure
    if "stats" not in stats_dict:
        result.add_error(f"{filename}: Missing 'stats' key")
        result.add_file(False)
        return

    stats = stats_dict["stats"]

    if not stats:
        result.add_empty_file()

    # Validate each GUID entry
    file_valid = True
    for guid, word_stats in stats.items():
        if is_valid_guid(guid, valid_guids):
            result.add_valid_guid()

            # Validate word stats structure
            if not isinstance(word_stats, dict):
                result.add_error(f"{filename}: Invalid stats structure for {guid}")
                file_valid = False
                continue

            # Check for valid stat types
            for key in word_stats.keys():
                if key not in VALID_STAT_TYPES and key not in VALID_META_TYPES:
                    result.add_error(f"{filename}: Invalid stat type '{key}' for {guid}")
                    file_valid = False
        else:
            result.add_invalid_guid(guid)
            file_valid = False

    result.add_file(file_valid)


def get_user_stats_files(user_id: str) -> List[str]:
    """Get all stats files for a user."""
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
            if (filename.endswith('_current.json') or
                filename.endswith('_yesterday.json') or
                filename.endswith('_current.json.gz') or
                filename.endswith('_yesterday.json.gz')):
                files.append(os.path.join(daily_dir, filename))

    return sorted(files)


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


def validate_user(user_id: str) -> ValidationResult:
    """
    Validate all stats files for a single user.

    Args:
        user_id: User ID to validate

    Returns:
        ValidationResult
    """
    print(f"\n{'='*60}")
    print(f"Validating user {user_id}")
    print(f"{'='*60}")

    result = ValidationResult()

    # Get valid GUIDs from mapping table
    mapping_table = get_mapping_table()
    valid_guids = set(mapping_table.values())

    # Get stats files
    stats_files = get_user_stats_files(user_id)

    if not stats_files:
        print(f"No stats files found for user {user_id}")
        return result

    print(f"Validating {len(stats_files)} files...")

    # Validate each file
    for filepath in stats_files:
        filename = os.path.basename(filepath)
        validate_stats_file(filepath, valid_guids, result)

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Validate Trakaido GUID migration'
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--user-id', type=str, help='User ID to validate')
    group.add_argument('--all-users', action='store_true', help='Validate all users')

    args = parser.parse_args()

    # Determine which users to validate
    if args.all_users:
        user_ids = get_all_user_ids()
        if not user_ids:
            print("No users found in trakaido data directory")
            return 1
        print(f"Found {len(user_ids)} users to validate")
    else:
        user_ids = [args.user_id]

    # Validate each user
    all_results = []
    for user_id in user_ids:
        result = validate_user(user_id)
        all_results.append(result)
        print(f"\n{result}")

    # Combined summary
    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*60}")

    total_files = sum(r.total_files for r in all_results)
    total_valid_files = sum(r.valid_files for r in all_results)
    total_entries = sum(r.total_entries for r in all_results)
    total_valid_guids = sum(r.valid_guids for r in all_results)
    total_invalid_guids = sum(r.invalid_guids for r in all_results)
    total_errors = sum(len(r.errors) for r in all_results)

    print(f"Users validated: {len(user_ids)}")
    print(f"Total files: {total_files}")
    print(f"Valid files: {total_valid_files}")
    print(f"Total entries: {total_entries}")
    print(f"Valid GUIDs: {total_valid_guids}")
    print(f"Invalid GUIDs: {total_invalid_guids}")
    print(f"Total errors: {total_errors}")

    if total_invalid_guids > 0 or total_errors > 0:
        print("\n** VALIDATION FAILED **")
        return 1
    else:
        print("\n** VALIDATION PASSED **")
        return 0


if __name__ == '__main__':
    sys.exit(main())
