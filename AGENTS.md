# AGENTS.md - Agentic Coding Guidelines

## Project Overview

`deep-translator` is a Python library for translating text between languages using multiple translation services (Google, DeepL, Microsoft, ChatGPT/OpenAI, etc.). Also includes a Streamlit-based PDF translation application (`app.py`).

## Build, Lint, and Test Commands

### Running Tests

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_google.py

# Run a single test function
pytest tests/test_google.py::test_content

# Run tests with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "test_google"
```

### Code Formatting

```bash
# Format code with black and isort
make format

# Or run individually:
isort .
black deep_translator tests
```

### Linting

```bash
# Run pre-commit checks (recommended)
pre-commit run --all-files

# Run flake8 only
flake8 deep_translator tests --max-line-length=109

# Run pycln (remove unused imports)
pycln --config=pyproject.toml
```

### Running the Application

```bash
# Run the Streamlit PDF translator app
streamlit run app.py

# Run with command line options
python app.py --translator openai --model translategemma:12b

# Run the CLI
deep-translator  # or: dt
```

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or with poetry
poetry install

# Install with all extras
poetry install --all-extras
```

## Code Style Guidelines

### Formatting

- **Line length**: 79 characters (black default), 109 characters max (flake8)
- Use **black** for code formatting
- Use **isort** for import sorting (profile: black, multi_line_output: 3)
- Use **pycln** to remove unused imports
- Trailing commas enabled

### Import Conventions

```python
# Standard library first
import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple, Union

# Third-party packages
import pymupdf
import streamlit as st
from dotenv import load_dotenv

# Local imports (use explicit imports, not relative)
from deep_translator.base import BaseTranslator
from deep_translator.constants import GOOGLE_LANGUAGES_TO_CODES
from deep_translator.exceptions import ApiKeyException
```

### Type Hints

- Use type hints for function arguments and return values
- Use `Optional[X]` instead of `X | None` (Python 3.7 support)
- Use `Union[X, Y]` for multiple types
- Use `List[X]`, `Dict[K, V]` instead of `list[X]`, `dict[K, V]` (Python 3.7 support)

```python
def translate(self, text: str, **kwargs) -> str:
    ...

def extract_pdf_text(
    page,
    pdf_path: Optional[str],
    page_num: int,
    mode: Optional[ParserMode] = None,
) -> List[Tuple[Tuple[float, float, float, float], str]]:
    ...
```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `GoogleTranslator`, `OpenAICompatibleTranslator`)
- **Functions/methods**: `snake_case` (e.g., `get_supported_languages`, `extract_text_docling`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `GOOGLE_LANGUAGES_TO_CODES`, `TEXT_EXTRACTION_FLAGS`)
- **Private methods**: `_leading_underscore` (e.g., `_map_language_to_code`, `_get_language_name`)
- **Test functions**: `snake_case` starting with `test_` (e.g., `test_content`, `test_google_translator`)
- **Enum classes**: `PascalCase` with `UPPER_SNAKE_CASE` values (e.g., `ParserMode.LEGACY`)

### Error Handling

- Use custom exceptions from `deep_translator.exceptions`
- Raise specific exceptions with meaningful messages
- Log errors with `logging.error()` or `logging.warning()`
- Use try/except with specific exception types

```python
from deep_translator.exceptions import ApiKeyException, InvalidSourceOrTargetLanguage

if not api_key:
    raise ApiKeyException(env_var=OPEN_AI_ENV_VAR)

try:
    result = converter.convert(pdf_path)
except Exception as e:
    logging.error(f"Docling extraction failed: {e}")
    return extract_text_legacy(page)
```

### Docstrings

- Use Google-style docstrings
- Keep line length under 79 characters
- Include parameter types and return types

```python
def translate(self, text: str, **kwargs) -> str:
    """
    Translate text using the configured translator.

    @param text: text to translate
    @return: translated text
    """
```

### Class Structure

Follow the pattern in `deep_translator/base.py`:

