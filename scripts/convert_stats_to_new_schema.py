#!/usr/bin/env python3
"""
Convert all user stats files (journey stats and daily snapshots) from old schema to new schema.

This script:
1. Finds all stats files for all users and languages
2. Converts old schema format to new schema format
3. Rewrites files in place (handles both regular JSON and GZIP files)

Usage:
    python scripts/convert_stats_to_new_schema.py [--data-dir PATH] [--dry-run]

    --data-dir PATH  : Path to the data directory (default: data/trakaido)
    --dry-run        : Show what would be converted without making changes
"""

import argparse
import gzip
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Set

# Schema conversion constants
OLD_STAT_TYPES = {"multipleChoice", "listeningEasy", "listeningHard", "typing", "blitz", "sentences"}
OLD_META_TYPES = {"exposed", "lastSeen", "lastCorrectAnswer", "lastIncorrectAnswer", "markedAsKnown"}

DIRECT_PRACTICE_TYPES = {
    "multipleChoice_englishToTarget",
    "multipleChoice_targetToEnglish",
    "listening_targetAudioToTarget",
    "listening_targetAudioToEnglish",
    "typing_englishToTarget",
    "typing_targetToEnglish",
    "blitz_englishToTarget",
    "blitz_targetToEnglish"
}


def create_empty_word_stats() -> Dict[str, Any]:
    """Create an empty word stats object with the new schema structure."""
    return {
        "exposed": False,
        "directPractice": {
            "multipleChoice_englishToTarget": {"correct": 0, "incorrect": 0},
            "multipleChoice_targetToEnglish": {"correct": 0, "incorrect": 0},
            "listening_targetAudioToTarget": {"correct": 0, "incorrect": 0},
            "listening_targetAudioToEnglish": {"correct": 0, "incorrect": 0},
            "typing_englishToTarget": {"correct": 0, "incorrect": 0},
            "typing_targetToEnglish": {"correct": 0, "incorrect": 0},
            "blitz_englishToTarget": {"correct": 0, "incorrect": 0},
            "blitz_targetToEnglish": {"correct": 0, "incorrect": 0}
        },
        "contextualExposure": {
            "sentences": {"correct": 0, "incorrect": 0}
        },
        "practiceHistory": {
            "lastSeen": None,
            "lastCorrectAnswer": None,
            "lastIncorrectAnswer": None
        }
    }


def is_old_schema(word_stats: Dict[str, Any]) -> bool:
    """Check if word stats are in old schema format."""
    # Check if it has any old stat types at the top level
    for old_type in OLD_STAT_TYPES:
        if old_type in word_stats:
            return True
    # Check if it has old meta types at the top level (except exposed which exists in both)
    if "lastSeen" in word_stats or "lastCorrectAnswer" in word_stats or "lastIncorrectAnswer" in word_stats:
        return True
    return False


def migrate_old_to_new_schema(old_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate word stats from old schema to new schema.

    Migration strategy: All old stats go to target->english direction.
    """
    new_stats = create_empty_word_stats()

    # Migrate top-level flags
    new_stats["exposed"] = old_stats.get("exposed", False)
    if "markedAsKnown" in old_stats:
        new_stats["markedAsKnown"] = old_stats["markedAsKnown"]

    # Migrate stat types to target->english direction
    if "multipleChoice" in old_stats:
        new_stats["directPractice"]["multipleChoice_targetToEnglish"] = old_stats["multipleChoice"]

    if "listeningEasy" in old_stats:
        new_stats["directPractice"]["listening_targetAudioToTarget"] = old_stats["listeningEasy"]

    if "listeningHard" in old_stats:
        new_stats["directPractice"]["listening_targetAudioToEnglish"] = old_stats["listeningHard"]

    if "typing" in old_stats:
        new_stats["directPractice"]["typing_targetToEnglish"] = old_stats["typing"]

    if "blitz" in old_stats:
        new_stats["directPractice"]["blitz_targetToEnglish"] = old_stats["blitz"]

    if "sentences" in old_stats:
        new_stats["contextualExposure"]["sentences"] = old_stats["sentences"]

    # Migrate timestamps
    new_stats["practiceHistory"]["lastSeen"] = old_stats.get("lastSeen", None)
    new_stats["practiceHistory"]["lastCorrectAnswer"] = old_stats.get("lastCorrectAnswer", None)
    new_stats["practiceHistory"]["lastIncorrectAnswer"] = old_stats.get("lastIncorrectAnswer", None)

    return new_stats


def convert_stats_file(stats_data: Dict[str, Any]) -> tuple[Dict[str, Any], int]:
    """Convert a stats file from old schema to new schema.

    Returns:
        tuple: (converted_data, number_of_words_converted)
    """
    if not isinstance(stats_data, dict) or "stats" not in stats_data:
        return stats_data, 0

    converted_count = 0
    converted_stats = {}

    for word_key, word_stats in stats_data["stats"].items():
        if is_old_schema(word_stats):
            converted_stats[word_key] = migrate_old_to_new_schema(word_stats)
            converted_count += 1
        else:
            converted_stats[word_key] = word_stats

    return {"stats": converted_stats}, converted_count


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load a JSON file (handles both regular and GZIP)."""
    if file_path.suffix == '.gz':
        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            return json.load(f)
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)


