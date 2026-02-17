"""Tests for GUID -> word label loading in classroom stats."""

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import constants
from trakaido.blueprints import classroom_stats


class ClassroomStatsWordLabelTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = constants.DATA_DIR
        constants.DATA_DIR = self.temp_dir
        classroom_stats._load_guid_word_labels.cache_clear()

    def tearDown(self):
        classroom_stats._load_guid_word_labels.cache_clear()
        constants.DATA_DIR = self.original_data_dir
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_wireword(self, lang_code: str, filename: str, payload):
        out_dir = os.path.join(
            self.temp_dir,
            "trakaido_wordlists",
            f"lang_{lang_code}",
            "generated",
            "wireword",
        )
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as outfile:
            json.dump(payload, outfile)

    @patch("trakaido.blueprints.classroom_stats.get_language_manager")
    def test_loads_base_target_and_grammatical_forms(self, mock_get_language_manager):
        mock_get_language_manager.return_value.get_language_config.return_value = SimpleNamespace(
            code="lt"
        )
        self._write_wireword(
            "lt",
            "wireword_verbs.json",
            [
                {
                    "guid": "V08_004",
                    "base_target": "keisti",
                    "base_english": "change",
                    "grammatical_forms": {
                        "present_3rd": {"target": "keičia", "english": "changes"}
                    },
                }
            ],
        )

        labels = classroom_stats._load_guid_word_labels("lithuanian")

        self.assertEqual(labels["V08_004"], "keisti — change")
        self.assertEqual(labels["V08_004_present_3rd"], "keičia — changes")

    @patch("trakaido.blueprints.classroom_stats.get_language_manager")
    def test_loads_french_target_fields(self, mock_get_language_manager):
        mock_get_language_manager.return_value.get_language_config.return_value = SimpleNamespace(
            code="fr"
        )
        self._write_wireword(
            "fr",
            "wireword_core.json",
            [
                {
                    "guid": "F01_001",
                    "base_target": "bonjour",
                    "base_english": "hello",
                }
            ],
        )

        labels = classroom_stats._load_guid_word_labels("french")

        self.assertEqual(labels["F01_001"], "bonjour — hello")


if __name__ == "__main__":
    unittest.main()