```python
class BaseTranslator(ABC):
    """Abstract class that serves as a base translator."""

    def __init__(
        self,
        base_url: str = None,
        languages: dict = GOOGLE_LANGUAGES_TO_CODES,
        source: str = "auto",
        target: str = "en",
    ):
        self._source = source
        self._target = target

    @property
    def source(self):
        return self._source

    @abstractmethod
    def translate(self, text: str, **kwargs) -> str:
        """Translate text."""
        ...
```

## File Organization

```
deep_translator/
├── __init__.py          # Exports public API
├── base.py              # BaseTranslator abstract class
├── constants.py         # Constants and language mappings
├── exceptions.py        # Custom exception classes
├── chatgpt.py           # ChatGPT/OpenAI translator
├── openai_compatible.py # OpenAI-compatible translator with retry
├── pdf_parser.py        # PDF text extraction (legacy/docling/hybrid)
├── postprocess.py       # Translation post-processing (digit/punctuation conversion)
├── models_config.py     # Model definitions and configuration
├── prompts/             # Prompt templates for different models
│   ├── __init__.py      # Prompt loader with auto-detection
│   ├── default.py       # Default prompt template
│   └── translategemma.py # TranslateGemma-specific prompt
├── google.py            # GoogleTranslator
├── deepl.py             # DeeplTranslator
└── ...                  # Other translators
```

## Environment Variables

Key environment variables (set in `.env`):

```bash
OPENAI_API_KEY=your_key
OPENAI_API_BASE=http://localhost:11434/v1  # For local LLM
OPENAI_MODEL=translategemma:12b
DEFAULT_MODEL=translategemma:12b
PDF_PARSER_MODE=legacyocr  # Options: legacy, docling, hybrid, legacyocr
```

### PDF Parser Modes

- `legacy` - PyMuPDF only (fastest, may have encoding issues with some PDFs)
- `docling` - AI-based OCR using docling package (best quality, requires docling)
- `hybrid` - Try legacy first, fallback to docling if garbled text detected
- `legacyocr` - Try legacy first, fallback to PyMuPDF's built-in Tesseract OCR if garbled text detected (requires tesseract binary)

## Adding New Prompt Templates

Create a new file in `deep_translator/prompts/`:

```python
# deep_translator/prompts/my_model.py
TEMPLATE = """Your prompt with {text}, {source_lang}, {target_lang}..."""

def build_prompt(text: str, source_lang: str, source_code: str, 
                 target_lang: str, target_code: str) -> str:
    return TEMPLATE.format(
        text=text, 
        source_lang=source_lang,
        source_code=source_code,
        target_lang=target_lang, 
        target_code=target_code
    )
```

## Translation Post-Processing

The `postprocess.py` module handles post-translation transformations:

- **Digit conversion**: Western Arabic digits → target language script (e.g., 4 → ۴ for Persian)
- **Punctuation conversion**: Language-specific punctuation (e.g., , → ، for Persian/Arabic)
- **Newline preservation**: Maintains line breaks in translated text

Supported languages:
- Persian (`fa`): Digits and punctuation
- Arabic (`ar`): Digits and punctuation

```python
from deep_translator.postprocess import postprocess_translation

translated = "This is page 4, section 5?"
processed = postprocess_translation(translated, "fa")
# Result: "This is page ۴، section ۵؟"
```

## Testing Guidelines

- Place tests in `tests/` directory
- Test file naming: `test_<module_name>.py`
- Use pytest fixtures for common setup
- Mock external API calls where appropriate

```python
@pytest.fixture
def google_translator():
    return GoogleTranslator(target="en")

def test_content(google_translator):
    assert google_translator.translate(text="좋은") == "good"
```

## Pre-commit Hooks

Run `pre-commit install` to set up local hooks. Hooks include:
- black, flake8, isort, pycln
- check-toml, check-yaml
- trailing-whitespace, end-of-file-fixer
- python-check-blanket-noqa, python-no-eval

## Git Conventions

- Use meaningful commit messages
- Run `make format` before committing
- Ensure pre-commit hooks pass
- Run tests before pushing
