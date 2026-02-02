"""Tests for the pinyin module Chinese text annotation."""

import unittest
from unittest.mock import patch, MagicMock

# Pinyin module requires jieba and pypinyin dependencies
try:
    from aml_parser.pinyin import (
        ChineseAnnotation,
        PinyinFormatter,
        ToneSandhi,
        PinyinProcessor,
        annotate_chinese,
    )
    PINYIN_AVAILABLE = True
except ImportError:
    # Dependencies (jieba, pypinyin) not installed - skip tests
    PINYIN_AVAILABLE = False
    ChineseAnnotation = None
    PinyinFormatter = None
    ToneSandhi = None
    PinyinProcessor = None
    annotate_chinese = None


@unittest.skipUnless(PINYIN_AVAILABLE, "Pinyin module dependencies not available")
class TestChineseAnnotation(unittest.TestCase):
    """Test suite for ChineseAnnotation dataclass."""

    def test_create_annotation(self):
        """ChineseAnnotation should store hanzi, pinyin, and definition."""
        annotation = ChineseAnnotation(
            hanzi="你好",
            pinyin="NǏ HǍO",
            definition="hello"
        )
        self.assertEqual(annotation.hanzi, "你好")
        self.assertEqual(annotation.pinyin, "NǏ HǍO")
        self.assertEqual(annotation.definition, "hello")

    def test_annotation_equality(self):
        """Two annotations with same values should be equal."""
        ann1 = ChineseAnnotation(hanzi="好", pinyin="HǍO", definition="good")
        ann2 = ChineseAnnotation(hanzi="好", pinyin="HǍO", definition="good")
        self.assertEqual(ann1, ann2)


@unittest.skipUnless(PINYIN_AVAILABLE, "Pinyin module dependencies not available")
class TestPinyinFormatter(unittest.TestCase):
    """Test suite for PinyinFormatter class."""

    def test_capitalize_empty_string(self):
        """_capitalize should handle empty string."""
        result = PinyinFormatter._capitalize("")
        self.assertEqual(result, "")

    def test_capitalize_lowercase(self):
        """_capitalize should uppercase lowercase string."""
        result = PinyinFormatter._capitalize("hello")
        self.assertEqual(result, "HELLO")

    def test_get_first_vowel_index_a(self):
        """_get_first_vowel_index should find 'a' vowel."""
        result = PinyinFormatter._get_first_vowel_index("han")
        self.assertEqual(result, 1)

    def test_get_first_vowel_index_no_vowel(self):
        """_get_first_vowel_index should return None when no vowel."""
        result = PinyinFormatter._get_first_vowel_index("xyz")
        self.assertIsNone(result)

    def test_get_first_vowel_index_at_start(self):
        """_get_first_vowel_index should find vowel at start."""
        result = PinyinFormatter._get_first_vowel_index("ai")
        self.assertEqual(result, 0)

    def test_apply_diacritic_tone_1(self):
        """apply_diacritic should add tone 1 diacritic."""
        result = PinyinFormatter.apply_diacritic("ma", 1)
        self.assertEqual(result, "mā")

    def test_apply_diacritic_tone_2(self):
        """apply_diacritic should add tone 2 diacritic."""
        result = PinyinFormatter.apply_diacritic("ma", 2)
        self.assertEqual(result, "má")

    def test_apply_diacritic_tone_3(self):
        """apply_diacritic should add tone 3 diacritic."""
        result = PinyinFormatter.apply_diacritic("ma", 3)
        self.assertEqual(result, "mǎ")

    def test_apply_diacritic_tone_4(self):
        """apply_diacritic should add tone 4 diacritic."""
        result = PinyinFormatter.apply_diacritic("ma", 4)
        self.assertEqual(result, "mà")

    def test_apply_diacritic_empty_string(self):
        """apply_diacritic should handle empty string."""
        result = PinyinFormatter.apply_diacritic("", 1)
        self.assertEqual(result, "")

    def test_apply_diacritic_invalid_tone(self):
        """apply_diacritic should not modify for invalid tone."""
        result = PinyinFormatter.apply_diacritic("ma", 0)
        self.assertEqual(result, "ma")
        result = PinyinFormatter.apply_diacritic("ma", 5)
        self.assertEqual(result, "ma")

    def test_apply_diacritic_v_to_u_umlaut(self):
        """apply_diacritic should convert v to ü."""
        result = PinyinFormatter.apply_diacritic("nv", 3)
        self.assertEqual(result, "nǚ")

    def test_apply_diacritic_uppercase(self):
        """apply_diacritic should work with uppercase vowels."""
        result = PinyinFormatter.apply_diacritic("MA", 1)
        self.assertEqual(result, "MĀ")

    def test_apply_diacritic_no_vowel(self):
        """apply_diacritic should return unchanged if no vowel."""
        result = PinyinFormatter.apply_diacritic("ng", 1)
        self.assertEqual(result, "ng")


