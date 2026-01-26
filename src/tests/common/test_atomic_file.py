"""Tests for the atomic file writing utilities."""

import json
import os
import tempfile
import threading
import time
import unittest

from common.atomic_file import (
    atomic_write_text,
    atomic_write_json,
    read_with_lock,
    read_json_with_lock,
    recover_from_backup,
    file_lock,
    FileLockError,
)


class TestAtomicWriteText(unittest.TestCase):
    """Test cases for atomic_write_text function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_new_file(self):
        """Test writing to a new file."""
        content = "Hello, World!"
        result = atomic_write_text(self.test_file, content)

        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.test_file))
        with open(self.test_file, 'r') as f:
            self.assertEqual(f.read(), content)

    def test_write_overwrites_existing(self):
        """Test that writing overwrites existing content."""
        # Write initial content
        atomic_write_text(self.test_file, "Initial content")

        # Write new content
        new_content = "New content"
        result = atomic_write_text(self.test_file, new_content)

        self.assertTrue(result)
        with open(self.test_file, 'r') as f:
            self.assertEqual(f.read(), new_content)

    def test_creates_backup(self):
        """Test that backup file is created."""
        # Write initial content
        atomic_write_text(self.test_file, "Initial content")

        # Write new content (should create backup)
        atomic_write_text(self.test_file, "New content")

        backup_path = self.test_file + ".bak"
        self.assertTrue(os.path.exists(backup_path))
        with open(backup_path, 'r') as f:
            self.assertEqual(f.read(), "Initial content")

    def test_no_backup_when_disabled(self):
        """Test that backup is not created when disabled."""
        atomic_write_text(self.test_file, "Initial content")
        atomic_write_text(self.test_file, "New content", backup=False)

        backup_path = self.test_file + ".bak"
        self.assertFalse(os.path.exists(backup_path))

    def test_creates_parent_directories(self):
        """Test that parent directories are created if they don't exist."""
        nested_file = os.path.join(self.temp_dir, "nested", "dir", "test.txt")
        result = atomic_write_text(nested_file, "content")

        self.assertTrue(result)
        self.assertTrue(os.path.exists(nested_file))

    def test_write_with_unicode(self):
        """Test writing Unicode content."""
        # Use actual Unicode characters (Chinese, Russian, emoji)
        content = "Hello, 世界! Жаргон 😀"
        result = atomic_write_text(self.test_file, content)

        self.assertTrue(result)
        with open(self.test_file, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read(), content)

    def test_write_without_lock(self):
        """Test writing without file locking."""
        result = atomic_write_text(self.test_file, "content", use_lock=False)

        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.test_file))


class TestAtomicWriteJson(unittest.TestCase):
    """Test cases for atomic_write_json function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.json")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_json(self):
        """Test writing JSON data."""
        data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        result = atomic_write_json(self.test_file, data)

        self.assertTrue(result)
        with open(self.test_file, 'r') as f:
            loaded = json.load(f)
        self.assertEqual(loaded, data)

    def test_write_json_with_indent(self):
        """Test writing JSON with indentation."""
        data = {"key": "value"}
        result = atomic_write_json(self.test_file, data, indent=2)

        self.assertTrue(result)
        with open(self.test_file, 'r') as f:
            content = f.read()
        # Indented JSON should have newlines
        self.assertIn("\n", content)

    def test_write_json_with_custom_formatter(self):
        """Test writing JSON with custom formatter."""
        def custom_formatter(data):
            return "CUSTOM: " + json.dumps(data)

        data = {"key": "value"}
        result = atomic_write_json(self.test_file, data, formatter=custom_formatter)

        self.assertTrue(result)
        with open(self.test_file, 'r') as f:
            content = f.read()
        self.assertTrue(content.startswith("CUSTOM: "))

    def test_write_json_with_unicode(self):
        """Test writing JSON with Unicode characters."""
        # Use actual Unicode characters (Chinese greeting and emoji)
        data = {"greeting": "你好", "emoji": "😀"}
        result = atomic_write_json(self.test_file, data)

        self.assertTrue(result)
        with open(self.test_file, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        self.assertEqual(loaded, data)


class TestReadWithLock(unittest.TestCase):
    """Test cases for read_with_lock function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_existing_file(self):
        """Test reading an existing file."""
        content = "Test content"
        with open(self.test_file, 'w') as f:
            f.write(content)

        result = read_with_lock(self.test_file)
        self.assertEqual(result, content)

    def test_read_nonexistent_file(self):
        """Test reading a nonexistent file."""
        result = read_with_lock(self.test_file)
        self.assertIsNone(result)


