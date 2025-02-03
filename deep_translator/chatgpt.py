__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

import os
from typing import List, Optional

from deep_translator.base import BaseTranslator
from deep_translator.constants import (
    OPEN_AI_ENV_VAR,
    OPEN_AI_BASE_URL_ENV_VAR,
    OPEN_AI_MODEL_ENV_VAR,
)
from deep_translator.exceptions import ApiKeyException


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
            base_url=self.base_url if self.base_url else None
        )

        prompt = f"Translate the text below into {self.target}.\n"
        prompt += f'Text: "{text}"'

        # if model is empty (for mlx_lm.server, the model should be default_model)
        # export OPENAI_MODEL=default_model
        response = client.chat.completions.create(
            model=self.model if self.model else "default_model",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        

        return response.choices[0].message.content

    def translate_file(self, path: str, **kwargs) -> str:
        return self._translate_file(path, **kwargs)

    def translate_batch(self, batch: List[str], **kwargs) -> List[str]:
        """
        @param batch: list of texts to translate
        @return: list of translations
        """
        return self._translate_batch(batch, **kwargs)
