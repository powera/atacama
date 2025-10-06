#!/usr/bin/env python3
"""
Migrate user stats from wordKey format to GUID format.

This script migrates all stats files for one or more users:
- Main journey stats (lithuanian.json)
- Daily snapshots (current and yesterday, both .json and .json.gz)

Usage:
    python migrate_user_stats.py --user-id 123 [--dry-run]
    python migrate_user_stats.py --all-users [--dry-run]
"""

import argparse
import os
import sys
from typing import List

# Add project root to Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import constants
from tools.guid_migration.convert_stats import convert_stats_file, ConversionStats


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
    Get all stats files for a user that need migration.

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


def migrate_user(user_id: str, dry_run: bool = False, max_unmapped_ratio: float = 0.20) -> bool:
    """
    Migrate all stats files for a single user.

    Args:
        user_id: User ID to migrate
        dry_run: If True, don't actually modify files
        max_unmapped_ratio: Maximum ratio of unmapped words allowed (default 0.20 = 20%)

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Migrating user {user_id} (dry_run={dry_run})")
    print(f"{'='*60}")

    stats_files = get_user_stats_files(user_id)

    if not stats_files:
        print(f"No stats files found for user {user_id}")
        return True

    print(f"Found {len(stats_files)} files to migrate")

    # Track overall statistics
    total_words = 0
    total_converted = 0
    total_unmapped = 0
    failed_files = []

    # Convert each file
    for filepath in stats_files:
        filename = os.path.basename(filepath)
        print(f"\nProcessing: {filename}")

        stats, success = convert_stats_file(filepath, dry_run=dry_run, max_unmapped_ratio=max_unmapped_ratio)

        if not success:
            print(f"  FAILED: {filename}")
            failed_files.append(filename)
            continue

        # Accumulate stats
        total_words += stats.total_words
        total_converted += stats.converted_words
        total_unmapped += stats.unmapped_words

        print(f"  {stats}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Migration Summary for user {user_id}")
    print(f"{'='*60}")
    print(f"Total files processed: {len(stats_files)}")
    print(f"Files failed: {len(failed_files)}")
    print(f"Total words: {total_words}")
    print(f"Converted: {total_converted}")
    print(f"Unmapped: {total_unmapped}")

    if total_words > 0:
        print(f"Success rate: {total_converted/total_words:.1%}")

    if failed_files:
        print(f"\nFailed files:")
        for filename in failed_files:
            print(f"  - {filename}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Migrate Trakaido user stats from wordKey to GUID format'
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--user-id', type=str, help='User ID to migrate')
    group.add_argument('--all-users', action='store_true', help='Migrate all users')

    parser.add_argument('--dry-run', action='store_true',
                        help='Perform dry run without modifying files')
    parser.add_argument('--max-unmapped', type=float, default=0.20,
                        help='Maximum ratio of unmapped words allowed (default: 0.20 = 20%%)')

    args = parser.parse_args()

    # Determine which users to migrate
    if args.all_users:
        user_ids = get_all_user_ids()
        if not user_ids:
            print("No users found in trakaido data directory")
            return 1
        print(f"Found {len(user_ids)} users to migrate: {', '.join(user_ids)}")
    else:
        user_ids = [args.user_id]

    # Migrate each user
    failed_users = []
    for user_id in user_ids:
        success = migrate_user(user_id, dry_run=args.dry_run, max_unmapped_ratio=args.max_unmapped)
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
        print("\n** MIGRATION COMPLETE **")

    return 0


if __name__ == '__main__':
    sys.exit(main())