@unittest.skipUnless(PINYIN_AVAILABLE, "Pinyin module dependencies not available")
class TestToneSandhi(unittest.TestCase):
    """Test suite for ToneSandhi class."""

    def test_third_tone_sandhi_two_third_tones(self):
        """Two consecutive third tones should change first to second."""
        syllables = [("ni", 3), ("hao", 3)]
        result = ToneSandhi.apply_third_tone_sandhi(syllables)
        self.assertEqual(result, [("ni", 2), ("hao", 3)])

    def test_third_tone_sandhi_no_consecutive(self):
        """Non-consecutive third tones should not change."""
        syllables = [("ni", 3), ("de", 5), ("hao", 3)]
        result = ToneSandhi.apply_third_tone_sandhi(syllables)
        self.assertEqual(result, [("ni", 3), ("de", 5), ("hao", 3)])

    def test_third_tone_sandhi_first_tone(self):
        """First tones should not change."""
        syllables = [("ma", 1), ("ma", 1)]
        result = ToneSandhi.apply_third_tone_sandhi(syllables)
        self.assertEqual(result, [("ma", 1), ("ma", 1)])

    def test_third_tone_sandhi_empty(self):
        """Empty list should return empty."""
        result = ToneSandhi.apply_third_tone_sandhi([])
        self.assertEqual(result, [])

    def test_third_tone_sandhi_single(self):
        """Single syllable should not change."""
        result = ToneSandhi.apply_third_tone_sandhi([("ni", 3)])
        self.assertEqual(result, [("ni", 3)])

    def test_yi_before_fourth_tone(self):
        """一 before fourth tone should become second tone."""
        word = "一定"
        syllables = [("yi", 1), ("ding", 4)]
        result = ToneSandhi.apply_yi_bu_rules(word, syllables)
        self.assertEqual(result, [("yi", 2), ("ding", 4)])

    def test_yi_before_other_tone(self):
        """一 before non-fourth tone should become fourth tone."""
        word = "一般"
        syllables = [("yi", 1), ("ban", 1)]
        result = ToneSandhi.apply_yi_bu_rules(word, syllables)
        self.assertEqual(result, [("yi", 4), ("ban", 1)])

    def test_yi_isolated(self):
        """一 in isolation should be first tone."""
        word = "一"
        syllables = [("yi", 1)]
        result = ToneSandhi.apply_yi_bu_rules(word, syllables)
        self.assertEqual(result, [("yi", 1)])

    def test_bu_before_fourth_tone(self):
        """不 before fourth tone should become second tone."""
        word = "不是"
        syllables = [("bu", 4), ("shi", 4)]
        result = ToneSandhi.apply_yi_bu_rules(word, syllables)
        self.assertEqual(result, [("bu", 2), ("shi", 4)])

    def test_bu_before_other_tone(self):
        """不 before non-fourth tone should stay fourth tone."""
        word = "不好"
        syllables = [("bu", 4), ("hao", 3)]
        result = ToneSandhi.apply_yi_bu_rules(word, syllables)
        self.assertEqual(result, [("bu", 4), ("hao", 3)])

    def test_regular_word_no_change(self):
        """Regular word without 一 or 不 should not change."""
        word = "你好"
        syllables = [("ni", 3), ("hao", 3)]
        result = ToneSandhi.apply_yi_bu_rules(word, syllables)
        self.assertEqual(result, [("ni", 3), ("hao", 3)])


