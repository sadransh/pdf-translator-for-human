import argparse
import logging
import os
from typing import Optional

import pymupdf
import streamlit as st
from dotenv import load_dotenv

from deep_translator import GoogleTranslator
from deep_translator.models_config import (
    CUSTOM_MODEL_OPTION,
    get_available_models,
    get_default_model,
    get_model_display_name,
)
from deep_translator.openai_compatible import OpenAICompatibleTranslator
from deep_translator.pdf_translator import COLOR_MAP, get_page_image
from deep_translator.pdf_translator import (
    translate_all_pages as shared_translate_all_pages,
)
from deep_translator.pdf_translator import (
    translate_pdf_pages as shared_translate_pdf_pages,
)

load_dotenv()

DEFAULT_PAGES_PER_LOAD = 3
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL")
DEFAULT_API_BASE = os.environ.get("OPENAI_API_BASE", "http://localhost:8080/v1")

TRANSLATORS = {
    "OpenAI Compatible": OpenAICompatibleTranslator,
    "OpenAI": OpenAICompatibleTranslator,
    "Google": GoogleTranslator,
}

LANGUAGE_OPTIONS = {
    "简体中文": "zh-CN",
    "繁體中文": "zh-TW",
    "English": "en",
    "日本語": "ja",
    "한국어": "ko",
    "Español": "es",
    "Français": "fr",
    "Deutsch": "de",
    "persian": "fa",
}

SOURCE_LANGUAGE_OPTIONS = {
    "English": "en",
    "简体中文": "zh-CN",
    "繁體中文": "zh-TW",
    "日本語": "ja",
    "한국어": "ko",
    "Español": "es",
    "Français": "fr",
    "Deutsch": "de",
    "Auto": "auto",
}

TRANSLATOR_CONFIG = {
    "type": "Google",
    "openai": {
        "default_api_base": DEFAULT_API_BASE,
        "default_model": DEFAULT_MODEL,
        "default_api_key": "ollama",
    },
    "google": {"default_api_base": "https://translate.googleapis.com"},
}


def parse_args():
    parser = argparse.ArgumentParser(description="PDF Translator Application")
    parser.add_argument(
        "--translator",
        type=str,
        choices=["google", "openai"],
        default="openai",
        help="Specify translator type: google or openai",
    )
    parser.add_argument("--api-base", type=str, help="API base URL for the translator")
    parser.add_argument(
        "--api-key", type=str, help="API key for OpenAI compatible translator"
    )
    parser.add_argument(
        "--model", type=str, help="Model name for OpenAI compatible translator"
    )
    return parser.parse_args()


def update_translator_config(args):
    global TRANSLATOR_CONFIG

    TRANSLATOR_CONFIG["type"] = (
        "Google" if args.translator.lower() == "google" else "OpenAI"
    )

    if args.translator.lower() == "google":
        if args.api_base:
            TRANSLATOR_CONFIG["google"]["default_api_base"] = args.api_base
    else:
        if args.api_base:
            TRANSLATOR_CONFIG["openai"]["default_api_base"] = args.api_base
        if args.api_key:
            TRANSLATOR_CONFIG["openai"]["default_api_key"] = args.api_key
        if args.model:
            TRANSLATOR_CONFIG["openai"]["default_model"] = args.model


class StreamlitProgressCallback:
    def __init__(self):
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()
        self.total = 1

    def __call__(self, current: int, total: int, message: str):
        self.total = max(self.total, total)
        self.status_text.text(message)
        self.progress_bar.progress(current / self.total)


def translate_pdf_pages(
    doc,
    doc_bytes,
    start_page,
    num_pages,
    translator,
    text_color,
    translator_name,
    target_lang,
    pdf_path: Optional[str] = None,
):
    progress_callback = StreamlitProgressCallback()

    translated_pages = shared_translate_pdf_pages(
        doc=doc,
        start_page=start_page,
        num_pages=num_pages,
        translator=translator,
        target_lang=target_lang,
        text_color=text_color,
        translator_name=translator_name,
        pdf_path=pdf_path,
        progress_callback=progress_callback,
        use_cache=True,
        add_footer=True,
    )

    progress_callback.progress_bar.empty()

    return translated_pages