class TestReadJsonWithLock(unittest.TestCase):
    """Test cases for read_json_with_lock function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.json")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_valid_json(self):
        """Test reading valid JSON."""
        data = {"key": "value", "number": 42}
        with open(self.test_file, 'w') as f:
            json.dump(data, f)

        result = read_json_with_lock(self.test_file)
        self.assertEqual(result, data)

    def test_read_invalid_json(self):
        """Test reading invalid JSON returns None."""
        with open(self.test_file, 'w') as f:
            f.write("not valid json {{{")

        result = read_json_with_lock(self.test_file)
        self.assertIsNone(result)

    def test_read_nonexistent_file(self):
        """Test reading nonexistent file returns None."""
        result = read_json_with_lock(self.test_file)
        self.assertIsNone(result)


class TestRecoverFromBackup(unittest.TestCase):
    """Test cases for recover_from_backup function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.json")
        self.backup_file = self.test_file + ".bak"

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recover_from_valid_backup(self):
        """Test recovery from valid backup."""
        # Create corrupted main file
        with open(self.test_file, 'w') as f:
            f.write("corrupted {{{")

        # Create valid backup
        valid_data = {"stats": {}}
        with open(self.backup_file, 'w') as f:
            json.dump(valid_data, f)

        result = recover_from_backup(self.test_file)
        self.assertTrue(result)

        # Main file should now be the backup content
        with open(self.test_file, 'r') as f:
            recovered = json.load(f)
        self.assertEqual(recovered, valid_data)

        # Corrupted file should be saved
        corrupted_path = self.test_file + ".corrupted"
        self.assertTrue(os.path.exists(corrupted_path))

    def test_recover_no_backup_exists(self):
        """Test recovery when no backup exists."""
        with open(self.test_file, 'w') as f:
            f.write("corrupted")

        result = recover_from_backup(self.test_file)
        self.assertFalse(result)

    def test_recover_backup_also_corrupted(self):
        """Test recovery when backup is also corrupted."""
        # Create corrupted main file
        with open(self.test_file, 'w') as f:
            f.write("corrupted {{{")

        # Create corrupted backup
        with open(self.backup_file, 'w') as f:
            f.write("also corrupted {{{")

        result = recover_from_backup(self.test_file)
        self.assertFalse(result)


class TestFileLock(unittest.TestCase):
    """Test cases for file_lock context manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        # Create the file
        with open(self.test_file, 'w') as f:
            f.write("test")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_exclusive_lock(self):
        """Test acquiring exclusive lock."""
        with file_lock(self.test_file) as lock_file:
            self.assertIsNotNone(lock_file)

    def test_shared_lock(self):
        """Test acquiring shared lock."""
        with file_lock(self.test_file, shared=True) as lock_file:
            self.assertIsNotNone(lock_file)

    def test_lock_timeout_with_contention(self):
        """Test that lock times out when file is locked by another process."""
        lock_acquired = threading.Event()
        should_release = threading.Event()
        lock_released = threading.Event()

        def hold_lock():
            with file_lock(self.test_file, timeout=30):
                lock_acquired.set()
                should_release.wait(timeout=5)
            lock_released.set()

        # Start thread that holds the lock
        thread = threading.Thread(target=hold_lock)
        thread.start()

        try:
            # Wait for lock to be acquired
            lock_acquired.wait(timeout=2)

            # Try to acquire the same lock with very short timeout
            with self.assertRaises(FileLockError):
                with file_lock(self.test_file, timeout=0):
                    pass  # Should not reach here
        finally:
            # Signal thread to release and wait for cleanup
            should_release.set()
            lock_released.wait(timeout=2)
            thread.join(timeout=2)


class TestConcurrentAccess(unittest.TestCase):
    """Test concurrent access scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.json")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sequential_writes(self):
        """Test that sequential writes don't corrupt data."""
        for i in range(10):
            data = {"iteration": i, "data": "x" * 1000}
            result = atomic_write_json(self.test_file, data)
            self.assertTrue(result)

            # Verify content is valid after each write
            with open(self.test_file, 'r') as f:
                loaded = json.load(f)
            self.assertEqual(loaded["iteration"], i)

    def test_concurrent_writes_from_threads(self):
        """Test that concurrent writes from threads don't corrupt data."""
        results = []
        errors = []

        def write_data(thread_id):
            try:
                for i in range(5):
                    data = {"thread": thread_id, "iteration": i}
                    result = atomic_write_json(self.test_file, data)
                    results.append(result)
                    time.sleep(0.01)  # Small delay to increase contention
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_data, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should have occurred
        self.assertEqual(len(errors), 0)

        # All writes should have succeeded
        self.assertTrue(all(results))

        # Final file should be valid JSON
        with open(self.test_file, 'r') as f:
            data = json.load(f)
        self.assertIn("thread", data)
        self.assertIn("iteration", data)


if __name__ == '__main__':
    unittest.main()
