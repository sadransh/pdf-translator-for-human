import hashlib
import logging
import os
import re
from html import escape as html_escape
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

import pymupdf

from deep_translator.pdf_parser import (
    ParserMode,
    clear_docling_cache,
    extract_pdf_text,
    get_horizontal_lines,
    get_parser_mode,
    is_garbled_text,
    redraw_horizontal_lines,
)
from deep_translator.postprocess import postprocess_translation


def expand_bbox(
    bbox: Tuple[float, float, float, float], expansion_factor: float = 1.15
) -> Tuple[float, float, float, float]:
    """
    Expand bounding box width by a given factor while keeping height unchanged.

    @param bbox: Original bounding box (x0, y0, x1, y1)
    @param expansion_factor: Factor to expand width (default: 1.15 for 15% expansion)
    @return: Expanded bounding box
    """
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    expanded_width = width * expansion_factor
    new_x1 = x0 + expanded_width
    return (x0, y0, new_x1, y1)


def do_rectangles_overlap(
    rect1: Tuple[float, float, float, float],
    rect2: Tuple[float, float, float, float],
) -> bool:
    """
    Check if two rectangles overlap using separating axis theorem.

    @param rect1: First rectangle (x0, y0, x1, y1)
    @param rect2: Second rectangle (x0, y0, x1, y1)
    @return: True if rectangles overlap, False otherwise
    """
    x0_1, y0_1, x1_1, y1_1 = rect1
    x0_2, y0_2, x1_2, y1_2 = rect2

    # Check if rectangles do NOT overlap
    if x1_1 <= x0_2 or x1_2 <= x0_1 or y1_1 <= y0_2 or y1_2 <= y0_1:
        return False
    return True


def adjust_bbox_for_collision(
    bbox: Tuple[float, float, float, float],
    existing_bboxes: List[Tuple[float, float, float, float]],
    min_spacing: float = 8.0,
) -> Tuple[float, float, float, float]:
    """
    Adjust bbox position to avoid collisions with existing bboxes.

    @param bbox: Original bounding box to check
    @param existing_bboxes: List of already placed bboxes
    @param min_spacing: Minimum vertical spacing between bboxes
    @return: Adjusted bbox position
    """
    x0, y0, x1, y1 = bbox

    # Check for collisions and adjust position
    for existing_bbox in existing_bboxes:
        if do_rectangles_overlap(bbox, existing_bbox):
            # Move bbox down by minimum spacing
            y0 = (
                existing_bbox[3] + min_spacing
            )  # existing_bbox[3] is y1 (bottom)
            y1 = y0 + (bbox[3] - bbox[1])  # Maintain same height
            bbox = (x0, y0, x1, y1)

    return bbox


COLOR_MAP = {
    "darkred": (0.8, 0, 0),
    "black": (0, 0, 0),
    "blue": (0, 0, 0.8),
    "darkgreen": (0, 0.5, 0),
    "purple": (0.5, 0, 0.5),
}

# Configuration for bounding box handling
BBOX_EXPANSION_FACTOR = float(os.environ.get("BBOX_EXPANSION_FACTOR", "1.15"))
MIN_SPACING = float(os.environ.get("MIN_SPACING", "8.0"))
COLLISION_DETECTION_ENABLED = (
    os.environ.get("COLLISION_DETECTION_ENABLED", "true").lower() == "true"
)

ProgressCallback = Callable[[int, int, str], None]


def get_cache_dir() -> Path:
    cache_dir = Path(".cached")
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_cache_key(
    doc_info: dict,
    page_num: int,
    translator_name: str,
    target_lang: str,
    text_content: str,
) -> str:
    content_hash = hashlib.md5(text_content.encode("utf-8")).hexdigest()[:8]
    doc_id = f"{doc_info.get('title', '')}_{doc_info.get('author', '')}_{doc_info.get('pagecount', '')}"
    doc_hash = hashlib.md5(doc_id.encode("utf-8")).hexdigest()[:8]
    return f"{doc_hash}_{content_hash}_page{page_num}_{translator_name}_{target_lang}.pdf"


