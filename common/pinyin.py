"""
Enhanced Chinese text annotation system with advanced pinyin processing.

This module provides sophisticated Chinese text annotation with features designed
for non-native speakers:
- Capitalized pinyin with proper diacritical marks
- Tone sandhi rules for common patterns
- Multi-word segmentation with separate annotations
- CEDICT-based definitions with pypinyin fallback

The system maintains both in-memory and disk caches for performance.
"""

from dataclasses import dataclass
import logging
import re
from typing import Dict, List, Optional, Tuple, Set
from functools import lru_cache

import jieba
from pypinyin import pinyin, Style

logger = logging.getLogger(__name__)

@dataclass
class ChineseAnnotation:
    """Represents annotation data for a Chinese character or word."""
    hanzi: str
    pinyin: str  # In uppercase with diacritics
    definition: str

class PinyinFormatter:
    """Handles conversion of numbered pinyin to diacritic format."""
    
    # Mapping for vowel + tone number to vowel with diacritic
    TONE_MARKS = {
        'a': 'āáǎà', 'e': 'ēéěè', 'i': 'īíǐì',
        'o': 'ōóǒò', 'u': 'ūúǔù', 'ü': 'ǖǘǚǜ',
        'A': 'ĀÁǍÀ', 'E': 'ĒÉĚÈ', 'I': 'ĪÍǏÌ',
        'O': 'ŌÓǑÒ', 'U': 'ŪÚǓÙ', 'Ü': 'ǕǗǙǛ'
    }
    
    @staticmethod
    def _capitalize(syllable: str) -> str:
        """Capitalize pinyin syllable."""
        return syllable.upper() if syllable else ''

    @staticmethod
    def _get_first_vowel_index(syllable: str) -> Optional[int]:
        """Find the first vowel in a syllable."""
        vowels = 'aeiouüvAEIOUÜV'
        for i, char in enumerate(syllable):
            if char in vowels:
                return i
        return None

    @classmethod
    def apply_diacritic(cls, syllable: str, tone: int) -> str:
        """Convert numbered pinyin to diacritic format."""
        if not syllable or tone not in range(1, 5):
            return syllable

        syllable = syllable.replace('v', 'ü').replace('V', 'Ü')
        vowel_index = cls._get_first_vowel_index(syllable)
        if vowel_index is None:
            return syllable

        vowel = syllable[vowel_index]
        if vowel.lower() in cls.TONE_MARKS:
            new_vowel = cls.TONE_MARKS[vowel][tone - 1]
            return syllable[:vowel_index] + new_vowel + syllable[vowel_index + 1:]
        return syllable

