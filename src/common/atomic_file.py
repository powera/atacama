"""Atomic file writing utilities to prevent corruption from interrupted writes.

This module provides utilities for safely writing files with:
- Atomic writes (write to temp file, then rename)
- File locking to prevent concurrent access
- Automatic backup of previous version
- fsync to ensure data is flushed to disk

Usage:
    from common.atomic_file import atomic_write_json, atomic_write_text

    # Write JSON atomically
    atomic_write_json("/path/to/file.json", {"key": "value"})

    # Write text atomically
    atomic_write_text("/path/to/file.txt", "content here")
"""

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional

from common.base.logging_config import get_logger

# Module-level logger
logger = get_logger(__name__)


# Lock timeout in seconds (0 = non-blocking)
DEFAULT_LOCK_TIMEOUT = 30


class AtomicWriteError(Exception):
    """Raised when atomic write operation fails."""
    pass


class FileLockError(Exception):
    """Raised when file lock cannot be acquired."""
    pass


@contextmanager
def file_lock(file_path: str, timeout: int = DEFAULT_LOCK_TIMEOUT, shared: bool = False):
    """Context manager for acquiring a file lock.

    Creates a lock file adjacent to the target file to coordinate access.
    Uses fcntl.flock for Unix file locking.

    Args:
        file_path: Path to the file to lock
        timeout: Maximum time to wait for lock (seconds). 0 = non-blocking.
        shared: If True, acquire shared (read) lock. If False, exclusive (write) lock.

    Yields:
        The lock file handle (for use if needed)

    Raises:
        FileLockError: If the lock cannot be acquired within timeout
    """
    lock_path = file_path + ".lock"
    lock_dir = os.path.dirname(lock_path)

    # Ensure directory exists
    if lock_dir:
        os.makedirs(lock_dir, exist_ok=True)

    lock_file = None
    try:
        # Create/open lock file
        lock_file = open(lock_path, 'w')

        # Determine lock type
        lock_type = fcntl.LOCK_SH if shared else fcntl.LOCK_EX

        if timeout == 0:
            # Non-blocking
            fcntl.flock(lock_file.fileno(), lock_type | fcntl.LOCK_NB)
        else:
            # Blocking with timeout - we simulate timeout by trying non-blocking in a loop
            import time
            start_time = time.time()
            while True:
                try:
                    fcntl.flock(lock_file.fileno(), lock_type | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.time() - start_time >= timeout:
                        raise FileLockError(
                            f"Could not acquire lock on {file_path} within {timeout} seconds"
                        )
                    time.sleep(0.1)

        yield lock_file

    except BlockingIOError:
        raise FileLockError(f"Could not acquire lock on {file_path} (file is locked by another process)")
    finally:
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except Exception:
                pass


def atomic_write_text(
    file_path: str,
    content: str,
    encoding: str = 'utf-8',
    backup: bool = True,
    use_lock: bool = True,
    lock_timeout: int = DEFAULT_LOCK_TIMEOUT
) -> bool:
    """Atomically write text content to a file.

    This function:
    1. Acquires an exclusive lock on the file
    2. Writes content to a temporary file in the same directory
    3. Calls fsync to ensure data is on disk
    4. If backup=True and file exists, renames existing file to .bak
    5. Atomically renames temp file to target path
    6. Releases the lock

    Args:
        file_path: Absolute path to the file to write
        content: The text content to write
        encoding: Text encoding (default: utf-8)
        backup: If True, keep the previous version as .bak (default: True)
        use_lock: If True, use file locking (default: True)
        lock_timeout: Seconds to wait for lock (default: 30)

    Returns:
        True on success, False on failure

    Raises:
        AtomicWriteError: On write failure (only if backup restoration fails)
    """
    file_dir = os.path.dirname(file_path) or '.'
    backup_path = file_path + ".bak"
    temp_fd = None
    temp_path = None

    def do_write():
        nonlocal temp_fd, temp_path

        # Create temp file in same directory (ensures same filesystem for atomic rename)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_dir,
            prefix='.tmp_',
            suffix=os.path.basename(file_path)
        )

        try:
            # Write content to temp file
            with os.fdopen(temp_fd, 'w', encoding=encoding) as f:
                temp_fd = None  # os.fdopen takes ownership
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            # Create backup of existing file if it exists
            if backup and os.path.exists(file_path):
                try:
                    # Remove old backup if exists
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    # Rename current to backup
                    os.rename(file_path, backup_path)
                except Exception as e:
                    logger.warning(f"Failed to create backup for {file_path}: {e}")
                    # Continue anyway - backup is optional

            # Atomic rename temp to target
            os.rename(temp_path, file_path)
            temp_path = None  # Successful rename

            return True

        except Exception as e:
            logger.error(f"Error during atomic write to {file_path}: {e}")

            # Clean up temp file if it still exists
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

            # Try to restore from backup if we moved the original
            if backup and not os.path.exists(file_path) and os.path.exists(backup_path):
                try:
                    os.rename(backup_path, file_path)
                    logger.info(f"Restored {file_path} from backup after failed write")
                except Exception as restore_error:
                    logger.error(f"CRITICAL: Failed to restore {file_path} from backup: {restore_error}")
                    raise AtomicWriteError(
                        f"Write failed and could not restore from backup: {e}"
                    ) from e

            return False

        finally:
            # Ensure temp file descriptor is closed if fdopen wasn't called
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except Exception:
                    pass

    # Ensure directory exists
    os.makedirs(file_dir, exist_ok=True)

    if use_lock:
        try:
            with file_lock(file_path, timeout=lock_timeout):
                return do_write()
        except FileLockError as e:
            logger.error(f"Could not acquire lock for {file_path}: {e}")
            return False
    else:
        return do_write()


