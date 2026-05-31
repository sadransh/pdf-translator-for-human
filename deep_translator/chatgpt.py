__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

import logging
import os
from typing import List, Optional

from deep_translator.base import BaseTranslator
from deep_translator.constants import (
    GOOGLE_LANGUAGES_TO_CODES,
    OPEN_AI_BASE_URL_ENV_VAR,
    OPEN_AI_ENV_VAR,
    OPEN_AI_MODEL_ENV_VAR,
)
from deep_translator.exceptions import ApiKeyException
from deep_translator.prompts import build_prompt

logging.basicConfig(
    filename="application.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)-5s %(lineno)d %(filename)s:%(funcName)s - %(message)s",
)


class ChatGptTranslator(BaseTranslator):
    """
    class that wraps functions, which use the ChatGPT
    under the hood to translate word(s)
    """

    def __init__(
        self,
        source: str = "auto",
        target: str = "english",
        api_key: Optional[str] = os.getenv(OPEN_AI_ENV_VAR, None),
        model: Optional[str] = os.getenv(OPEN_AI_MODEL_ENV_VAR, "gpt-4o-mini"),
        base_url: Optional[str] = os.getenv(OPEN_AI_BASE_URL_ENV_VAR, None),
        **kwargs,
    ):
        """
        @param api_key: your openai api key.
        @param source: source language
        @param target: target language
        @param model: OpenAI model to use
        @param base_url: custom OpenAI API base URL
        """
        if not api_key:
            raise ApiKeyException(env_var=OPEN_AI_ENV_VAR)

        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        super().__init__(source=source, target=target, **kwargs)

    def translate(self, text: str, **kwargs) -> str:
        """
        @param text: text to translate
        @return: translated text
        """
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url if self.base_url else None,
        )

        source_lang = self._get_language_name(self._source)
        target_lang = self._get_language_name(self._target)
        source_code = self._source if self._source != "auto" else "auto"
        target_code = self._target

        prompt = build_prompt(
            model_name=self.model or "default",
            text=text,
            source_lang=source_lang,
            source_code=source_code,
            target_lang=target_lang,
            target_code=target_code,
        )

        logging.info(f"Using model: {self.model}")
        logging.info(f"Prompt: {prompt}")

        response = client.chat.completions.create(
            model=self.model if self.model else "default_model",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        resp = response.choices[0].message.content or ""
        logging.info(f"model response:{resp}")
        return resp

    def _get_language_name(self, code: str) -> str:
        for name, c in GOOGLE_LANGUAGES_TO_CODES.items():
            if c == code:
                return name.title()
        return code

    def translate_file(self, path: str, **kwargs) -> str:
        return self._translate_file(path, **kwargs)

    def translate_batch(self, batch: List[str], **kwargs) -> List[str]:
        """
        @param batch: list of texts to translate
        @return: list of translations
        """
        return self._translate_batch(batch, **kwargs)
