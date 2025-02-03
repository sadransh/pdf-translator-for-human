import argparse
import pymupdf
from deep_translator import (
    GoogleTranslator,
    ChatGptTranslator,
)

# Map of supported translators
TRANSLATORS = {
    'google': GoogleTranslator,
    'chatgpt': ChatGptTranslator,
}

def translate_pdf(input_file: str, source_lang: str, target_lang: str, layer: str = "Text", 
                 translator_name: str = "google", text_color: str = "darkred", keep_original: bool = True):
    """
    Translate a PDF file from source language to target language
    
    Args:
        input_file: Path to input PDF file
        source_lang: Source language code (e.g. 'en', 'fr')
        target_lang: Target language code (e.g. 'ko', 'ja') 
        layer: Name of the OCG layer (default: "Text")
        translator_name: Name of the translator to use (default: "google")
        text_color: Color of translated text (default: "darkred")
        keep_original: Whether to keep original text visible (default: True)
    """
    # Define colors
    WHITE = pymupdf.pdfcolor["white"]
    
    # Color mapping
    COLOR_MAP = {
        "darkred": (0.8, 0, 0),
        "black": (0, 0, 0),
        "blue": (0, 0, 0.8),
        "darkgreen": (0, 0.5, 0),
        "purple": (0.5, 0, 0.5),
    }
    
    # Get RGB color values, default to darkred if color not found
    rgb_color = COLOR_MAP.get(text_color.lower(), COLOR_MAP["darkred"])

    # This flag ensures that text will be dehyphenated after extraction.
    textflags = pymupdf.TEXT_DEHYPHENATE

    # Get the translator class
    if translator_name not in TRANSLATORS:
        raise ValueError(f"Unsupported translator: {translator_name}. Available translators: {', '.join(TRANSLATORS.keys())}")
    
    TranslatorClass = TRANSLATORS[translator_name]
    
    # Configure the translator
    translator = TranslatorClass(source=source_lang, target=target_lang)

    # Generate output filename
    output_file = input_file.rsplit('.', 1)[0] + f'-{target_lang}.pdf'

    # Open the document
    doc = pymupdf.open(input_file)

    # Define an Optional Content layer for translation
    ocg_trans = doc.add_ocg(layer, on=True)
    
    # If not keeping original, create a layer for original text and hide it
    if not keep_original:
        ocg_orig = doc.add_ocg("Original", on=False)

    # Iterate over all pages
    for page in doc:
        # Extract text grouped like lines in a paragraph.
        blocks = page.get_text("blocks", flags=textflags)

        # Every block of text is contained in a rectangle ("bbox")
        for block in blocks:
            bbox = block[:4]  # area containing the text
            text = block[4]  # the text of this block

            # Invoke the actual translation
            translated = translator.translate(text)

            if not keep_original:
                # Move original text to hidden layer
                page.insert_htmlbox(
                    bbox,
                    text,
                    css="* {font-family: sans-serif;}",
                    oc=ocg_orig
                )
                # Clear original text area in base layer
                page.draw_rect(bbox, color=None, fill=WHITE)
            else:
                # Cover the original text only in translation layer
                page.draw_rect(bbox, color=None, fill=WHITE, oc=ocg_trans)

            # Write the translated text in specified color
            page.insert_htmlbox(
                bbox,
                translated,
                css=f"* {{font-family: sans-serif; color: rgb({int(rgb_color[0]*255)}, {int(rgb_color[1]*255)}, {int(rgb_color[2]*255)});}}",
                oc=ocg_trans
            )

    doc.subset_fonts()
    doc.ez_save(output_file)
    print(f"Translated PDF saved as: {output_file}")

def main():
    """
    can be invoked like this:
    ```
    # Basic usage
    python translator_cli.py --source english --target zh-CN input.pdf

    # With custom color and hiding original text
    python translator_cli.py --source english --target zh-CN --color blue --no-original input.pdf

    # Using ChatGPT translator
    export OPENAI_API_KEY=sk-proj-xxxx
    export OPENAI_API_BASE=https://api.xxxx.com/v1
    export OPENAI_API_BASE=http://localhost:8080/v1 #  for local llm api
    export OPENAI_MODEL=default_model
    
    python translator_cli.py --source english --translator chatgpt --target zh-CN input.pdf

    # do not keep original text as an optional layer:
    python translator_cli.py --source english --translator chatgpt --target zh-CN --no-original input.pdf
    
    ```

    The translated content is an optional content layer in the new PDF file. 
    The optional layer can be hidden in Acrobat PDF Reader and Foxit Reader.
    """
    
    parser = argparse.ArgumentParser(description='Translate PDF documents.')
    parser.add_argument('input_file', help='Input PDF file path')
    parser.add_argument('--source', '-s', default='en',
                       help='Source language code (default: en)')
    parser.add_argument('--target', '-t', default='zh-CN',
                       help='Target language code (default: zh-CN)')
    parser.add_argument('--layer', '-l', default='Text',
                       help='Name of the OCG layer (default: Text)')
    parser.add_argument('--translator', '-tr', default='google',
                       choices=list(TRANSLATORS.keys()),
                       help='Translator to use (default: google)')
    parser.add_argument('--color', '-c', default='darkred',
                       choices=['darkred', 'black', 'blue', 'darkgreen', 'purple'],
                       help='Color of translated text (default: darkred)')
    parser.add_argument('--no-original', action='store_true',
                       help='Do not keep original text in base layer (default: False)')

    args = parser.parse_args()

    try:
        translate_pdf(args.input_file, args.source, args.target, args.layer, 
                     args.translator, args.color, not args.no_original)
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()