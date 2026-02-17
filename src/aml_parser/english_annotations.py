"""
English word annotation system using greenland-mint vocabulary data.

Provides annotation of English words with lemma, GUID, definition, POS, and
translations. Parallels the Chinese annotation system in pinyin.py.

Words are matched against the atacama_lookup.json exported from greenland-mint.
Words not found in the lookup but present in the stopwords section get a
lighter annotation indicating their POS category (pronoun, article, etc.).
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import constants
from common.base.logging_config import get_logger

logger = get_logger(__name__)


def _get_pinyin_for_chinese(text: str) -> Optional[str]:
    """Get formatted pinyin for Chinese text using the pinyin processor."""
    try:
        from aml_parser.pinyin import default_processor

        return default_processor._get_pinyin_for_text(text)
    except Exception:
        return None


WORD_PATTERN = re.compile(r"[a-zA-Z']+(?:-[a-zA-Z']+)*")

# Simple suffix-stripping rules for lemmatization fallback
_SUFFIX_RULES: List[tuple[str, str]] = [
    ("ies", "y"),
    ("ves", "f"),
    ("ses", "s"),
    ("zes", "z"),
    ("ches", "ch"),
    ("shes", "sh"),
    ("xes", "x"),
    ("ing", ""),
    ("ting", "t"),
    ("ning", "n"),
    ("ping", "p"),
    ("ding", "d"),
    ("ging", "g"),
    ("bing", "b"),
    ("ming", "m"),
    ("ring", "r"),
    ("ling", "l"),
    ("ning", "n"),
    ("ied", "y"),
    ("ed", ""),
    ("ted", "t"),
    ("ned", "n"),
    ("ped", "p"),
    ("ded", "d"),
    ("ged", "g"),
    ("bed", "b"),
    ("med", "m"),
    ("red", "r"),
    ("led", "l"),
    ("er", ""),
    ("est", ""),
    ("ly", ""),
    ("s", ""),
]


@dataclass
class EnglishAnnotation:
    """Annotation data for an English word."""

    word: str
    lemma: str
    guid: Optional[str]
    definition: Optional[str]
    pos_type: Optional[str]
    pos_subtype: Optional[str] = None
    translations: Dict[str, str] = field(default_factory=dict)
    derivative_form: Optional[str] = None
    is_stopword: bool = False


class EnglishAnnotationProcessor:
    """Looks up English words in the atacama lookup table."""

    def __init__(self, lookup_path: Optional[str] = None) -> None:
        self._lookup: Dict[str, dict] = {}
        self._stopwords: Dict[str, dict] = {}
        self._loaded = False

        if lookup_path is None:
            lookup_path = os.path.join(constants.DATA_DIR, "annotations", "atacama_lookup.json")
        self._lookup_path = lookup_path
        self._load()

    def _load(self) -> None:
        """Load the lookup JSON file."""
        if not os.path.exists(self._lookup_path):
            logger.warning("Atacama lookup file not found: %s", self._lookup_path)
            return

        try:
            with open(self._lookup_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._stopwords = data.pop("_stopwords", {})
            data.pop("_meta", None)
            self._lookup = data
            self._loaded = True
            logger.info(
                "Loaded atacama lookup: %d entries, %d stopwords",
                len(self._lookup),
                len(self._stopwords),
            )
        except Exception as e:
            logger.error("Failed to load atacama lookup: %s", e)

    def get_annotation(self, word: str) -> Optional[EnglishAnnotation]:
        """Look up annotation for a single English word.

        Tries exact match (lowercase), then simple suffix-stripping fallback.
        """
        if not self._loaded:
            return None

        key = word.lower()

        # Check stopwords first
        sw = self._stopwords.get(key)
        if sw:
            return EnglishAnnotation(
                word=word,
                lemma=sw["lemma"],
                guid=None,
                definition=None,
                pos_type=sw["pos"],
                is_stopword=True,
            )

        # Exact match in lookup
        entry = self._lookup.get(key)
        if entry:
            return self._entry_to_annotation(word, entry)

        # Suffix-stripping fallback
        for suffix, replacement in _SUFFIX_RULES:
            if key.endswith(suffix) and len(key) > len(suffix) + 1:
                candidate = key[: -len(suffix)] + replacement
                entry = self._lookup.get(candidate)
                if entry:
                    return self._entry_to_annotation(word, entry, fallback_form=suffix)

        return None

    def _entry_to_annotation(
        self, word: str, entry: dict, fallback_form: Optional[str] = None
    ) -> EnglishAnnotation:
        """Convert a lookup entry dict to an EnglishAnnotation."""
        return EnglishAnnotation(
            word=word,
            lemma=entry.get("lemma", word),
            guid=entry.get("guid"),
            definition=entry.get("definition"),
            pos_type=entry.get("pos_type"),
            pos_subtype=entry.get("pos_subtype"),
            translations=entry.get("translations", {}),
            derivative_form=entry.get("form") or fallback_form,
        )

    def annotate_text(self, text: str) -> Dict[str, dict]:
        """Process text and return word→annotation mapping for all matched words.

        Each unique word is looked up once. Results include both vocabulary
        entries and stopwords (with ``is_stopword: true``).

        Args:
            text: Raw text (AML markup before HTML conversion)

        Returns:
            Dictionary mapping lowercase word to annotation dict
        """
        if not self._loaded:
            return {}

        annotations: Dict[str, dict] = {}
        seen: set[str] = set()

        for match in WORD_PATTERN.finditer(text):
            word = match.group()
            key = word.lower()
            if key in seen or len(key) < 2:
                continue
            seen.add(key)

            ann = self.get_annotation(word)
            if ann is None:
                continue

            result: dict = {
                "lemma": ann.lemma,
                "pos_type": ann.pos_type,
            }
            if ann.is_stopword:
                result["is_stopword"] = True
            else:
                if ann.guid:
                    result["guid"] = ann.guid
                if ann.definition:
                    result["definition"] = ann.definition
                if ann.pos_subtype:
                    result["pos_subtype"] = ann.pos_subtype
                if ann.translations:
                    translations = dict(ann.translations)
                    zh_text = translations.get("zh")
                    if zh_text:
                        py = _get_pinyin_for_chinese(zh_text)
                        if py:
                            translations["zh_pinyin"] = py
                    result["translations"] = translations
                if ann.derivative_form:
                    result["form"] = ann.derivative_form
            annotations[key] = result

        return annotations


# Global singleton
default_processor = EnglishAnnotationProcessor()


def annotate_english(text: str) -> Dict[str, dict]:
    """Convenience function using the default processor."""
    return default_processor.annotate_text(text)