class ToneSandhi:
    """Implements tone sandhi rules for Mandarin."""
    
    @staticmethod
    def apply_third_tone_sandhi(syllables: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
        """Apply tone sandhi rules for third tones."""
        result = []
        i = 0
        while i < len(syllables):
            if i + 1 < len(syllables) and syllables[i][1] == 3 and syllables[i + 1][1] == 3:
                # Change first third tone to second tone
                result.append((syllables[i][0], 2))
                result.append(syllables[i + 1])
                i += 2
            else:
                result.append(syllables[i])
                i += 1
        return result

    @staticmethod
    def apply_yi_bu_rules(word: str, syllables: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
        """Apply special rules for 一 and 不."""
        result = []
        for i, (syl, tone) in enumerate(syllables):
            if word[i] == '一':
                # 一 in isolation: first tone
                # Before fourth tone: second tone
                # Before any other tone: fourth tone
                if i + 1 < len(syllables):
                    next_tone = syllables[i + 1][1]
                    new_tone = 2 if next_tone == 4 else 4
                    result.append((syl, new_tone))
                else:
                    result.append((syl, 1))
            elif word[i] == '不' and i + 1 < len(syllables):
                # 不 before fourth tone becomes second tone
                next_tone = syllables[i + 1][1]
                new_tone = 2 if next_tone == 4 else tone
                result.append((syl, new_tone))
            else:
                result.append((syl, tone))
        return result

class PinyinProcessor:
    """Handles pinyin and definition lookups for Chinese text."""
    
    def __init__(self, use_remote_cache: bool = False):
        """Initialize the pinyin processor."""
        self.use_remote_cache = use_remote_cache
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        self.cedict: Dict[str, Tuple[str, str]] = {}
        self._local_cache: Dict[str, ChineseAnnotation] = {}
        self.formatter = PinyinFormatter()
        self.tone_sandhi = ToneSandhi()
        
        try:
            self._load_cedict()
        except Exception as e:
            logger.warning(f"Could not load CEDICT: {e}")

    def _load_cedict(self) -> None:
        """
        Load CC-CEDICT dictionary data.
        Format: traditional simplified [pinyin] /definition/
        Example: 下腳 下脚 [xia4 jiao3] /to get a footing/
        """
        try:
            with open('data/cedict/cedict_1_0_ts_utf-8_mdbg.txt', 'r', encoding='utf-8') as f:
                pattern = re.compile(r'^(\S+)\s+(\S+)\s+\[(.*?)\]\s+/(.*?)/')
                
                for line in f:
                    if line.startswith('#'):
                        continue
                        
                    match = pattern.match(line.strip())
                    if not match:
                        continue
                        
                    traditional, simplified, pin, definitions = match.groups()
                    # Clean up definitions and convert to readable format
                    clean_defs = definitions.strip('/').split('/')
                    primary_def = clean_defs[0] if clean_defs else ""
                    
                    # Store both traditional and simplified forms
                    self.cedict[traditional] = (pin, primary_def)
                    self.cedict[simplified] = (pin, primary_def)
                    
        except FileNotFoundError:
            logger.warning("CEDICT file not found. Falling back to pypinyin only.")
    

    def _extract_numbered_syllables(self, pinyin_text: str) -> List[Tuple[str, int]]:
        """Extract syllables and their tone numbers from numbered pinyin."""
        pattern = re.compile(r'([a-zA-Z]+)([1-5])')
        return [(match.group(1), int(match.group(2))) 
                for match in pattern.finditer(pinyin_text)]

    def _format_pinyin(self, word: str, pinyin_text: str) -> str:
        """Format pinyin with proper capitalization and tone marks."""
        syllables = self._extract_numbered_syllables(pinyin_text)
        
        # Apply tone sandhi rules
        syllables = self.tone_sandhi.apply_third_tone_sandhi(syllables)
        syllables = self.tone_sandhi.apply_yi_bu_rules(word, syllables)
        
        # Convert to diacritic format and capitalize
        formatted = []
        for syl, tone in syllables:
            syl = self.formatter._capitalize(syl)
            syl = self.formatter.apply_diacritic(syl, tone)
            formatted.append(syl)
            
        return ' '.join(formatted)

    def _segment_words(self, text: str) -> List[str]:
        """Segment Chinese text into words using jieba."""
        return list(jieba.cut(text))

    def annotate_text(self, text: str) -> Dict[str, Dict[str, str]]:
        """
        Process text and return word-level annotations.
        
        Returns dictionary mapping each word to its annotation data.
        Words are determined by jieba segmentation.
        """
        annotations = {}
        words = self._segment_words(text)
        
        for word in words:
            if not self.chinese_pattern.match(word):
                continue
                
            annotation = self.get_annotation(word)
            if annotation:
                annotations[word] = {
                    "pinyin": annotation.pinyin,
                    "definition": annotation.definition
                }
            
        return annotations

    def _get_pinyin_for_text(self, text: str) -> str:
        """Generate properly formatted pinyin for Chinese text."""
        if text in self.cedict:
            raw_pinyin = self.cedict[text][0]
        else:
            # Fall back to pypinyin
            pin = pinyin(text, style=Style.TONE3)
            raw_pinyin = ' '.join([p[0] for p in pin])
        
        return self._format_pinyin(text, raw_pinyin)

    def _get_definition(self, text: str) -> str:
        """
        Get English definition for Chinese text.
        
        Args:
            text: Chinese text to look up
        Returns:
            Definition if found, otherwise empty string
        """
        # Direct dictionary lookup
        if text in self.cedict:
            return self.cedict[text][1]
            
        # For multi-character text not in dictionary, try word segmentation
        if len(text) > 1:
            words = jieba.cut(text)
            definitions = []
            for word in words:
                if word in self.cedict:
                    definitions.append(f"{word}: {self.cedict[word][1]}")
            if definitions:
                return '; '.join(definitions)
                
        return ""
            
    @lru_cache(maxsize=1000)
    def get_annotation(self, hanzi: str) -> Optional[ChineseAnnotation]:
        """
        Get annotation for Chinese characters.
        
        Args:
            hanzi: Chinese characters to look up
        Returns:
            ChineseAnnotation if found, None otherwise
        """
        # Check local cache first
        if hanzi in self._local_cache:
            return self._local_cache[hanzi]
            
        # Get pinyin (either from CEDICT or pypinyin fallback)
        pinyin_text = self._get_pinyin_for_text(hanzi)
        
        # Get definition
        definition = self._get_definition(hanzi)
        if not definition:
            definition = "[No definition available]"
            
        annotation = ChineseAnnotation(
            hanzi=hanzi,
            pinyin=pinyin_text,
            definition=definition
        )
        
        # Cache the result
        self._local_cache[hanzi] = annotation
        return annotation
    
    def extract_chinese(self, text: str) -> List[str]:
        """
        Extract all Chinese character sequences from text.
        
        Args:
            text: Text to process
        Returns:
            List of Chinese character sequences
        """
        return self.chinese_pattern.findall(text)
    
    def annotate_text(self, text: str) -> Dict[str, Dict[str, str]]:
        """
        Process text and return annotations in format expected by ColorScheme.
        
        Args:
            text: Text containing Chinese characters
        Returns:
            Dictionary mapping hanzi to annotation data
        """
        annotations = {}
        
        for hanzi in self.extract_chinese(text):
            annotation = self.get_annotation(hanzi)
            if annotation:
                annotations[hanzi] = {
                    "pinyin": annotation.pinyin,
                    "definition": annotation.definition
                }
            else:
                logger.warning(f"No annotation found for: {hanzi}")
                
        return annotations
    
    def add_to_cache(self, annotation: ChineseAnnotation) -> None:
        """
        Add an annotation to the local cache.
        
        Args:
            annotation: Annotation to cache
        """
        self._local_cache[annotation.hanzi] = annotation
        
    def clear_cache(self) -> None:
        """Clear the local cache and LRU cache."""
        self._local_cache.clear()
        self.get_annotation.cache_clear()

# Global instance for convenience
default_processor = PinyinProcessor()

def annotate_chinese(text: str) -> Dict[str, Dict[str, str]]:
    """
    Convenience function using default processor.
    
    Args:
            text: Text to annotate
    Returns:
            Annotation dictionary
    """
    return default_processor.annotate_text(text)
