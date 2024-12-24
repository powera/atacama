"""
Chinese text annotation system using CC-CEDICT dictionary with pypinyin fallback.

This module provides functionality for annotating Chinese text with pinyin and English
definitions. It primarily uses CC-CEDICT dictionary data, falling back to pypinyin
for characters not found in the dictionary. The system supports both traditional
and simplified Chinese characters.

The module maintains both in-memory and disk caches for performance, with options
for remote caching in future implementations.
"""

from dataclasses import dataclass
from functools import lru_cache
import logging
import re
from typing import Dict, List, Optional, Tuple

import jieba  # For word segmentation
from pypinyin import pinyin, Style

logger = logging.getLogger(__name__)

@dataclass
class ChineseAnnotation:
    """Represents annotation data for a Chinese character or word."""
    hanzi: str
    pinyin: str
    definition: str

class PinyinProcessor:
    """Handles pinyin and definition lookups for Chinese text."""
    
    def __init__(self, use_remote_cache: bool = False):
        """
        Initialize the pinyin processor.
        
        Args:
            use_remote_cache: Whether to use remote database caching (not implemented)
        """
        self.use_remote_cache = use_remote_cache
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        
        # Dictionary to store both traditional and simplified forms
        # Format: {character: (pinyin, definition)}
        self.cedict: Dict[str, Tuple[str, str]] = {}
        self._local_cache: Dict[str, ChineseAnnotation] = {}
        
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
    
    def _get_pinyin_for_text(self, text: str) -> str:
        """
        Generate pinyin for Chinese text using pypinyin as fallback.
        
        Args:
            text: Chinese text to convert
        Returns:
            Pinyin with tone numbers
        """
        # Try CEDICT first
        if text in self.cedict:
            return self.cedict[text][0]
            
        # Fall back to pypinyin
        pin = pinyin(text, style=Style.TONE3)
        return ' '.join([p[0] for p in pin])
    
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