def get_cached_translation(cache_key: str) -> Optional[pymupdf.Document]:
    cache_path = get_cache_dir() / cache_key
    if cache_path.exists():
        try:
            return pymupdf.open(str(cache_path))
        except Exception as e:
            logging.error(f"Error loading cache: {str(e)}")
            return None
    return None


def save_translation_cache(doc: pymupdf.Document, cache_key: str):
    cache_path = get_cache_dir() / cache_key
    doc.save(str(cache_path))


def _is_word_continuation(text: str) -> bool:
    first = text.lstrip()
    if not first:
        return False
    if not first[0].islower():
        return False
    first_token = first.split()[0]
    if re.match(r"^\[?\(?\d+\)?\]?$", first_token):
        return False
    return True


def translate_pdf_pages(
    doc: pymupdf.Document,
    start_page: int,
    num_pages: int,
    translator,
    target_lang: str,
    text_color: str = "darkred",
    translator_name: str = "google",
    pdf_path: Optional[str] = None,
    parser_mode: Optional[ParserMode] = None,
    progress_callback: Optional[ProgressCallback] = None,
    use_cache: bool = True,
    add_footer: bool = True,
    keep_original: bool = True,
    ocg_layer_name: str = "Translation",
    collect_text: bool = False,
) -> Union[
    List[pymupdf.Document],
    Tuple[List[pymupdf.Document], List[Tuple[int, List[str]]]],
]:
    model_name = getattr(translator, "model", None)
    logging.info(
        f"Using translator: {translator_name}, model: {model_name}, source: {translator._source}, target: {translator._target}"
    )

    WHITE = pymupdf.pdfcolor["white"]
    rgb_color = COLOR_MAP.get(text_color.lower(), COLOR_MAP["darkred"])

    translated_pages = []
    page_texts: List[Tuple[int, List[str]]] = []
    total_pages = min(start_page + num_pages, doc.page_count) - start_page
    cache_hits = 0
    page_carryover: Optional[str] = None

    effective_parser_mode = parser_mode or get_parser_mode()

    for i, page_num in enumerate(
        range(start_page, min(start_page + num_pages, doc.page_count))
    ):
        if progress_callback:
            progress_callback(
                i + 1, total_pages, f"Translating page {page_num + 1}..."
            )

        page = doc[page_num]
        text_content = page.get_text("text")

        cache_key = get_cache_key(
            doc.metadata, page_num, translator_name, target_lang, text_content
        )

        cached_doc = get_cached_translation(cache_key) if use_cache else None
        if cached_doc is not None:
            translated_pages.append(cached_doc)
            cache_hits += 1
            logging.info(
                f"Cache hit: Using cached translation for page {page_num + 1}"
            )
            if progress_callback:
                progress_callback(
                    i + 1, total_pages, f"Using cache for page {page_num + 1}"
                )
        else:
            logging.info(f"Cache miss: Translating page {page_num + 1}")

            new_doc = pymupdf.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            page = new_doc[0]

            ocg_trans = None
            ocg_orig = None
            if not keep_original:
                ocg_trans = new_doc.add_ocg(ocg_layer_name, on=True)
                ocg_orig = new_doc.add_ocg("Original", on=False)

            horizontal_lines = get_horizontal_lines(page)

            footnote_separator_y = None
            for _hl in horizontal_lines:
                _rect = _hl.get("rect")
                if _rect is not None:
                    _y = _rect.y0
                    if (
                        footnote_separator_y is None
                        or _y < footnote_separator_y
                    ):
                        footnote_separator_y = _y

            text_blocks = extract_pdf_text(
                page, pdf_path, page_num, effective_parser_mode
            )
            logging.info(
                f"Parser mode: {effective_parser_mode}, extracted {len(text_blocks)} blocks"
            )

            insertions = []
            current_page_translations: List[str] = []

            for bbox, text, font_size in text_blocks:
                original_text = text
                if page_carryover is not None and _is_word_continuation(text):
                    text = page_carryover + text
                    logging.info(
                        f"Hyphen carryover: prepended '{page_carryover}' to next block"
                    )
                    page_carryover = None

                stripped = text.rstrip()
                if stripped.endswith("-"):
                    match = re.search(r"(\S+)-$", stripped)
                    if match:
                        tail = stripped
                        window = tail[-100:]
                        carry_start = None

                        for sep in (".", ",", ";", " ", ")"):
                            idx = window.rfind(sep)
                            if idx != -1:
                                abs_idx = len(tail) - 100 + idx + 1
                                carry_start = max(0, abs_idx)
                                break

                        if carry_start is not None:
                            page_carryover = tail[carry_start:]
                            text = tail[:carry_start]
                        else:
                            page_carryover = match.group(1)
                            text = stripped[: match.start()]

                        logging.info(
                            f"Hyphen carryover saved: '{page_carryover}'"
                        )
                        if not text.strip():
                            if bbox != (0.0, 0.0, 0.0, 0.0):
                                insertions.append(
                                    (bbox, None, None, True, original_text)
                                )
                            continue

                if (
                    footnote_separator_y is not None
                    and bbox != (0.0, 0.0, 0.0, 0.0)
                    and bbox[1] > footnote_separator_y
                ):
                    font_size = 10.0
                if is_garbled_text(text):
                    logging.warning(
                        f"Garbled text detected at page {page_num + 1}, replacing unknown chars"
                    )
                    text = text.replace("\ufffd", "?")

                translated = translator.translate(text)
                translated = str(translated)
                translated = postprocess_translation(translated, target_lang)
                if collect_text:
                    current_page_translations.append(translated)

                is_rtl = False
                try:
                    is_rtl = bool(
                        getattr(
                            translator, "_is_rtl_language", lambda: False
                        )()
                    )
                except Exception:
                    is_rtl = False
                if (
                    not is_rtl
                    and isinstance(target_lang, str)
                    and target_lang.lower().startswith("fa")
                ):
                    is_rtl = True

                if is_rtl:
                    cleaned = translated.replace("\u202b", "").replace(
                        "\u202c", ""
                    )
                    # Use Unicode directional formatting for better RTL handling
                    # RLE (Right-to-Left Embedding) + text + PDF (Pop Directional Formatting)
                    rtl_text = f"\u202b{cleaned}\u202c"
                    escaped = html_escape(rtl_text)
                    rgb_str = (
                        f"rgb({int(rgb_color[0] * 255)}, "
                        f"{int(rgb_color[1] * 255)}, "
                        f"{int(rgb_color[2] * 255)})"
                    )
                    css_style = (
                        f"body {{margin: 0px;}} "
                        f"* {{font-family: Arial, sans-serif; font-size: {font_size}pt; "
                        f"direction: rtl;"
                        f"text-align: justify;"
                        f"color: {rgb_str};}}"
                    )
                    # style="text-align: justify; direction: rtl;"
                    content_to_insert = f"<div dir='rtl'>{escaped}</div>"
                else:
                    content_to_insert = html_escape(translated)
                    css_style = f"* {{font-family: Arial, sans-serif; font-size: {font_size}pt; color: rgb({int(rgb_color[0] * 255)}, {int(rgb_color[1] * 255)}, {int(rgb_color[2] * 255)});}}"

                insertions.append(
                    (bbox, content_to_insert, css_style, False, original_text)
                )

            if keep_original:
                for bbox, content_to_insert, css_style, skip, _ in insertions:
                    if skip:
                        page.draw_rect(bbox, color=None, fill=WHITE)
                    elif bbox != (0.0, 0.0, 0.0, 0.0):
                        page.add_redact_annot(bbox)
                page.apply_redactions()

                # Process insertions with collision detection
                processed_bboxes = []
                for bbox, content_to_insert, css_style, skip, _ in insertions:
                    if skip:
                        continue

                    # Expand bbox width if enabled
                    if BBOX_EXPANSION_FACTOR and BBOX_EXPANSION_FACTOR != 1.0:
                        bbox = expand_bbox(bbox, BBOX_EXPANSION_FACTOR)

                    # Adjust bbox for collisions if enabled
                    if COLLISION_DETECTION_ENABLED:
                        bbox = adjust_bbox_for_collision(
                            bbox, processed_bboxes, MIN_SPACING
                        )

                    processed_bboxes.append(bbox)

                    if bbox == (0.0, 0.0, 0.0, 0.0):
                        page.insert_htmlbox(
                            page.rect,
                            content_to_insert,
                            css=css_style,
                            oc=ocg_trans,
                        )
                    else:
                        page.draw_rect(bbox, color=None, fill=WHITE)
                        page.insert_htmlbox(
                            bbox,
                            content_to_insert,
                            css=css_style,
                            oc=ocg_trans,
                        )

                    # Expand bbox width if enabled
                    if BBOX_EXPANSION_FACTOR and BBOX_EXPANSION_FACTOR != 1.0:
                        bbox = expand_bbox(bbox, BBOX_EXPANSION_FACTOR)

                    # Adjust bbox for collisions if enabled
                    if COLLISION_DETECTION_ENABLED:
                        bbox = adjust_bbox_for_collision(
                            bbox, processed_bboxes, MIN_SPACING
                        )

                    processed_bboxes.append(bbox)

                    if bbox == (0.0, 0.0, 0.0, 0.0):
                        page.insert_htmlbox(
                            page.rect,
                            content_to_insert,
                            css=css_style,
                            oc=ocg_trans,
                        )
                    else:
                        page.draw_rect(bbox, color=None, fill=WHITE)
                        page.insert_htmlbox(
                            bbox,
                            content_to_insert,
                            css=css_style,
                            oc=ocg_trans,
                        )
            else:
                # Redact base-stream text first so the original PDF text is
                # fully removed from the text layer before inserting the
                # translation.  insert_htmlbox with oc= only controls
                # visibility; text inside any content stream is always
                # extractable, so we must redact before any inserts.
                for bbox, _, _, skip, _ in insertions:
                    if not skip and bbox != (0.0, 0.0, 0.0, 0.0):
                        page.add_redact_annot(bbox)
                page.apply_redactions()

                for (
                    bbox,
                    content_to_insert,
                    css_style,
                    skip,
                    _original_text,
                ) in insertions:
                    if skip:
                        page.draw_rect(bbox, color=None, fill=WHITE)
                        continue
                    if bbox == (0.0, 0.0, 0.0, 0.0):
                        page.insert_htmlbox(
                            page.rect,
                            content_to_insert,
                            css=css_style,
                            oc=ocg_trans,
                        )
                    else:
                        page.draw_rect(bbox, color=None, fill=WHITE)
                        page.insert_htmlbox(
                            bbox,
                            content_to_insert,
                            css=css_style,
                            oc=ocg_trans,
                        )

            last_body_text_y = None

            if footnote_separator_y is not None:
                for bbox, text, font_size in text_blocks:
                    if (
                        bbox != (0.0, 0.0, 0.0, 0.0)
                        and bbox[3] < footnote_separator_y
                    ):
                        if (
                            last_body_text_y is None
                            or bbox[3] > last_body_text_y
                        ):
                            last_body_text_y = bbox[3]

            if last_body_text_y is not None:
                new_separator_y = last_body_text_y + 3
                # shape = page.new_shape()
                # shape.draw_line(
                #     pymupdf.Point(50, new_separator_y),
                #     pymupdf.Point(page.rect.width - 50, new_separator_y),
                # )
                # shape.finish(color=(0, 0, 0), width=0.5)
                # shape.commit()
                logging.info(
                    f"Drew footnote separator at y={new_separator_y} (below last body text at y={last_body_text_y})"
                )
            else:
                redraw_horizontal_lines(page, horizontal_lines)

            if add_footer:
                model_name = getattr(translator, "model", "AI")
                if model_name is None:
                    model_name = translator_name
                footer_text = f"AI translation powered by {model_name}. AI translation may include mistakes."
                footer_rect = pymupdf.Rect(
                    20,
                    page.rect.height - 30,
                    page.rect.width - 20,
                    page.rect.height - 10,
                )
                if not keep_original:
                    page.insert_htmlbox(
                        footer_rect,
                        html_escape(footer_text),
                        css="* {text-align:center; font-family: Arial, sans-serif; font-size: 8pt; color: rgb(150, 150, 150);}",
                        oc=ocg_trans,
                    )
                else:
                    page.insert_htmlbox(
                        footer_rect,
                        html_escape(footer_text),
                        css="* {text-align:center; font-family: Arial, sans-serif; font-size: 8pt; color: rgb(150, 150, 150);}",
                    )

            if use_cache:
                save_translation_cache(new_doc, cache_key)
            translated_pages.append(new_doc)
            if collect_text:
                page_texts.append((page_num + 1, current_page_translations))
            logging.info(f"Translation complete for page {page_num + 1}")

    if pdf_path:
        clear_docling_cache(pdf_path)

    if collect_text:
        return translated_pages, page_texts
    return translated_pages


