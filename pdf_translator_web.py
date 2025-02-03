import os
import json
import hashlib
from pathlib import Path
import streamlit as st
import pymupdf
from deep_translator import (
    GoogleTranslator,
    ChatGptTranslator,
)

# Constants
DEFAULT_PAGES_PER_LOAD = 2
DEFAULT_MODEL = "default_model"
DEFAULT_API_BASE = "http://localhost:8080/v1"

# Supported translators
TRANSLATORS = {
    'google': GoogleTranslator,
    'chatgpt': ChatGptTranslator,
}

# Color options
COLOR_MAP = {
    "darkred": (0.8, 0, 0),
    "black": (0, 0, 0),
    "blue": (0, 0, 0.8),
    "darkgreen": (0, 0.5, 0),
    "purple": (0.5, 0, 0.5),
}

# Target language options for ChatGPT
LANGUAGE_OPTIONS = {
    "简体中文": "zh-CN",
    "繁體中文": "zh-TW",
    "English": "en",
    "日本語": "ja",
    "한국어": "ko",
    "Español": "es",
    "Français": "fr",
    "Deutsch": "de",
}

# Add source language options
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

def get_cache_dir():
    """Get or create cache directory"""
    cache_dir = Path('.cached')
    cache_dir.mkdir(exist_ok=True)
    return cache_dir

def get_cache_key(file_content: bytes, page_num: int, translator_name: str, target_lang: str):
    """Generate cache key for a specific page translation"""
    # 使用文件内容的hash作为缓存key的一部分
    file_hash = hashlib.md5(file_content).hexdigest()
    return f"{file_hash}_page{page_num}_{translator_name}_{target_lang}.pdf"

def get_cached_translation(cache_key: str) -> pymupdf.Document:
    """Get cached translation if exists"""
    cache_path = get_cache_dir() / cache_key
    if cache_path.exists():
        return pymupdf.open(str(cache_path))
    return None

def save_translation_cache(doc: pymupdf.Document, cache_key: str):
    """Save translation to cache"""
    cache_path = get_cache_dir() / cache_key
    doc.save(str(cache_path))

def translate_pdf_pages(doc, doc_bytes, start_page, num_pages, translator, text_color, translator_name, target_lang):
    """Translate specific pages of a PDF document with progress and caching"""
    WHITE = pymupdf.pdfcolor["white"]
    rgb_color = COLOR_MAP.get(text_color.lower(), COLOR_MAP["darkred"])
    
    translated_pages = []
    
    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, page_num in enumerate(range(start_page, min(start_page + num_pages, doc.page_count))):
        status_text.text(f"Translating page {page_num + 1}...")
        
        # Check cache first
        cache_key = get_cache_key(doc_bytes, page_num, translator_name, target_lang)
        cached_doc = get_cached_translation(cache_key)
        
        if cached_doc is not None:
            translated_pages.append(cached_doc)
        else:
            # Create a new PDF document for this page
            new_doc = pymupdf.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            page = new_doc[0]
            
            # Extract and translate text blocks
            blocks = page.get_text("blocks", flags=pymupdf.TEXT_DEHYPHENATE)
            
            for block in blocks:
                bbox = block[:4]
                text = block[4]
                
                # Translate the text
                translated = translator.translate(text)
                
                # Cover original text with white and add translation in color
                page.draw_rect(bbox, color=None, fill=WHITE)
                page.insert_htmlbox(
                    bbox,
                    translated,
                    css=f"* {{font-family: sans-serif; color: rgb({int(rgb_color[0]*255)}, {int(rgb_color[1]*255)}, {int(rgb_color[2]*255)});}}"
                )
            
            # Save to cache
            save_translation_cache(new_doc, cache_key)
            translated_pages.append(new_doc)
        
        # Update progress
        progress = (i + 1) / min(num_pages, doc.page_count - start_page)
        progress_bar.progress(progress)
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
    
    return translated_pages

def get_page_image(page, scale=2.0):
    """Get high quality image from PDF page"""
    # 计算缩放后的尺寸
    zoom = scale
    mat = pymupdf.Matrix(zoom, zoom)
    
    # 使用高分辨率渲染页面
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    return pix