@unittest.skipUnless(PINYIN_AVAILABLE, "Pinyin module dependencies not available")
class TestPinyinProcessor(unittest.TestCase):
    """Test suite for PinyinProcessor class."""

    def setUp(self):
        """Set up test processor with mocked CEDICT loading."""
        with patch.object(PinyinProcessor, '_load_cedict'):
            self.processor = PinyinProcessor()
            self.processor.cedict = {
                "你好": ("ni3 hao3", "hello"),
                "好": ("hao3", "good"),
                "世界": ("shi4 jie4", "world"),
            }

    def test_extract_chinese_single(self):
        """extract_chinese should find single Chinese sequence."""
        result = self.processor.extract_chinese("Hello 你好 World")
        self.assertEqual(result, ["你好"])

    def test_extract_chinese_multiple(self):
        """extract_chinese should find multiple Chinese sequences."""
        result = self.processor.extract_chinese("Hello 你好 World 世界")
        self.assertEqual(result, ["你好", "世界"])

    def test_extract_chinese_none(self):
        """extract_chinese should return empty list when no Chinese."""
        result = self.processor.extract_chinese("Hello World")
        self.assertEqual(result, [])

    def test_extract_numbered_syllables(self):
        """_extract_numbered_syllables should parse numbered pinyin."""
        result = self.processor._extract_numbered_syllables("ni3 hao3")
        self.assertEqual(result, [("ni", 3), ("hao", 3)])

    def test_extract_numbered_syllables_mixed_case(self):
        """_extract_numbered_syllables should handle mixed case."""
        result = self.processor._extract_numbered_syllables("NI3 HAO3")
        self.assertEqual(result, [("NI", 3), ("HAO", 3)])

    def test_get_definition_found(self):
        """_get_definition should return definition from CEDICT."""
        result = self.processor._get_definition("好")
        self.assertEqual(result, "good")

    def test_get_definition_not_found(self):
        """_get_definition should return empty string when not found."""
        result = self.processor._get_definition("xyz")
        self.assertEqual(result, "")

    def test_get_annotation(self):
        """get_annotation should return ChineseAnnotation."""
        result = self.processor.get_annotation("好")
        self.assertIsInstance(result, ChineseAnnotation)
        self.assertEqual(result.hanzi, "好")
        self.assertEqual(result.definition, "good")

    def test_get_annotation_caching(self):
        """get_annotation should cache results."""
        # First call
        result1 = self.processor.get_annotation("好")
        # Second call should return cached
        result2 = self.processor.get_annotation("好")
        self.assertEqual(result1, result2)

    def test_annotate_text(self):
        """annotate_text should return dict of annotations."""
        result = self.processor.annotate_text("Hello 你好 World")
        self.assertIn("你好", result)
        self.assertIn("pinyin", result["你好"])
        self.assertIn("definition", result["你好"])

    def test_add_to_cache(self):
        """add_to_cache should add annotation to local cache."""
        annotation = ChineseAnnotation(hanzi="测试", pinyin="CÈ SHÌ", definition="test")
        self.processor.add_to_cache(annotation)
        self.assertIn("测试", self.processor._local_cache)

    def test_clear_cache(self):
        """clear_cache should clear both caches."""
        self.processor._local_cache["test"] = "value"
        self.processor.clear_cache()
        self.assertEqual(len(self.processor._local_cache), 0)

    @patch.object(PinyinProcessor, '_segment_words')
    def test_annotate_text_by_words(self, mock_segment):
        """annotate_text_by_words should use jieba segmentation."""
        mock_segment.return_value = ["你好", "世界"]
        result = self.processor.annotate_text_by_words("你好世界")
        self.assertIn("你好", result)
        self.assertIn("世界", result)


@unittest.skipUnless(PINYIN_AVAILABLE, "Pinyin module dependencies not available")
class TestAnnotateChinese(unittest.TestCase):
    """Test suite for annotate_chinese convenience function."""

    @patch('aml_parser.pinyin.default_processor')
    def test_uses_default_processor(self, mock_processor):
        """annotate_chinese should use the default processor."""
        mock_processor.annotate_text.return_value = {"好": {"pinyin": "HǍO", "definition": "good"}}
        result = annotate_chinese("好")
        mock_processor.annotate_text.assert_called_once_with("好")
        self.assertEqual(result, {"好": {"pinyin": "HǍO", "definition": "good"}})


if __name__ == '__main__':
    unittest.main()
