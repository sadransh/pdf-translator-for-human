import os
import json
import hashlib
from pathlib import Path
import streamlit as st
import pymupdf
from deep_translator import (
    GoogleTranslator,
)
from deep_translator.openai_compatible import OpenAICompatibleTranslator
import logging

# Constants
DEFAULT_PAGES_PER_LOAD = 2
DEFAULT_MODEL = "default_model"
DEFAULT_API_BASE = "http://localhost:8080/v1"

# Supported translators
TRANSLATORS = {
    'OpenAI Compatible': OpenAICompatibleTranslator,
    'OpenAI': OpenAICompatibleTranslator,
    'google': GoogleTranslator,
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

def get_cache_key(doc_info: dict, page_num: int, translator_name: str, target_lang: str, text_content: str):
    """Generate cache key for a specific page translation"""
    # 使用文档信息和页面内容的组合生成唯一标识
    content_hash = hashlib.md5(text_content.encode('utf-8')).hexdigest()[:8]
    doc_id = f"{doc_info.get('title', '')}_{doc_info.get('author', '')}_{doc_info.get('pagecount', '')}"
    doc_hash = hashlib.md5(doc_id.encode('utf-8')).hexdigest()[:8]
    return f"{doc_hash}_{content_hash}_page{page_num}_{translator_name}_{target_lang}.pdf"

def get_cached_translation(cache_key: str) -> pymupdf.Document:
    """Get cached translation if exists"""
    cache_path = get_cache_dir() / cache_key
    if cache_path.exists():
        try:
            return pymupdf.open(str(cache_path))
        except Exception as e:
            logging.error(f"Error loading cache: {str(e)}")
            return None
    return None

def save_translation_cache(doc: pymupdf.Document, cache_key: str):
    """Save translation to cache"""
    cache_path = get_cache_dir() / cache_key
    doc.save(str(cache_path))  # 确保提供文件路径字符串

def translate_pdf_pages(doc, doc_bytes, start_page, num_pages, translator, text_color, translator_name, target_lang):
    """Translate specific pages of a PDF document with progress and caching"""
    WHITE = pymupdf.pdfcolor["white"]
    rgb_color = COLOR_MAP.get(text_color.lower(), COLOR_MAP["darkred"])
    
    translated_pages = []
    total_pages = min(start_page + num_pages, doc.page_count) - start_page
    cache_hits = 0
    
    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, page_num in enumerate(range(start_page, min(start_page + num_pages, doc.page_count))):
        status_text.text(f"Translating page {page_num + 1}...")
        
        # Extract text content for cache key
        page = doc[page_num]
        text_content = page.get_text("text")
        
        # Check cache first using text content
        cache_key = get_cache_key(
            doc.metadata,
            page_num,
            translator_name,
            target_lang,
            text_content
        )
        
        cached_doc = get_cached_translation(cache_key)
        
        if cached_doc is not None:
            translated_pages.append(cached_doc)
            cache_hits += 1
            logging.info(f"Cache hit: Using cached translation for page {page_num + 1}")
            status_text.text(f"Using cached translation for page {page_num + 1}")
        else:
            logging.info(f"Cache miss: Translating page {page_num + 1}")
            status_text.text(f"Translating page {page_num + 1} (not in cache)")
            
            # Create a new PDF document for this page
            new_doc = pymupdf.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            page = new_doc[0]
            
            # Extract and translate text blocks
            blocks = page.get_text("blocks", flags=pymupdf.TEXT_DEHYPHENATE)
            
            for block in blocks:
                bbox = block[:4]
                text = block[4]
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
            logging.info(f"Cached new translation for page {page_num + 1}")
        
        # Update progress
        progress = (i + 1) / total_pages
        progress_bar.progress(progress)
    
    # Clear progress indicators and show summary
    progress_bar.empty()
    if cache_hits > 0:
        st.info(f"Used cache for {cache_hits} out of {total_pages} pages")
    
    return translated_pages

def get_page_image(page, scale=2):
    """Get high quality image from PDF page"""
    # 计算缩放后的尺寸
    zoom = scale
    mat = pymupdf.Matrix(zoom, zoom)
    
    # 使用较低分辨率渲染页面，但保持清晰度
    pix = page.get_pixmap(
        matrix=mat,
        alpha=False,
        colorspace="rgb",  # Use RGB instead of RGBA
    )
    
    return pix

def translate_all_pages(
    input_doc,
    output_doc,
    translator,
    progress_bar,
    batch_size=1,
    **kwargs
):
    """Translate all pages of the PDF document"""
    # Define colors
    WHITE = pymupdf.pdfcolor["white"]
    rgb_color = COLOR_MAP.get(kwargs.get('text_color', 'darkred').lower(), COLOR_MAP["darkred"])
    
    total_pages = input_doc.page_count
    
    # Create a progress bar for overall progress
    status_text = st.empty()
    
    # Translate all pages using translate_pdf_pages
    translated_pages = translate_pdf_pages(
        input_doc,
        None,  # doc_bytes not needed as we're using text content for cache
        0,  # start from first page
        total_pages,  # translate all pages
        translator,
        kwargs.get('text_color', 'darkred'),
        kwargs.get('translator_name', 'google'),
        kwargs.get('target_lang', 'zh-CN')
    )
    
    # Combine all pages into one PDF with compression
    output_path = kwargs.get('output_path', 'output.pdf')
    for trans_doc in translated_pages:
        output_doc.insert_pdf(trans_doc)
    
    # Save with compression options
    output_doc.save(
        output_path,
        garbage=4,
        deflate=True,
        clean=True,
        linear=True
    )
    
    return output_doc

def main():
    st.set_page_config(layout="wide", page_title="PDF Translator for Human: with Local-LLM/GPT")
    st.title("PDF Translator for Human: with Local-LLM/GPT")

    # Sidebar configuration
    with st.sidebar:
        st.header("Settings")
        
        # Store previous file name to detect changes
        previous_file = st.session_state.get('previous_file', None)
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
        
        # Reset session state when a new file is uploaded
        if uploaded_file is not None and (previous_file is None or uploaded_file.name != previous_file):
            # Reset all relevant session state variables
            st.session_state.current_page = 0
            st.session_state.translation_started = True
            st.session_state.all_translated = False
            st.session_state.translated_doc = None
            st.session_state.previous_file = uploaded_file.name
            st.rerun()
            
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
        
        # OpenAI specific settings
        if translator_name in ['OpenAI', 'OpenAI Compatible']:
            st.subheader(f"{translator_name} Settings")
            target_lang = st.selectbox(
                "Target Language",
                options=list(LANGUAGE_OPTIONS.keys()),
                index=0
            )
            
            # Get API key from environment or user input
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                api_key = st.text_input(
                    "API Key",
                    value="sk-xxx",
                    type="password"
                )
            
            # Different default API base for OpenAI and OpenAI Compatible
            default_base = "https://api.openai.com/v1" if translator_name == 'OpenAI' else DEFAULT_API_BASE
            api_base = st.text_input(
                "API Base URL",
                value=os.getenv("OPENAI_API_BASE", default_base)
            )
            
            # Different default model for OpenAI and OpenAI Compatible
            default_model = "gpt-4o-mini" if translator_name == 'OpenAI' else DEFAULT_MODEL
            model = st.text_input(
                "Model Name",
                value=os.getenv("OPENAI_MODEL", default_model)
            )
            
            # Store API settings in session state
            if 'api_settings' not in st.session_state:
                st.session_state.api_settings = {}
            st.session_state.api_settings.update({
                'api_key': api_key,
                'api_base': api_base,
                'model': model
            })
            
            target_lang = LANGUAGE_OPTIONS[target_lang]
        else:
            # For Google Translator, show target language selection
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
        
        # Initialize translation status
        if 'all_translated' not in st.session_state:
            st.session_state.all_translated = False
        if 'translated_doc' not in st.session_state:
            st.session_state.translated_doc = None
        
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
            
            # Configure translator with selected source language and API settings
            TranslatorClass = TRANSLATORS[translator_name]
            translator = TranslatorClass(
                source=source_lang,
                target=target_lang,
                api_key=st.session_state.api_settings.get('api_key'),
                base_url=st.session_state.api_settings.get('api_base'),
                model=st.session_state.api_settings.get('model')
            )
            
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
        
        # Navigation and action buttons in one row
        st.markdown("---")  # Add a separator
        button_col1, button_col2, button_col3, button_col4 = st.columns(4)
        
        # Previous Pages button
        with button_col1:
            if st.session_state.current_page > 0:
                if st.button("Previous Pages", use_container_width=True):
                    st.session_state.current_page = max(0, st.session_state.current_page - pages_per_load)
                    st.rerun()
            else:
                st.button("Previous Pages", disabled=True, use_container_width=True)
        
        # Next Pages button
        with button_col2:
            if st.session_state.current_page + pages_per_load < doc.page_count:
                if st.button("Next Pages", use_container_width=True):
                    st.session_state.current_page = min(
                        doc.page_count - 1,
                        st.session_state.current_page + pages_per_load
                    )
                    st.rerun()
            else:
                st.button("Next Pages", disabled=True, use_container_width=True)
        
        # Translate All button
        with button_col3:
            if st.button("Translate All", 
                        disabled=st.session_state.all_translated,
                        use_container_width=True):
                # Configure translator
                TranslatorClass = TRANSLATORS[translator_name]
                translator = TranslatorClass(
                    source=source_lang,
                    target=target_lang,
                    api_key=st.session_state.api_settings.get('api_key'),
                    base_url=st.session_state.api_settings.get('api_base'),
                    model=st.session_state.api_settings.get('model')
                )
                
                # Translate all pages
                output_doc = pymupdf.open()
                output_path = f"translated_{uploaded_file.name}"
                output_doc = translate_all_pages(
                    doc,
                    output_doc,
                    translator,
                    st.empty(),
                    pages_per_load,
                    text_color=text_color,
                    translator_name=translator_name,
                    target_lang=target_lang,
                    output_path=output_path  # 提供输出路径
                )
                
                st.session_state.all_translated = True
                st.session_state.translated_doc = output_path
                st.rerun()
        
        # Download button
        with button_col4:
            if not st.session_state.all_translated:
                st.markdown(
                    """
                    <div title="You can download the translated file after all content has been translated">
                        <button style="width: 100%" disabled>Download</button>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                with open(st.session_state.translated_doc, "rb") as file:
                    st.download_button(
                        "Download",
                        file,
                        file_name=f"translated_{uploaded_file.name}",
                        mime="application/pdf",
                        use_container_width=True
                    )
    else:
        st.info("Please upload a PDF file to begin translation")

if __name__ == "__main__":
    main() 