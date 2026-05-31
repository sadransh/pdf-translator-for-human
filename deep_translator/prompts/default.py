__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

TEMPLATE = """Translate the text below into {target_lang}.

Text: "{text}"
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
