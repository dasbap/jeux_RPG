"""
Internationalization (i18n) module for the RPG game.

Provides translation functionality with lazy loading of language files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Default language
DEFAULT_LANGUAGE = "en"

# Supported languages
SUPPORTED_LANGUAGES = {"fr", "en", "ja"}

# Cache for loaded translations
_translations: dict[str, dict[str, str]] = {}


def _get_translations_dir() -> Path:
    """Get the translations directory path."""
    return Path(__file__).parent / "translations"


def _load_language(lang: str) -> dict[str, str]:
    """
    Load translations for a specific language.
    
    Args:
        lang: Language code (fr, en, ja)
        
    Returns:
        Dict of translation key -> translated string
    """
    if lang in _translations:
        return _translations[lang]
    
    translations_path = _get_translations_dir() / f"{lang}.json"
    
    if not translations_path.exists():
        # Fallback to default language
        if lang != DEFAULT_LANGUAGE:
            return _load_language(DEFAULT_LANGUAGE)
        return {}
    
    with open(translations_path, "r", encoding="utf-8") as f:
        _translations[lang] = json.load(f)
    
    return _translations[lang]


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
    """
    Translate a key to the specified language.
    
    Args:
        key: Translation key (e.g., "nav.enter_building")
        lang: Language code (fr, en, ja)
        **kwargs: Format variables to inject into the string
        
    Returns:
        Translated string with variables interpolated
        
    Example:
        >>> t("nav.enter_building", "fr", building_name="Forge")
        "Tu entres dans Forge."
    """
    translations = _load_language(lang)
    
    # Get nested keys (e.g., "nav.enter_building" -> translations["nav"]["enter_building"])
    text = translations.get(key)
    
    if text is None:
        # Fallback to default language
        if lang != DEFAULT_LANGUAGE:
            return t(key, DEFAULT_LANGUAGE, **kwargs)
        # Return the key itself if not found
        return key
    
    # Format with provided variables
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            # If format fails, return unformatted text
            pass
    
    return text


def get_translator(lang: str = DEFAULT_LANGUAGE):
    """
    Get a translator function for a specific language.
    
    Args:
        lang: Language code
        
    Returns:
        Function that translates keys for the specified language
        
    Example:
        >>> tr = get_translator("en")
        >>> tr("nav.enter_building", building_name="Forge")
        "You enter Forge."
    """
    def translator(key: str, **kwargs: Any) -> str:
        return t(key, lang, **kwargs)
    return translator


def clear_cache() -> None:
    """Clear the translations cache. Useful for testing."""
    _translations.clear()


def is_supported_language(lang: str) -> bool:
    """Check if a language is supported."""
    return lang in SUPPORTED_LANGUAGES


def get_player_language(user_id: str) -> str:
    """
    Get the language preference for a player.
    
    This integrates with the bot's storage system to get
    the player's chosen language from their save file.
    
    Args:
        user_id: Discord user ID
        
    Returns:
        Language code (fr, en, ja)
    """
    try:
        from bot.game.storage import get_player_language as storage_get_lang
        return storage_get_lang(user_id)
    except ImportError:
        return DEFAULT_LANGUAGE


def t_player(key: str, user_id: str, **kwargs: Any) -> str:
    """
    Translate a key using the player's language preference.
    
    Args:
        key: Translation key
        user_id: Discord user ID
        **kwargs: Format variables
        
    Returns:
        Translated string in player's language
    """
    lang = get_player_language(user_id)
    return t(key, lang, **kwargs)


def translate_class_name(class_name: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """
    Translate a class name to the specified language.
    
    Args:
        class_name: Internal class name (e.g., "Knight", "Priest")
        lang: Language code (fr, en, ja)
        
    Returns:
        Translated class name, or original if no translation found
    """
    key = f"class.{class_name}"
    translated = t(key, lang)
    # If translation returns the key itself, return original class name
    return translated if translated != key else class_name


def translate_class_name_player(class_name: str, user_id: str) -> str:
    """
    Translate a class name using the player's language preference.
    
    Args:
        class_name: Internal class name
        user_id: Discord user ID
        
    Returns:
        Translated class name in player's language
    """
    lang = get_player_language(user_id)
    return translate_class_name(class_name, lang)


def translate_class_list(class_names: list[str], lang: str = DEFAULT_LANGUAGE) -> list[str]:
    """
    Translate a list of class names.
    
    Args:
        class_names: List of internal class names
        lang: Language code
        
    Returns:
        List of translated class names
    """
    return [translate_class_name(name, lang) for name in class_names]


def translate_class_list_player(class_names: list[str], user_id: str) -> list[str]:
    """
    Translate a list of class names using the player's language.
    
    Args:
        class_names: List of internal class names
        user_id: Discord user ID
        
    Returns:
        List of translated class names in player's language
    """
    lang = get_player_language(user_id)
    return translate_class_list(class_names, lang)


def get_internal_class_name(translated_name: str, available_classes: list[str]) -> str | None:
    """
    Find the internal class name from a translated name.
    
    Searches all languages to find a match.
    
    Args:
        translated_name: The translated class name (e.g., "Chevalier", "ナイト")
        available_classes: List of valid internal class names
        
    Returns:
        Internal class name if found, None otherwise
    """
    translated_lower = translated_name.lower()
    
    # First check if it's already an internal name
    for internal_name in available_classes:
        if internal_name.lower() == translated_lower:
            return internal_name
    
    # Search in all languages
    for lang in SUPPORTED_LANGUAGES:
        for internal_name in available_classes:
            translated = translate_class_name(internal_name, lang)
            if translated.lower() == translated_lower:
                return internal_name
    
    return None


__all__ = [
    "t",
    "t_player",
    "get_translator",
    "get_player_language",
    "clear_cache",
    "is_supported_language",
    "translate_class_name",
    "translate_class_name_player",
    "translate_class_list",
    "translate_class_list_player",
    "get_internal_class_name",
    "DEFAULT_LANGUAGE",
    "SUPPORTED_LANGUAGES",
]
