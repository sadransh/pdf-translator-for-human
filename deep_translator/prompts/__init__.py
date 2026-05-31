__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

import importlib
import logging

logging.basicConfig(
    filename="application.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)-5s %(lineno)d %(filename)s:%(funcName)s - %(message)s",
)

MODEL_PATTERNS = {
    "translategemma": "translategemma",
}


def get_prompt_template(model_name: str):
    if not model_name:
        from deep_translator.prompts import default

        return default

    model_lower = model_name.lower()

    for pattern, module_name in MODEL_PATTERNS.items():
        if pattern in model_lower:
            try:
                module = importlib.import_module(
                    f"deep_translator.prompts.{module_name}"
                )
                logging.info(
                    f"Loaded prompt template '{module_name}' for model: {model_name}"
                )
                return module
            except ImportError:
                logging.warning(
                    f"Pattern '{pattern}' matched but module '{module_name}' not found"
                )

    module_name = (
        model_name.lower()
        .replace("-", "_")
        .replace(".", "_")
        .replace(":", "_")
    )
    module_name = module_name.split("/")[0].split("@")[0]

    try:
        module = importlib.import_module(
            f"deep_translator.prompts.{module_name}"
        )
        logging.info(f"Loaded prompt template for model: {model_name}")
        return module
    except ImportError:
        logging.info(
            f"No specific prompt for model '{model_name}', using default"
        )
        from deep_translator.prompts import default

        return default


def build_prompt(
    model_name: str,
    text: str,
    source_lang: str,
    source_code: str,
    target_lang: str,
    target_code: str,
) -> str:
    template_module = get_prompt_template(model_name)
    return template_module.build_prompt(
        text=text,
        source_lang=source_lang,
        source_code=source_code,
        target_lang=target_lang,
        target_code=target_code,
    )
