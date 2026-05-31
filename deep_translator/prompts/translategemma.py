__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

TEMPLATE = """You are a professional {source_lang} ({source_code}) to {target_lang} ({target_code}) translator. Your goal is to accurately convey the meaning and nuances of the original {source_lang} text while adhering to {target_lang} grammar, vocabulary, and cultural sensitivities.
Produce only the {target_lang} translation, without any additional explanations or commentary. Please translate the following {source_lang} text into {target_lang}:


{text}
"""


def build_prompt(
    text: str,
    source_lang: str,
    source_code: str,
    target_lang: str,
    target_code: str,
) -> str:
    return TEMPLATE.format(
        text=text,
        source_lang=source_lang,
        source_code=source_code,
        target_lang=target_lang,
        target_code=target_code,
    )