def translate_all_pages(
    input_doc: pymupdf.Document,
    translator,
    target_lang: str,
    output_path: str,
    text_color: str = "darkred",
    translator_name: str = "google",
    pdf_path: Optional[str] = None,
    parser_mode: Optional[ParserMode] = None,
    progress_callback: Optional[ProgressCallback] = None,
    use_cache: bool = True,
    add_footer: bool = True,
    keep_original: bool = True,
    ocg_layer_name: str = "Translation",
    save_md: bool = False,
) -> str:
    model_name = getattr(translator, "model", None)
    logging.info(
        f"Starting full document translation with: {translator_name}, model: {model_name}"
    )
    logging.info(
        f"Translator settings - source: {translator._source}, target: {translator._target}"
    )

    total_pages = input_doc.page_count

    result = translate_pdf_pages(
        input_doc,
        0,
        total_pages,
        translator,
        target_lang,
        text_color=text_color,
        translator_name=translator_name,
        pdf_path=pdf_path,
        parser_mode=parser_mode,
        progress_callback=progress_callback,
        use_cache=use_cache,
        add_footer=add_footer,
        keep_original=keep_original,
        ocg_layer_name=ocg_layer_name,
        collect_text=save_md,
    )

    if save_md:
        translated_pages, page_texts = result
    else:
        translated_pages = result
        page_texts = None

    output_doc = pymupdf.open()
    for trans_doc in translated_pages:
        output_doc.insert_pdf(trans_doc)

    output_doc.save(
        output_path,
        garbage=4,
        deflate=True,
        clean=True,
    )
    output_doc.close()

    if save_md and page_texts:
        md_path = output_path.rsplit(".", 1)[0] + ".md"
        md_lines: List[str] = []
        for page_num, translations in page_texts:
            md_lines.append(f"## Page {page_num}\n")
            for block in translations:
                md_lines.append(block)
                md_lines.append("")
            md_lines.append("---\n")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
        logging.info(f"Markdown saved as: {md_path}")

    return output_path


def get_page_image(page, scale: float = 2) -> bytes:
    zoom = scale
    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(
        matrix=mat,
        alpha=False,
        colorspace="rgb",
    )
    return pix.tobytes()