def save_json_file(file_path: Path, data: Dict[str, Any]):
    """Save a JSON file (handles both regular and GZIP)."""
    if file_path.suffix == '.gz':
        with gzip.open(file_path, 'wt', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def scan_language_dir(lang_dir: Path, journey_stats_files: list[Path], daily_snapshot_files: list[Path]):
    """Scan a language directory for stats files."""
    # Journey stats file
    stats_file = lang_dir / "stats.json"
    if stats_file.exists():
        journey_stats_files.append(stats_file)

    # Daily snapshot files
    daily_dir = lang_dir / "daily"
    if daily_dir.exists() and daily_dir.is_dir():
        for daily_file in daily_dir.iterdir():
            if daily_file.is_file() and (
                daily_file.suffix == '.json' or
                (daily_file.suffix == '.gz' and daily_file.stem.endswith('.json'))
            ):
                daily_snapshot_files.append(daily_file)


def find_all_stats_files(data_dir: Path) -> tuple[list[Path], list[Path]]:
    """Find all stats files in the data directory.

    Uses production structure: data/trakaido/{user_id}/{language}/stats.json

    Returns:
        tuple: (list of journey stats files, list of daily snapshot files)
    """
    journey_stats_files = []
    daily_snapshot_files = []

    # Production structure: {user_id}/{language}/daily/*.json
    for user_dir in data_dir.iterdir():
        if not user_dir.is_dir() or user_dir.name.startswith('.'):
            continue

        # Skip test/backup directories - only process numeric user IDs
        if not user_dir.name.isdigit():
            print(f"Skipping non-numeric user directory: {user_dir.name}")
            continue

        # Check each language directory
        for lang_dir in user_dir.iterdir():
            if lang_dir.is_dir():
                scan_language_dir(lang_dir, journey_stats_files, daily_snapshot_files)

    return journey_stats_files, daily_snapshot_files


def main():
    parser = argparse.ArgumentParser(
        description="Convert all user stats files from old schema to new schema"
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/trakaido',
        help='Path to the data directory (default: data/trakaido)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be converted without making changes'
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    if not data_dir.exists():
        print(f"Error: Data directory does not exist: {data_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning for stats files in: {data_dir}")
    print()

    # Find all stats files
    journey_stats_files, daily_snapshot_files = find_all_stats_files(data_dir)

    print(f"Found {len(journey_stats_files)} journey stats files")
    print(f"Found {len(daily_snapshot_files)} daily snapshot files")
    print()

    if args.dry_run:
        print("DRY RUN MODE - No files will be modified")
        print()

    # Convert journey stats files
    total_journey_converted = 0
    total_journey_words = 0

    print("Converting journey stats files...")
    for stats_file in journey_stats_files:
        try:
            data = load_json_file(stats_file)
            converted_data, converted_count = convert_stats_file(data)

            if converted_count > 0:
                total_journey_converted += 1
                total_journey_words += converted_count

                rel_path = stats_file.relative_to(data_dir)
                print(f"  {rel_path}: {converted_count} words converted")

                if not args.dry_run:
                    save_json_file(stats_file, converted_data)

        except Exception as e:
            print(f"  ERROR processing {stats_file}: {e}", file=sys.stderr)

    print()

    # Convert daily snapshot files
    total_daily_converted = 0
    total_daily_words = 0

    print("Converting daily snapshot files...")
    for snapshot_file in daily_snapshot_files:
        try:
            data = load_json_file(snapshot_file)
            converted_data, converted_count = convert_stats_file(data)

            if converted_count > 0:
                total_daily_converted += 1
                total_daily_words += converted_count

                rel_path = snapshot_file.relative_to(data_dir)
                print(f"  {rel_path}: {converted_count} words converted")

                if not args.dry_run:
                    save_json_file(snapshot_file, converted_data)

        except Exception as e:
            print(f"  ERROR processing {snapshot_file}: {e}", file=sys.stderr)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Journey stats files converted: {total_journey_converted} ({total_journey_words} words)")
    print(f"Daily snapshot files converted: {total_daily_converted} ({total_daily_words} words)")
    print(f"Total files converted: {total_journey_converted + total_daily_converted}")
    print(f"Total words converted: {total_journey_words + total_daily_words}")

    if args.dry_run:
        print()
        print("This was a DRY RUN. No files were modified.")
        print("Run without --dry-run to perform the actual conversion.")
    else:
        print()
        print("Conversion complete!")


if __name__ == '__main__':
    main()
