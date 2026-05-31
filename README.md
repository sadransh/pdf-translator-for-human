# PDF Translator for Human

**Fork of [davideuler/pdf-translator-for-human](https://github.com/davideuler/pdf-translator-for-human)** — a side-by-side PDF reader/translator powered by local LLMs, ChatGPT, or Google Translate. This fork adds full RTL language support, multi-strategy PDF parsing, pluggable translation prompts, post-processing pipelines, and more.

## New Features & Changes

This fork extends the upstream project with the following additions:

- **RTL Language Support** — Full right-to-left rendering for Persian, Arabic, Hebrew, and Urdu using Unicode RLE/PDF markers and HTML `dir='rtl'` formatting
- **Persian/Farsi as a first-class target language** — Added throughout the app, language mappings, and UI
- **Post-Processing Pipeline** — Automatic digit conversion (0-9 → Persian/Arabic numerals) and punctuation conversion (`,` → `،`, `?` → `؟`)
- **Multi-Strategy PDF Parsing** — 5 extraction modes (legacy, docling, hybrid, legacy+Tesseract OCR, legacy+easyOCR) with automatic garbled text detection
- **Pluggable Prompt System** — Model-specific prompt templates with auto-detection; add your own in `deep_translator/prompts/`
- **Model Configuration Registry** — Centralized model list with display names, env-var customization, and UI dropdown selector
- **Bbox Collision Detection** — Prevents translated text blocks from overlapping, with adjustable expansion and spacing
- **Hyphen Carryover** — Handles words hyphenated across page boundaries by carrying them to the next block
- **Footnote Handling** — Detects footnote separators, adjusts font size for footnote text, and redraws separator lines
- **Translation Caching** — Page-level MD5-based cache in `.cached/` to skip re-translation of already-translated pages
- **Markdown Export** — Optional `.md` sidecar file with all translated text organized by page
- **OCG Layer Support** — Original text preserved as a toggleable PDF layer (show/hide in PDF viewers)
- **AI Attribution Footers** — Each page gets an "AI translation powered by [model]" footer
- **PDF Splitting Utility** — `split_pdf.py` CLI tool for splitting PDFs into chapters by page ranges
- **CLI Batch Processing** — Process entire directories of PDFs with progress reporting
- **Refactored core** — PDF translation logic extracted from `app.py` into `deep_translator/pdf_translator.py` for reuse in both web UI and CLI
| **Bbox Collision Detection** | Prevents translated text blocks from overlapping with adjustable expansion and spacing |
| **Hyphen Carryover** | Handles words hyphenated across page boundaries, carrying them to the next block |
| **Footnote Handling** | Detects footnote separators, adjusts font size for footnote text, and redraws separator lines |
| **Translation Caching** | Page-level MD5-based cache in `.cached/` directory — skip re-translation of already-translated pages |
| **Markdown Export** | Optional `.md` sidecar file with all translated text organized by page |
| **OCG Layer Support** | Original text can be preserved as a toggleable PDF layer (on/off in PDF viewers) |
| **AI Attribution Footers** | Each page gets an "AI translation powered by [model]" footer |
| **PDF Splitting Utility** | `split_pdf.py` CLI tool for splitting PDFs into chapters by page ranges |
| **CLI Batch Processing** | Process entire directories of PDFs with progress reporting |
| **Persian/Farsi Support** | Added as a first-class target language throughout the app and language mappings |

## Snapshot

![PDF Translator for Human](saved-demo.jpg)


---
rest is  from original read me ... not updated with changes from this repo

## Huggingface Space

https://huggingface.co/spaces/davideuler/pdf-translator-for-human

## Supported Translators and LLMs

- **Google Translator** (no API key required, free)
- **Local LLMs** via Ollama, llama.cpp, mlx_lm, etc.
- **ChatGPT / OpenAI**
- **DeepSeek** (OpenAI Compatible endpoint at `https://api.deepseek.com/v1`)
- **Qwen** (OpenAI Compatible endpoint)
- **Other OpenAI Compatible LLMs** (GLM, Moonshot, etc.)

### Predefined Models

The application ships with a curated list of models. Set `AVAILABLE_MODELS` env var to add custom ones:

| Model | Display Name |
|---|---|
| `gpt-4o-mini` | GPT-4o Mini (OpenAI - requires testing) |
| `gpt-4o` | GPT-4o (OpenAI - requires testing) |
| `gpt-4-turbo` | GPT-4 Turbo (OpenAI - requires testing) |
| `translategemma:12b` | TranslateGemma 12B (ollama local) |
| `llama3.1:8b` | Llama 3.1 8B (ollama local) |
| `qwen2.5:7b` | Qwen 2.5 7B (ollama local) |
| ... and more | |

## Quick Start

### Installation

```bash
pip install -r requirements.txt
# Or with poetry:
poetry install
```

### Run the Web Application -- not fully optimized

```bash
./run_translator_web.sh
# Or directly:
streamlit run app.py
```

### Run the CLI (recommended and tested at large scale)

#example to process a whole list of pdfs to persian with translategemma in both .md and .pdf format
```bash
python translator_cli.py  ../raw\ pdfs --source en --target fa --translator chatgpt --model translategemma:27b --no-original --md
```

```bash
# Translate a single PDF (Google Translate):
python translator_cli.py input.pdf --source en --target fa

# Translate with a local LLM:
python translator_cli.py input.pdf --source en --target fa \
  --translator openai \
  --model translategemma:12b \
  --api-base http://localhost:11434/v1

# Batch translate a directory:
python translator_cli.py /path/to/pdfs/ --source en --target fa --translator openai

# Enable markdown export:
python translator_cli.py input.pdf --source en --target fa --md

# No footer, no original layer:
python translator_cli.py input.pdf --source en --target fa --no-footer --no-original
```

### Split a PDF into Chapters

```bash
# Create a mapping file (pages.txt):
#   intro:1-15
#   chapter1:16-45
#   appendix:46-50

python split_pdf.py book.pdf pages.txt --prefix "ch-" --zero-padded
```

## PDF Parser Modes

Set `PDF_PARSER_MODE` environment variable or configure in the web UI:

| Mode | Description |
|---|---|
| `legacy` | PyMuPDF text extraction (fastest, may have encoding issues) |
| `docling` | AI-based OCR using docling (best quality, requires `docling` package) |
| `hybrid` | Try legacy first, fallback to docling if garbled text detected |
| `legacyocr` | Legacy + PyMuPDF's built-in Tesseract OCR fallback |
| `easyocr` | Legacy + easyOCR fallback for challenging PDFs |

```bash
# Use docling mode (default):
export PDF_PARSER_MODE=docling

# Use legacy mode (fastest):
export PDF_PARSER_MODE=legacy
```

## RTL Language Support

When translating to Persian, Arabic, Hebrew, or Urdu, the application automatically:

1. **Wraps translated text with Unicode RLE/PDF markers** (`U+202B` / `U+202C`) for proper bidirectional rendering
2. **Applies `dir='rtl'` HTML formatting** in PDF text layers
3. **Converts digits** — `4` becomes `۴` in Persian, `٤` in Arabic
4. **Converts punctuation** — `,` becomes `،`, `?` becomes `؟`
5. **Preserves newlines** in translated text

```python
from deep_translator.postprocess import postprocess_translation

result = postprocess_translation("Page 4, section 5?", "fa")
# "Page ۴، section ۵؟"
```

## Pluggable Prompt Templates

Create model-specific prompts by adding a file in `deep_translator/prompts/`:

```python
# deep_translator/prompts/my_model.py
TEMPLATE = """Translate the following text to {target_lang}.

Source text: {text}
"""

def build_prompt(text, source_lang, source_code, target_lang, target_code):
    return TEMPLATE.format(
        text=text,
        source_lang=source_lang,
        source_code=source_code,
        target_lang=target_lang,
        target_code=target_code,
    )
```

Models are matched by name pattern. The `default.py` template is used as a fallback.

## Translation Caching

Translated pages are automatically cached in `.cached/` using MD5 hashes of the source text. Re-translating the same page skips the LLM call and loads from cache. Delete the `.cached/` directory to force re-translation.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | API key for OpenAI-compatible services | `ollama` |
| `OPENAI_API_BASE` | Base URL for OpenAI-compatible services | `http://localhost:8080/v1` |
| `OPENAI_MODEL` | Default model name | `translategemma:12b` |
| `DEFAULT_MODEL` | Override default model | — |
| `AVAILABLE_MODELS` | Comma-separated list of additional models | — |
| `PDF_PARSER_MODE` | PDF text extraction mode | `docling` |
| `BBOX_EXPANSION_FACTOR` | Bbox width expansion factor | `1.15` |
| `MIN_SPACING` | Minimum spacing between translated blocks | `8.0` |
| `COLLISION_DETECTION_ENABLED` | Enable/disable collision detection | `true` |

## Local LLM Deployment

### Option 1: mlx_lm (Mac Silicon)

```bash
git clone https://huggingface.co/mlx-community/aya-expanse-8b-4bit
pip install mlx_lm
mlx_lm.server --model ./aya-expanse-8b-4bit --port 8080
```

### Option 2: llama.cpp (CPU/GPU/Mac)

```bash
wget https://hf-mirror.co/bartowski/aya-expanse-32b-GGUF/resolve/main/aya-expanse-32b-Q4_K_M.gguf
# Build and run llama.cpp:
./llama-server -m aya-expanse-32b-Q4_K_M.gguf --port 8080
```

### Option 3: Ollama / vLLM / LMStudio

See the official documentation for your preferred inference tool.

### Option 4: OpenAI-Compatible API

```bash
# DeepSeek
export OPENAI_MODEL=deepseek-chat
export OPENAI_API_BASE=https://api.deepseek.com/v1
export OPENAI_API_KEY=sk-xxxx

# Moonshot
export OPENAI_MODEL=moonshot-v1-8k
export OPENAI_API_BASE=https://api.moonshot.cn/v1
export OPENAI_API_KEY=sk-xxxx
```

## Project Structure

```
pdf-translator-for-human/
├── app.py                          # Streamlit web application
├── translator_cli.py               # CLI interface
├── split_pdf.py                    # PDF chapter splitting utility
├── deep_translator/
│   ├── __init__.py                 # Public API exports
│   ├── base.py                     # BaseTranslator with RTL support
│   ├── chatgpt.py                  # ChatGPT/OpenAI translator
│   ├── openai_compatible.py        # OpenAI-compatible translator
│   ├── models_config.py            # Model registry & configuration
│   ├── pdf_parser.py               # Multi-strategy PDF extraction
│   ├── pdf_translator.py           # Core translation engine
│   ├── postprocess.py              # Digit/punctuation conversion
│   ├── prompts/                    # Pluggable prompt templates
│   │   ├── __init__.py             # Auto-detection & loader
│   │   ├── default.py              # Default prompt template
│   │   └── translategemma.py       # TranslateGemma prompt
│   ├── constants.py                # Language codes (incl. Persian/Farsi)
│   └── ...                         # Other translators (Google, DeepL, etc.)
├── requirements.txt
├── AGENTS.md                       # AI coding agent guidelines
└── README.md
```

## Acknowledgements

- [deep-translator](https://github.com/nidhaloff/deep-translator) — the original translation library this project is built on
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF manipulation
- [docling](https://github.com/DS4SD/docling) — AI-based PDF parsing

Pull Requests are welcome.