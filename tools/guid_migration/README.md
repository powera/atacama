# Trakaido GUID Migration Tools

This directory contains scripts to migrate Trakaido user stats from the legacy `wordKey` format (e.g., `"akiniai-eyeglasses"`) to the new GUID format (e.g., `"N09_003"`).

## Overview

The migration consists of three main components:

1. **build_guid_mapping.py** - Builds a mapping table from wordKey → GUID by parsing dictionary files
2. **convert_stats.py** - Core conversion logic for transforming stats files
3. **migrate_user_stats.py** - Main migration script for users
4. **validate_migration.py** - Post-migration validation

## Prerequisites

- Python 3.7+
- Access to the `data/trakaido_wordlists/lang_lt/generated/dictionary/` directory
- Existing backups of user data (scripts do not create backups)

## Usage

### 1. Dry Run (Recommended First Step)

Test the migration on a single user without modifying files:

```bash
cd /path/to/atacama
python tools/guid_migration/migrate_user_stats.py --user-id 2 --dry-run
```

This will:
- Show which files would be converted
- Report unmapped words (words with no GUID match)
- Display conversion statistics
- Not modify any files

### 2. Migrate a Single User

```bash
python tools/guid_migration/migrate_user_stats.py --user-id 2
```

### 3. Migrate All Users

```bash
python tools/guid_migration/migrate_user_stats.py --all-users
```

Or with dry-run:

```bash
python tools/guid_migration/migrate_user_stats.py --all-users --dry-run
```

### 4. Adjust Unmapped Word Threshold

By default, files with >20% unmapped words will fail conversion. You can adjust this:

```bash
# Allow up to 25% unmapped words
python tools/guid_migration/migrate_user_stats.py --user-id 2 --max-unmapped 0.25

# Be more strict (only 10% unmapped)
python tools/guid_migration/migrate_user_stats.py --user-id 2 --max-unmapped 0.10
```

### 5. Validate Migration

After migration, validate that all files are using valid GUIDs:

```bash
python tools/guid_migration/validate_migration.py --user-id 2
```

Or validate all users:

```bash
python tools/guid_migration/validate_migration.py --all-users
```

## What Gets Migrated

For each user, the following files are converted:

- `lithuanian.json` - Main journey stats
- `daily/YYYY-MM-DD_current.json` - Daily current snapshots
- `daily/YYYY-MM-DD_yesterday.json` - Daily yesterday snapshots
- `daily/YYYY-MM-DD_current.json.gz` - Compressed daily current snapshots
- `daily/YYYY-MM-DD_yesterday.json.gz` - Compressed daily yesterday snapshots

Files that are **not** migrated:

- `corpuschoices.json` - Does not contain stats
- `daily/YYYY-MM-DD_nonces.json` - Does not contain word keys

## Error Handling

### Unmapped Words

If a word in the stats file cannot be found in the GUID mapping:

- **Dry-run mode**: Logs each unmapped word for review
- **Production mode**: Silently skips the unmapped word
- **Threshold check**: If >20% of words are unmapped (by default), migration fails
  - Adjustable with `--max-unmapped` flag (e.g., `--max-unmapped 0.25` for 25%)

### Failed Files

If a file fails to convert (e.g., exceeds unmapped threshold):

- The file is not modified
- The script continues with other files
- A summary report shows which files failed

## File Format

### Before Migration (wordKey format)

```json
{
  "stats": {
    "akiniai-eyeglasses": {
      "exposed": true,
      "multipleChoice": {
        "correct": 9,
        "incorrect": 0
      }
    }
  }
}
```

### After Migration (GUID format)

```json
{
  "stats": {
    "N09_003": {
      "exposed": true,
      "multipleChoice": {
        "correct": 9,
        "incorrect": 0
      }
    }
  }
}
```

## Testing Individual Files

You can test conversion on a single file:

```bash
python tools/guid_migration/convert_stats.py /path/to/lithuanian.json --dry-run
```

## Building the Mapping Table

To inspect the GUID mapping table:

```bash
python tools/guid_migration/build_guid_mapping.py
```

This will display sample mappings and statistics.

## Duplicate Handling

If multiple wordKeys map to the same GUID (e.g., `"apelsinas-orange"` and `"apelsinas-orange (fruit)"` both map to `N06_015`), the stats are automatically merged:

- Numeric counters (correct/incorrect) are **added together**
- Timestamps (lastSeen, lastCorrectAnswer) use the **latest value**
- Boolean flags (exposed) are **OR'd** (true if either is true)

## Notes

- All word stats (correct/incorrect counts, timestamps, etc.) are preserved during migration
- GZIP files are automatically handled (decompressed, converted, recompressed)
- The React app must support GUID format after migration
- Original file modification times are not preserved
- Parenthetical clarifications in wordKeys (e.g., `"orange (fruit)"`) are automatically stripped during mapping