def atomic_write_json(
    file_path: str,
    data: Dict[str, Any],
    encoding: str = 'utf-8',
    backup: bool = True,
    use_lock: bool = True,
    lock_timeout: int = DEFAULT_LOCK_TIMEOUT,
    formatter: Optional[Callable[[Dict[str, Any]], str]] = None,
    indent: Optional[int] = None,
    ensure_ascii: bool = False
) -> bool:
    """Atomically write JSON data to a file.

    Args:
        file_path: Absolute path to the file to write
        data: Dictionary to serialize as JSON
        encoding: Text encoding (default: utf-8)
        backup: If True, keep the previous version as .bak (default: True)
        use_lock: If True, use file locking (default: True)
        lock_timeout: Seconds to wait for lock (default: 30)
        formatter: Optional custom formatter function that takes data and returns string.
                  If provided, this is used instead of json.dumps.
        indent: JSON indentation level (default: None for compact)
        ensure_ascii: If True, escape non-ASCII characters (default: False)

    Returns:
        True on success, False on failure
    """
    try:
        if formatter:
            content = formatter(data)
        else:
            content = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize JSON for {file_path}: {e}")
        return False

    return atomic_write_text(
        file_path=file_path,
        content=content,
        encoding=encoding,
        backup=backup,
        use_lock=use_lock,
        lock_timeout=lock_timeout
    )


def read_with_lock(
    file_path: str,
    encoding: str = 'utf-8',
    lock_timeout: int = DEFAULT_LOCK_TIMEOUT
) -> Optional[str]:
    """Read a file with a shared lock.

    This ensures the file isn't being written to while reading.

    Args:
        file_path: Path to the file to read
        encoding: Text encoding (default: utf-8)
        lock_timeout: Seconds to wait for lock (default: 30)

    Returns:
        File contents as string, or None if file doesn't exist or error occurs
    """
    if not os.path.exists(file_path):
        return None

    try:
        with file_lock(file_path, timeout=lock_timeout, shared=True):
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
    except FileLockError as e:
        logger.error(f"Could not acquire read lock for {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None


def read_json_with_lock(
    file_path: str,
    encoding: str = 'utf-8',
    lock_timeout: int = DEFAULT_LOCK_TIMEOUT
) -> Optional[Dict[str, Any]]:
    """Read and parse a JSON file with a shared lock.

    Args:
        file_path: Path to the JSON file to read
        encoding: Text encoding (default: utf-8)
        lock_timeout: Seconds to wait for lock (default: 30)

    Returns:
        Parsed JSON as dictionary, or None if file doesn't exist or error occurs
    """
    content = read_with_lock(file_path, encoding, lock_timeout)
    if content is None:
        return None

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        return None


def recover_from_backup(file_path: str) -> bool:
    """Attempt to recover a corrupted file from its backup.

    Args:
        file_path: Path to the corrupted file

    Returns:
        True if recovery was successful, False otherwise
    """
    backup_path = file_path + ".bak"

    if not os.path.exists(backup_path):
        logger.warning(f"No backup file found at {backup_path}")
        return False

    try:
        # Validate backup is valid JSON (for JSON files)
        if file_path.endswith('.json'):
            with open(backup_path, 'r', encoding='utf-8') as f:
                json.load(f)  # Will raise if invalid

        # Move corrupted file aside
        corrupted_path = file_path + ".corrupted"
        if os.path.exists(file_path):
            os.rename(file_path, corrupted_path)

        # Restore from backup
        os.rename(backup_path, file_path)

        logger.info(f"Successfully recovered {file_path} from backup. Corrupted version saved as {corrupted_path}")
        return True

    except json.JSONDecodeError as e:
        logger.error(f"Backup file {backup_path} is also corrupted: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to recover {file_path} from backup: {e}")
        return False