def translate_all_pages(
    input_doc,
    output_doc,
    translator,
    progress_bar,
    batch_size=1,
    pdf_path=None,
    **kwargs,
):
    output_path = kwargs.get("output_path", "output.pdf")

    result_path = shared_translate_all_pages(
        input_doc=input_doc,
        translator=translator,
        target_lang=kwargs.get("target_lang", "fa"),
        output_path=output_path,
        text_color=kwargs.get("text_color", "darkred"),
        translator_name=kwargs.get("translator_name", "google"),
        pdf_path=pdf_path,
        use_cache=True,
        add_footer=True,
    )

    output_doc.insert_pdf(pymupdf.open(result_path))
    return output_doc


def init_session_state():
    if "current_page" not in st.session_state:
        st.session_state.current_page = 0
    if "translation_started" not in st.session_state:
        st.session_state.translation_started = True
    if "all_translated" not in st.session_state:
        st.session_state.all_translated = False
    if "translated_doc" not in st.session_state:
        st.session_state.translated_doc = None
    if "previous_file" not in st.session_state:
        st.session_state.previous_file = None
    if "api_settings" not in st.session_state:
        st.session_state.api_settings = {}


def main():
    st.set_page_config(layout="wide", page_title="PDF Translator for Human")
    st.title("PDF Translator for Human")

    init_session_state()

    with st.sidebar:
        st.header("Settings")

        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

        if uploaded_file is not None and (
            st.session_state.previous_file is None
            or uploaded_file.name != st.session_state.previous_file
        ):
            st.session_state.current_page = 0
            st.session_state.translation_started = True
            st.session_state.all_translated = False
            st.session_state.translated_doc = None
            st.session_state.previous_file = uploaded_file.name
            st.rerun()

        source_lang_name = st.selectbox(
            "Source Language",
            options=list(SOURCE_LANGUAGE_OPTIONS.keys()),
            index=0,
        )
        source_lang = SOURCE_LANGUAGE_OPTIONS[source_lang_name]

        pages_per_load = st.number_input(
            "Pages per load",
            min_value=1,
            max_value=5,
            value=DEFAULT_PAGES_PER_LOAD,
        )

        text_color = st.selectbox(
            "Translation Color", options=list(COLOR_MAP.keys()), index=0
        )

        target_lang = st.selectbox(
            "Target Language",
            options=list(LANGUAGE_OPTIONS.keys()),
            index=list(LANGUAGE_OPTIONS.keys()).index("persian"),
        )
        target_lang_code = LANGUAGE_OPTIONS[target_lang]

        st.subheader("Translator Settings")
        translator_type = st.radio(
            "Translator",
            options=["Google", "OpenAI Compatible"],
            index=0 if TRANSLATOR_CONFIG["type"] == "Google" else 1,
        )

        if translator_type == "OpenAI Compatible":
            api_key = st.text_input(
                "API Key",
                value=TRANSLATOR_CONFIG["openai"]["default_api_key"],
                type="password",
            )
            api_base = st.text_input(
                "API Base URL",
                value=TRANSLATOR_CONFIG["openai"]["default_api_base"],
            )

            available_models = get_available_models()
            default_model = get_default_model()

            model_options = available_models + [CUSTOM_MODEL_OPTION]
            default_index = (
                model_options.index(default_model)
                if default_model in model_options
                else 0
            )

            selected_model = st.selectbox(
                "Model",
                options=model_options,
                index=default_index,
                format_func=lambda x: (
                    get_model_display_name(x) if x != CUSTOM_MODEL_OPTION else x
                ),
            )

            if selected_model == CUSTOM_MODEL_OPTION:
                custom_model = st.text_input(
                    "Custom Model Name",
                    value=default_model,
                    placeholder="e.g., my-custom-model:7b",
                )
                model = custom_model
            else:
                model = selected_model

            st.session_state.api_settings.update(
                {"api_key": api_key, "api_base": api_base, "model": model}
            )
        else:
            st.session_state.api_settings.update(
                {"api_base": TRANSLATOR_CONFIG["google"]["default_api_base"]}
            )

    if uploaded_file is not None:
        doc_bytes = uploaded_file.read()
        doc = pymupdf.open(stream=doc_bytes)

        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(doc_bytes)
            pdf_temp_path = tmp_file.name

        col1, col2 = st.columns(2)

        with col1:
            st.header("Original")
            for page_num in range(
                st.session_state.current_page,
                min(
                    st.session_state.current_page + pages_per_load,
                    doc.page_count,
                ),
            ):
                page = doc[page_num]
                pix = get_page_image(page)
                st.image(
                    pix,
                    caption=f"Page {page_num + 1}",
                    width="stretch",
                )

        with col2:
            st.header("Translated")

            try:
                if translator_type == "Google":
                    translator = GoogleTranslator(
                        source=source_lang, target=target_lang_code
                    )
                else:
                    translator = OpenAICompatibleTranslator(
                        source=source_lang,
                        target=target_lang_code,
                        api_key=st.session_state.api_settings.get("api_key"),
                        base_url=st.session_state.api_settings.get("api_base"),
                        model=st.session_state.api_settings.get("model"),
                    )

                translated_pages = translate_pdf_pages(
                    doc,
                    doc_bytes,
                    st.session_state.current_page,
                    pages_per_load,
                    translator,
                    text_color,
                    translator_type,
                    target_lang_code,
                    pdf_path=pdf_temp_path,
                )

                for i, trans_doc in enumerate(translated_pages):
                    page = trans_doc[0]
                    pix = get_page_image(page)
                    st.image(
                        pix,
                        caption=f"Page {st.session_state.current_page + i + 1}",
                        width="stretch",
                    )

            except Exception as e:
                st.error(f"Translation error: {str(e)}")
                logging.error(f"Translation error: {str(e)}")
                return

        st.markdown("---")
        button_col1, button_col2, button_col3, button_col4 = st.columns(4)

        with button_col1:
            if st.session_state.current_page > 0:
                if st.button("Previous Pages", width="stretch"):
                    st.session_state.current_page = max(
                        0, st.session_state.current_page - pages_per_load
                    )
                    st.rerun()
            else:
                st.button("Previous Pages", disabled=True, width="stretch")

        with button_col2:
            if st.session_state.current_page + pages_per_load < doc.page_count:
                if st.button("Next Pages", width="stretch"):
                    st.session_state.current_page = min(
                        doc.page_count - 1,
                        st.session_state.current_page + pages_per_load,
                    )
                    st.rerun()
            else:
                st.button("Next Pages", disabled=True, width="stretch")

        with button_col3:
            if st.button(
                "Translate All",
                disabled=st.session_state.all_translated,
                width="stretch",
            ):
                try:
                    if translator_type == "Google":
                        translator = GoogleTranslator(
                            source=source_lang, target=target_lang_code
                        )
                    else:
                        translator = OpenAICompatibleTranslator(
                            source=source_lang,
                            target=target_lang_code,
                            api_key=st.session_state.api_settings.get("api_key"),
                            base_url=st.session_state.api_settings.get("api_base"),
                            model=st.session_state.api_settings.get("model"),
                        )

                    output_doc = pymupdf.open()
                    output_path = f"translated_{uploaded_file.name}"
                    output_doc = translate_all_pages(
                        doc,
                        output_doc,
                        translator,
                        st.empty(),
                        pages_per_load,
                        pdf_path=pdf_temp_path,
                        text_color=text_color,
                        translator_name=translator_type,
                        target_lang=target_lang_code,
                        output_path=output_path,
                    )

                    st.session_state.all_translated = True
                    st.session_state.translated_doc = output_path
                    st.rerun()
                except Exception as e:
                    st.error(f"Translation error: {str(e)}")
                    logging.error(f"Translation error: {str(e)}")
                    return

        with button_col4:
            if not st.session_state.all_translated:
                st.markdown(
                    """
                    <div title="You can download the translated file after all content has been translated">
                        <button style="width: 100%" disabled>Download</button>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                with open(st.session_state.translated_doc, "rb") as file:
                    st.download_button(
                        "Download",
                        file,
                        file_name=f"translated_{uploaded_file.name}",
                        mime="application/pdf",
                        width="stretch",
                    )
    else:
        st.info("Please upload a PDF file to begin translation")


if __name__ == "__main__":
    args = parse_args()
    update_translator_config(args)
    main()
