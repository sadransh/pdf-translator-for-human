import json
import time
import os,logging

import streamlit as st
from .chatgpt import ChatGptTranslator

logging.basicConfig(filename='application.log', level=logging.INFO, format='%(asctime)s - %(levelname)-5s %(lineno)d %(filename)s:%(funcName)s - %(message)s')

class OpenAICompatibleTranslator(ChatGptTranslator):
    """Translator that handles OpenAI compatible APIs with better error handling"""
    def __init__(self, source="en", target="zh-CN", **kwargs):
        super().__init__(source=source, target=target, **kwargs)
        self.retry_count = 3
        self.retry_delay = 1  # seconds

    def translate(self, text: str, **kwargs) -> str:
        """
        Translate text with retry mechanism and error handling
        """
        if not text.strip():
            return text

        for attempt in range(self.retry_count):
            try:
                logging.info(f"Request OpenAI compatible api, base_url: {self.base_url}")
                return super().translate(text, **kwargs)
            except json.JSONDecodeError:
                logging.warn(f"Translation API response JSONDecodeError, will retry later...")
                if attempt == self.retry_count - 1:
                    logging.error(f"Translation API response error, using original text")
                    st.warning(f"Translation API response error, using original text")
                    return text
                time.sleep(self.retry_delay)
            except Exception as e:
                logging.error(f"Translation error: {str(e)}")
                st.error(f"Translation error: {str(e)}")
                return text 