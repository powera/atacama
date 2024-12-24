from typing import Dict, Optional, List, Tuple
import re
from functools import lru_cache
import logging
from dataclasses import dataclass
from pypinyin import pinyin, Style
import jieba  # For word segmentation

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
        
        :param use_remote_cache: Whether to use remote database caching (not implemented)
        """
        self.use_remote_cache = use_remote_cache
        # Pattern to match Chinese characters
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        
        # Local cache configuration
        self._local_cache: Dict[str, ChineseAnnotation] = {}
        
        # Load CEDICT data if available
        self.cedict = {}
        try:
            self._load_cedict()
        except Exception as e:
            logger.warning(f"Could not load CEDICT: {e}")

    def _load_cedict(self) -> None:
        """
        Load CC-CEDICT dictionary data.
        Assumes CEDICT file is in data/cedict.txt
        """
        try:
            # TODO: is the filename meaningful?
            with open('data/cedict/cedict_1_0_ts_utf-8_mdbg.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('#'):
                        continue
                    parts = line.strip().split('/')
                    if len(parts) < 2:
                        continue
                    hanzi = parts[0].split('[')[0].strip()
                    definition = '/'.join(parts[1:-1])
                    self.cedict[hanzi] = definition
        except FileNotFoundError:
            logger.warning("CEDICT file not found. Only pinyin will be available.")
    
    def _get_pinyin_for_text(self, text: str) -> str:
        """
        Generate pinyin for Chinese text.
        
        :param text: Chinese text to convert
        :return: Pinyin with tone numbers
        """
        # Get pinyin with tone numbers
        pin = pinyin(text, style=Style.TONE3)
        # Flatten the list and join with spaces
        return ' '.join([p[0] for p in pin])
    
    def _get_definition(self, text: str) -> str:
        """
        Get English definition for Chinese text.
        
        :param text: Chinese text to look up
        :return: Definition if found, otherwise empty string
        """
        # First try direct lookup
        if text in self.cedict:
            return self.cedict[text]
            
        # If not found and text is longer than one character,
        # try breaking it into words and looking up each
        if len(text) > 1:
            words = jieba.cut(text)
            definitions = []
            for word in words:
                if word in self.cedict:
                    definitions.append(self.cedict[word])
            if definitions:
                return '; '.join(definitions)
                
        return ""
            
    @lru_cache(maxsize=1000)
    def get_annotation(self, hanzi: str) -> Optional[ChineseAnnotation]:
        """
        Get annotation for Chinese characters.
        
        :param hanzi: Chinese characters to look up
        :return: ChineseAnnotation if found, None otherwise
        """
        # First check local cache
        if hanzi in self._local_cache:
            return self._local_cache[hanzi]
            
        # TODO: Implement remote cache lookup when use_remote_cache is True
        if self.use_remote_cache:
            logger.info("Remote cache lookup not yet implemented")
            
        # Generate pinyin
        pinyin_text = self._get_pinyin_for_text(hanzi)
        
        # Get definition
        definition = self._get_definition(hanzi)
        if not definition:
            # If no definition found, at least return pinyin
            definition = f"[No definition available]"
            
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
        
        :param text: Text to process
        :return: List of Chinese character sequences
        """
        return self.chinese_pattern.findall(text)
    
    def annotate_text(self, text: str) -> Dict[str, Dict[str, str]]:
        """
        Process text and return annotations in format expected by ColorScheme.
        
        :param text: Text containing Chinese characters
        :return: Dictionary mapping hanzi to annotation data
        """
        annotations = {}
        
        # Extract all Chinese sequences
        chinese_sequences = self.extract_chinese(text)
        
        # Get annotations for each sequence
        for hanzi in chinese_sequences:
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
        
        :param annotation: Annotation to cache
        """
        self._local_cache[annotation.hanzi] = annotation
        
    def clear_cache(self) -> None:
        """Clear the local cache."""
        self._local_cache.clear()
        # Also clear the lru_cache for get_annotation
        self.get_annotation.cache_clear()

# Global instance for convenience
default_processor = PinyinProcessor()

def annotate_chinese(text: str) -> Dict[str, Dict[str, str]]:
    """
    Convenience function using default processor.
    
    :param text: Text to annotate
    :return: Annotation dictionary
    """
    return default_processor.annotate_text(text)