def main():
    st.set_page_config(layout="wide", page_title="PDF Translator for Human: with Local-LLM/GPT")
    st.title("PDF Translator for Human: with Local-LLM/GPT")

    # Sidebar configuration
    with st.sidebar:
        st.header("Settings")
        
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
        
        # Add source language selection
        source_lang_name = st.selectbox(
            "Source Language",
            options=list(SOURCE_LANGUAGE_OPTIONS.keys()),
            index=0  # Default to English
        )
        source_lang = SOURCE_LANGUAGE_OPTIONS[source_lang_name]
        
        translator_name = st.selectbox(
            "Select Translator",
            options=list(TRANSLATORS.keys()),
            index=0
        )
        
        pages_per_load = st.number_input(
            "Pages per load",
            min_value=1,
            max_value=5,
            value=DEFAULT_PAGES_PER_LOAD
        )
        
        text_color = st.selectbox(
            "Translation Color",
            options=list(COLOR_MAP.keys()),
            index=0
        )
        
        # ChatGPT specific settings
        if translator_name == 'chatgpt':
            st.subheader("ChatGPT Settings")
            target_lang = st.selectbox(
                "Target Language",
                options=list(LANGUAGE_OPTIONS.keys()),
                index=0
            )
            api_key = st.text_input(
                "OpenAI API Key",
                value=os.getenv("OPENAI_API_KEY", ""),
                type="password"
            )
            api_base = st.text_input(
                "API Base URL",
                value=os.getenv("OPENAI_API_BASE", DEFAULT_API_BASE)
            )
            model = st.text_input(
                "Model Name",
                value=os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
            )
            
            # Update environment variables
            os.environ["OPENAI_API_KEY"] = api_key
            os.environ["OPENAI_API_BASE"] = api_base
            os.environ["OPENAI_MODEL"] = model
            target_lang = LANGUAGE_OPTIONS[target_lang]
        else:
            # For Google Translator, also show target language selection
            target_lang_name = st.selectbox(
                "Target Language",
                options=list(SOURCE_LANGUAGE_OPTIONS.keys())[:-1],  # Remove "Auto" option
                index=0  # Default to first language
            )
            target_lang = SOURCE_LANGUAGE_OPTIONS[target_lang_name]

    # Main content area
    if uploaded_file is not None:
        doc_bytes = uploaded_file.read()
        doc = pymupdf.open(stream=doc_bytes)
        
        # Create two columns for side-by-side display
        col1, col2 = st.columns(2)
        
        # Initialize session state
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 0
            st.session_state.translation_started = True  # 自动开始翻译
        
        # Display original pages immediately
        with col1:
            st.header("Original")
            for page_num in range(st.session_state.current_page,
                                min(st.session_state.current_page + pages_per_load, doc.page_count)):
                page = doc[page_num]
                pix = get_page_image(page)
                st.image(pix.tobytes(), caption=f"Page {page_num + 1}", use_container_width=True)
        
        # Translation column
        with col2:
            st.header("Translated")
            
            # Configure translator with selected source language
            TranslatorClass = TRANSLATORS[translator_name]
            translator = TranslatorClass(source=source_lang, target=target_lang)
            
            # Translate current batch of pages
            translated_pages = translate_pdf_pages(
                doc,
                doc_bytes,
                st.session_state.current_page,
                pages_per_load,
                translator,
                text_color,
                translator_name,
                target_lang
            )
            
            # Display translated pages
            for i, trans_doc in enumerate(translated_pages):
                page = trans_doc[0]
                pix = get_page_image(page)
                st.image(pix.tobytes(), caption=f"Page {st.session_state.current_page + i + 1}", use_container_width=True)
        
        # Navigation buttons
        nav_col1, nav_col2 = st.columns(2)
        with nav_col1:
            if st.session_state.current_page > 0:
                if st.button("Previous Pages"):
                    st.session_state.current_page = max(0, st.session_state.current_page - pages_per_load)
                    st.rerun()
        
        with nav_col2:
            if st.session_state.current_page + pages_per_load < doc.page_count:
                if st.button("Next Pages"):
                    st.session_state.current_page = min(
                        doc.page_count - 1,
                        st.session_state.current_page + pages_per_load
                    )
                    st.rerun()
    else:
        st.info("Please upload a PDF file to begin translation")

if __name__ == "__main__":
    main() 