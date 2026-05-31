__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

import logging

logging.basicConfig(
    filename="application.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)-5s %(lineno)d %(filename)s:%(funcName)s - %(message)s",
)

PERSIAN_DIGITS = {
    "0": "۰",
    "1": "۱",
    "2": "۲",
    "3": "۳",
    "4": "۴",
    "5": "۵",
    "6": "۶",
    "7": "۷",
    "8": "۸",
    "9": "۹",
}

ARABIC_DIGITS = {
    "0": "٠",
    "1": "١",
    "2": "٢",
    "3": "٣",
    "4": "٤",
    "5": "٥",
    "6": "٦",
    "7": "٧",
    "8": "٨",
    "9": "٩",
}

LANGUAGE_DIGIT_MAPS = {
    "fa": PERSIAN_DIGITS,
    "persian": PERSIAN_DIGITS,
    "ar": ARABIC_DIGITS,
    "arabic": ARABIC_DIGITS,
}

LANGUAGE_PUNCTUATION_MAPS = {
    "fa": {
        ",": "،",
        ";": "؛",
        "?": "؟",
        "%": "٪",
    },
    "persian": {
        ",": "،",
        ";": "؛",
        "?": "؟",
        "%": "٪",
    },
    "ar": {
        ",": "،",
        ";": "؛",
        "?": "؟",
        "%": "٪",
    },
    "arabic": {
        ",": "،",
        ";": "؛",
        "?": "؟",
        "%": "٪",
    },
}


def convert_digits(text: str, target_lang: str) -> str:
    """
    Convert Western Arabic digits to target language digits.

    @param text: text containing digits to convert
    @param target_lang: target language code or name
    @return: text with converted digits
    """
    lang_lower = target_lang.lower() if target_lang else ""
    digit_map = LANGUAGE_DIGIT_MAPS.get(lang_lower)

    if not digit_map:
        return text

    result = []
    for char in text:
        if char in digit_map:
            result.append(digit_map[char])
        else:
            result.append(char)

    return "".join(result)


def convert_punctuation(text: str, target_lang: str) -> str:
    """
    Convert punctuation to target language equivalents.

    @param text: text containing punctuation to convert
    @param target_lang: target language code or name
    @return: text with converted punctuation
    """
    lang_lower = target_lang.lower() if target_lang else ""
    punct_map = LANGUAGE_PUNCTUATION_MAPS.get(lang_lower)

    if not punct_map:
        return text

    result = []
    for char in text:
        if char in punct_map:
            result.append(punct_map[char])
        else:
            result.append(char)

    return "".join(result)


def postprocess_translation(
    text: str, target_lang: str, preserve_newlines: bool = True
) -> str:
    """
    Apply post-processing to translated text.

    - Convert digits to target language script
    - Convert punctuation to target language equivalents
    - Preserve newlines

    @param text: translated text to post-process
    @param target_lang: target language code or name
    @param preserve_newlines: whether to preserve newlines in output
    @return: post-processed text
    """
    if not text:
        return text

    result = text

    lang_lower = target_lang.lower() if target_lang else ""

    if lang_lower in LANGUAGE_DIGIT_MAPS:
        result = convert_digits(result, target_lang)

    if lang_lower in LANGUAGE_PUNCTUATION_MAPS:
        result = convert_punctuation(result, target_lang)

    if preserve_newlines:
        lines = result.split("\n")
        result = "\n".join(line.rstrip() for line in lines)

    return result
