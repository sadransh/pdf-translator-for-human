__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

import os
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL_FALLBACK = "translategemma:12b"

PREDEFINED_MODELS: List[str] = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "translategemma:12b",
    "translategemma:7b",
    "translategemma:27b",
    "llama3.1:8b",
    "llama3:8b",
    "mistral:7b",
    "qwen2:7b",
    "qwen2.5:7b",
    "deepseek-coder:6.7b",
    "deepseek-r1:7b",
    "gemma2:9b",
    "phi3:3.8b",
    "codellama:7b",
]

MODEL_DISPLAY_NAMES: Dict[str, str] = {
    "gpt-4o-mini": "GPT-4o Mini (OpenAI)",
    "gpt-4o": "GPT-4o (OpenAI)",
    "gpt-4-turbo": "GPT-4 Turbo (OpenAI)",
    "gpt-4": "GPT-4 (OpenAI)",
    "gpt-3.5-turbo": "GPT-3.5 Turbo (OpenAI)",
    "translategemma:12b": "TranslateGemma 12B (Local)",
    "translategemma:7b": "TranslateGemma 7B (Local)",
    "translategemma:27": "TranslateGemma 7B (Local)",
    "llama3.1:8b": "Llama 3.1 8B (Local)",
    "llama3:8b": "Llama 3 8B (Local)",
    "mistral:7b": "Mistral 7B (Local)",
    "qwen2:7b": "Qwen 2 7B (Local)",
    "qwen2.5:7b": "Qwen 2.5 7B (Local)",
    "deepseek-coder:6.7b": "DeepSeek Coder 6.7B (Local)",
    "deepseek-r1:7b": "DeepSeek R1 7B (Local)",
    "gemma2:9b": "Gemma 2 9B (Local)",
    "phi3:3.8b": "Phi-3 3.8B (Local)",
    "codellama:7b": "CodeLlama 7B (Local)",
}

CUSTOM_MODEL_OPTION = "Custom (enter below)"


def get_available_models() -> List[str]:
    env_models = os.environ.get("AVAILABLE_MODELS", "")
    if env_models:
        custom_models = [m.strip() for m in env_models.split(",") if m.strip()]
        all_models = list(PREDEFINED_MODELS)
        for m in custom_models:
            if m not in all_models:
                all_models.append(m)
        return all_models
    return list(PREDEFINED_MODELS)


def get_default_model() -> str:
    return (
        os.environ.get("DEFAULT_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or DEFAULT_MODEL_FALLBACK
    )


def get_model_display_name(model: str) -> str:
    return MODEL_DISPLAY_NAMES.get(model, model)
