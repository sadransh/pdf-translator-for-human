import argparse
import os
from pathlib import Path
from typing import List, Optional

import pymupdf
from dotenv import load_dotenv

from deep_translator import GoogleTranslator
from deep_translator.models_config import get_default_model
from deep_translator.openai_compatible import OpenAICompatibleTranslator
from deep_translator.pdf_translator import translate_all_pages

TRANSLATORS = {
    "google": GoogleTranslator,
    "openai": OpenAICompatibleTranslator,
    "chatgpt": OpenAICompatibleTranslator,
}


def cli_progress_callback(current: int, total: int, message: str):
    print(f"\rTranslating page {current}/{total} - {message}", end="", flush=True)


def translate_pdf(
    input_file: str,
    source_lang: str,
    target_lang: str,
    translator_name: str = "google",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    text_color: str = "darkred",
    add_footer: bool = True,
    keep_original: bool = True,
    save_md: bool = False,
):
    """
    Translate a PDF file from source language to target language

    Args:
        input_file: Path to input PDF file
        source_lang: Source language code (e.g. 'en', 'fr')
        target_lang: Target language code (e.g. 'ko', 'ja')
        translator_name: Name of the translator to use (default: "google")
        model: Model name for OpenAI-compatible translators (default: from env)
        api_key: API key for OpenAI-compatible translators (default: from env or "ollama")
        api_base: API base URL for OpenAI-compatible translators (default: from env)
        text_color: Color of translated text (default: "darkred")
        add_footer: Whether to add AI attribution footer (default: True)
        keep_original: Whether to keep original text as optional layer (default: True)
        save_md: Whether to also save a Markdown file of the translated text (default: False)
    """
    if translator_name not in TRANSLATORS:
        raise ValueError(
            f"Unsupported translator: {translator_name}. Available translators: {', '.join(TRANSLATORS.keys())}"
        )

    TranslatorClass = TRANSLATORS[translator_name]

    if translator_name in ("openai", "chatgpt"):
        effective_model = model or get_default_model()
        effective_api_key = api_key or os.environ.get("OPENAI_API_KEY") or "ollama"
        effective_api_base = api_base or os.environ.get("OPENAI_API_BASE")
        translator = TranslatorClass(
            source=source_lang,
            target=target_lang,
            model=effective_model,
            api_key=effective_api_key,
            base_url=effective_api_base,
        )
    else:
        translator = TranslatorClass(source=source_lang, target=target_lang)

    output_file = input_file.rsplit(".", 1)[0] + f"-{target_lang}.pdf"

    doc = pymupdf.open(input_file)
    total_pages = len(doc)
    print(f"Translating {total_pages} pages...")

    output_path = translate_all_pages(
        input_doc=doc,
        translator=translator,
        target_lang=target_lang,
        output_path=output_file,
        text_color=text_color,
        translator_name=translator_name,
        pdf_path=input_file,
        progress_callback=cli_progress_callback,
        use_cache=False,
        add_footer=add_footer,
        keep_original=keep_original,
        save_md=save_md,
    )

    doc.close()
    print()  # New line after progress
    print(f"Translated PDF saved as: {output_path}")
    if save_md:
        md_path = output_path.rsplit(".", 1)[0] + ".md"
        print(f"Translated Markdown saved as: {md_path}")


def _collect_pdf_paths(input_path: str) -> List[str]:
    """Return a list of PDF file paths from the given input path.

    If input_path is a file, returns [input_path].
    If input_path is a directory, returns all .pdf files (non-recursive).
    """
    p = Path(input_path)
    if p.is_file():
        return [str(p)]
    if p.is_dir():
        pdfs = sorted(str(f) for f in p.iterdir() if f.suffix.lower() == ".pdf")
        if not pdfs:
            print(f"No PDF files found in directory: {input_path}")
        return pdfs
    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def main():
    """
    can be invoked like this:
    ```
    # Basic usage with Google translator
    python translator_cli.py --source english --target zh-CN input.pdf

    # Translate all PDFs in a folder
    python translator_cli.py --source english --target zh-CN /path/to/folder

    # With custom color
    python translator_cli.py --source english --target zh-CN --color blue input.pdf

    # Using OpenAI-compatible translator (API key from env, default model)
    export OPENAI_API_KEY=sk-proj-xxxx
    export OPENAI_API_BASE=http://localhost:8080/v1
    python translator_cli.py --source english --translator openai --target fa input.pdf

    # Using a specific model
    python translator_cli.py -s en -t fa -tr openai -m gpt-4o-mini input.pdf

    # Local LLM with Ollama (no real API key needed, defaults to "ollama")
    export OPENAI_API_BASE=http://localhost:11434/v1
    python translator_cli.py -s en -t fa -tr openai -m translategemma:12b input.pdf

    # Explicit API key and base URL
    python translator_cli.py -s en -t fa -tr openai -m gpt-4o-mini \\
        --api-key sk-proj-xxxx --api-base https://api.openai.com/v1 input.pdf

    # Skip footer
    python translator_cli.py -s en -t fa --no-footer input.pdf

    # Keep original text hidden behind optional layer (toggleable in PDF viewers)
    python translator_cli.py -s en -t fa --no-original input.pdf
    ```
    """
    load_dotenv()

    parser = argparse.ArgumentParser(description="Translate PDF documents.")
    parser.add_argument("input_path", help="Input PDF file or folder path")
    parser.add_argument(
        "--source", "-s", default="en", help="Source language code (default: en)"
    )
    parser.add_argument(
        "--target", "-t", default="zh-CN", help="Target language code (default: zh-CN)"
    )
    parser.add_argument(
        "--translator",
        "-tr",
        default="google",
        choices=list(TRANSLATORS.keys()),
        help="Translator to use (default: google)",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="Model name for OpenAI-compatible translators (default: from DEFAULT_MODEL env)",
    )
    parser.add_argument(
        "--api-key",
        "-k",
        default=None,
        help="API key for OpenAI-compatible translators (default: from OPENAI_API_KEY env, or 'ollama' for local LLMs)",
    )
    parser.add_argument(
        "--api-base",
        "-b",
        default=None,
        help="API base URL for OpenAI-compatible translators (default: from OPENAI_API_BASE env)",
    )
    parser.add_argument(
        "--color",
        "-c",
        default="black",
        choices=["darkred", "black", "blue", "darkgreen", "purple"],
        help="Color of translated text (default: darkred)",
    )
    parser.add_argument(
        "--no-footer",
        action="store_true",
        help="Do not add AI attribution footer to each page",
    )
    parser.add_argument(
        "--no-original",
        action="store_true",
        help="Hide original text behind optional layer (toggleable in PDF viewers)",
    )
    parser.add_argument(
        "--md",
        action="store_true",
        help="Also save translated text as a Markdown (.md) file",
    )

    args = parser.parse_args()

    try:
        pdf_files = _collect_pdf_paths(args.input_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        exit(1)

    if not pdf_files:
        exit(0)

    kwargs = dict(
        source_lang=args.source,
        target_lang=args.target,
        translator_name=args.translator,
        model=args.model,
        api_key=args.api_key,
        api_base=args.api_base,
        text_color=args.color,
        add_footer=not args.no_footer,
        keep_original=not args.no_original,
        save_md=args.md,
    )

    for i, pdf_file in enumerate(pdf_files, 1):
        if len(pdf_files) > 1:
            print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file}")
        try:
            translate_pdf(input_file=pdf_file, **kwargs)
        except Exception as e:
            print(f"\nError processing {pdf_file}: {e}")
            if len(pdf_files) == 1:
                exit(1)


if __name__ == "__main__":
    main()
