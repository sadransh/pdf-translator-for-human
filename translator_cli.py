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

def translate_pdf(input_file: str, source_lang: str, target_lang: str, layer: str = "Korean", translator_name: str = "google"):
    """
    Translate a PDF file from source language to target language
    
    Args:
        input_file: Path to input PDF file
        source_lang: Source language code (e.g. 'en', 'fr')
        target_lang: Target language code (e.g. 'ko', 'ja') 
        layer: Name of the OCG layer (default: "Korean")
        translator_name: Name of the translator to use (default: "google")
    """
    # Define color "white"
    WHITE = pymupdf.pdfcolor["white"]

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

    # Define an Optional Content layer in the document.
    # Activate it by default.
    ocg_xref = doc.add_ocg(layer, on=True)

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

            # Cover the source text with a white rectangle.
            page.draw_rect(bbox, color=None, fill=WHITE, oc=ocg_xref)

            # Write the translated text into the original rectangle
            page.insert_htmlbox(
                bbox, translated, css="* {font-family: sans-serif;}", oc=ocg_xref
            )

    doc.subset_fonts()
    doc.ez_save(output_file)
    print(f"Translated PDF saved as: {output_file}")

def main():
    """
      can be invoked like this:
      python translator_cli.py --source english --target zh-CN "/Users/david/Downloads/Level_up_coding_by_ai.pdf"
    """
    
    parser = argparse.ArgumentParser(description='Translate PDF documents.')
    parser.add_argument('input_file', help='Input PDF file path')
    parser.add_argument('--source', '-s', default='en',
                       help='Source language code (default: en)')
    parser.add_argument('--target', '-t', default='ko',
                       help='Target language code (default: ko)')
    parser.add_argument('--layer', '-l', default='Korean',
                       help='Name of the OCG layer (default: Korean)')
    parser.add_argument('--translator', '-tr', default='google',
                       choices=list(TRANSLATORS.keys()),
                       help='Translator to use (default: google)')

    args = parser.parse_args()

    try:
        translate_pdf(args.input_file, args.source, args.target, args.layer, args.translator)
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()