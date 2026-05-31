__copyright__ = "Copyright (C) 2020 Nidhal Baccouri"

import logging
import os
from enum import Enum
from typing import List, Optional, Tuple

import pymupdf
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    filename="application.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)-5s %(lineno)d %(filename)s:%(funcName)s - %(message)s",
)


class ParserMode(str, Enum):
    LEGACY = "legacy"
    DOCLING = "docling"
    HYBRID = "hybrid"
    LEGACYOCR = "legacyocr"
    EASYOCR = "easyocr"


PDF_PARSER_MODE = os.environ.get("PDF_PARSER_MODE", "docling").lower()
TEXT_EXTRACTION_FLAGS = (
    pymupdf.TEXT_PRESERVE_WHITESPACE
    | pymupdf.TEXT_PRESERVE_LIGATURES
    | pymupdf.TEXT_MEDIABOX_CLIP
    | pymupdf.TEXT_DEHYPHENATE
)


def get_parser_mode() -> ParserMode:
    mode = PDF_PARSER_MODE
    if mode == "legacy":
        return ParserMode.LEGACY
    elif mode == "hybrid":
        return ParserMode.HYBRID
    elif mode == "legacyocr":
        return ParserMode.LEGACYOCR
    elif mode == "easyocr":
        return ParserMode.EASYOCR
    else:
        return ParserMode.DOCLING


def is_garbled_text(text: str, threshold: float = 0.1) -> bool:
    if not text or not text.strip():
        return False
    if "��" in text.strip() or "????" in text.strip():
        return True
    replacement_chars = sum(
        1 for c in text if ord(c) == 0xFFFD or c == "\ufffd" or c == "�"
    )
    total_chars = len(text.strip())
    if total_chars == 0:
        return False
    bad_ratio = replacement_chars / total_chars
    return bad_ratio > threshold


DEFAULT_FONT_SIZE = 11.0


def extract_text_legacy(
    page,
) -> List[Tuple[Tuple[float, float, float, float], str, float]]:
    blocks = page.get_text("dict", flags=TEXT_EXTRACTION_FLAGS).get("blocks", [])
    result: List[Tuple[Tuple[float, float, float, float], str, float]] = []

    for block in blocks:
        if block.get("type", 1) != 0:
            continue

        bbox = tuple(block.get("bbox", (0, 0, 0, 0)))
        lines = block.get("lines", [])

        text_parts = []
        sizes = []

        for line in lines:
            for span in line.get("spans", []):
                text_parts.append(span.get("text", ""))
                size = span.get("size")
                if size and size > 0:
                    sizes.append(size)

        text = "".join(text_parts)
        avg_size = sum(sizes) / len(sizes) if sizes else DEFAULT_FONT_SIZE
        result.append((bbox, text, avg_size))

    return result


def extract_text_ocr(
    page, dpi: int = 300, use_easyocr: bool = False
) -> List[Tuple[Tuple[float, float, float, float], str, float]]:
    """
    Extract text using OCR.
    Requires either tesseract (if use_easyocr=False) or easyocr (if use_easyocr=True).

    @param page: pymupdf page object
    @param dpi: resolution for OCR
    @param use_easyocr: if True, use easyOCR; otherwise use PyMuPDF's Tesseract
    @return: list of (bbox, text, font_size) tuples
    """
    if use_easyocr:
        return extract_text_easyocr(page, dpi=dpi)

    try:
        pix = page.get_pixmap(dpi=dpi)
        new_doc = pymupdf.open()
        new_page = new_doc.new_page(width=pix.width, height=pix.height)
        new_page.insert_image(new_page.rect, pixmap=pix)
        tp = new_page.get_textpage_ocr(language="eng", DPI=dpi)
        ocr_text = new_page.get_text(textpage=tp)
        new_doc.close()

        items: List[Tuple[Tuple[float, float, float, float], str, float]] = []
        if ocr_text and isinstance(ocr_text, str) and ocr_text.strip():
            items.append(((0.0, 0.0, 0.0, 0.0), ocr_text, DEFAULT_FONT_SIZE))
        return items
    except AttributeError:
        logging.error("PyMuPDF OCR requires pymupdf >= 1.23.0 with Tesseract support")
        raise
    except Exception as e:
        logging.error(f"OCR extraction failed: {e}")
        raise


def extract_text_easyocr(
    page, dpi: int = 300
) -> List[Tuple[Tuple[float, float, float, float], str, float]]:
    """
    Extract text using easyOCR.

    @param page: pymupdf page object
    @param dpi: resolution for OCR
    @return: list of (bbox, text, font_size) tuples
    """
    try:
        import io

        import easyocr
        from PIL import Image
    except ImportError:
        logging.error("easyOCR not installed. Run: pip install easyocr")
        raise

    try:
        pix = page.get_pixmap(dpi=dpi)
        img_data = pix.tobytes("png")

        reader = easyocr.Reader(["en"], gpu=True)
        results = reader.readtext(img_data)

        detections: List[Tuple[Tuple[float, float, float, float], str, float]] = []
        for detection in results:
            bbox = detection[0]
            text = detection[1]

            if not text or not isinstance(text, str) or not text.strip():
                continue

            x0 = min(p[0] for p in bbox)
            y0 = min(p[1] for p in bbox)
            x1 = max(p[0] for p in bbox)
            y1 = max(p[1] for p in bbox)

            detections.append(((x0, y0, x1, y1), text, DEFAULT_FONT_SIZE))

        return _group_easyocr_detections(detections)
    except Exception as e:
        logging.error(f"easyOCR extraction failed: {e}")
        raise


def _group_easyocr_detections(
    detections: List[Tuple[Tuple[float, float, float, float], str, float]],
    line_threshold: float = 15.0,
    block_threshold: float = 30.0,
) -> List[Tuple[Tuple[float, float, float, float], str, float]]:
    """
    Group easyOCR detections into blocks (paragraphs) instead of returning each word.

    @param detections: list of (bbox, text, font_size) tuples from easyOCR
    @param line_threshold: max vertical distance to consider as same line
    @param block_threshold: max vertical distance between lines to consider same block
    @return: list of (bbox, text, font_size) tuples grouped by blocks
    """
    if not detections:
        return []

    sorted_detections = sorted(detections, key=lambda x: (x[0][1], x[0][0]))

    lines: List[List[Tuple[Tuple[float, float, float, float], str, float]]] = []
    current_line = [sorted_detections[0]]
    current_y = sorted_detections[0][0][1]

    for detection in sorted_detections[1:]:
        bbox = detection[0]
        y_pos = bbox[1]

        if abs(y_pos - current_y) <= line_threshold:
            current_line.append(detection)
        else:
            current_line.sort(key=lambda x: x[0][0])
            lines.append(current_line)
            current_line = [detection]
            current_y = y_pos

    if current_line:
        current_line.sort(key=lambda x: x[0][0])
        lines.append(current_line)

    blocks: List[Tuple[Tuple[float, float, float, float], str, float]] = []
    current_block = [lines[0]]
    current_block_bottom = lines[0][-1][0][3]

    for line in lines[1:]:
        line_top = line[0][0][1]
        line_bottom = line[-1][0][3]

        if line_top - current_block_bottom <= block_threshold:
            current_block.append(line)
            current_block_bottom = max(current_block_bottom, line_bottom)
        else:
            block = _merge_lines_into_block(current_block)
            blocks.append(block)
            current_block = [line]
            current_block_bottom = line_bottom

    if current_block:
        block = _merge_lines_into_block(current_block)
        blocks.append(block)

    return blocks


def _merge_lines_into_block(
    lines: List[List[Tuple[Tuple[float, float, float, float], str, float]]],
) -> Tuple[Tuple[float, float, float, float], str, float]:
    """
    Merge multiple lines into a single block.

    @param lines: list of lines, where each line is a list of detections
    @return: (bbox, combined_text, font_size)
    """
    all_texts = []
    bboxes = []
    font_sizes = []

    for line in lines:
        for bbox, text, font_size in line:
            bboxes.append(bbox)
            font_sizes.append(font_size)
            all_texts.append(text)

    x0 = min(b[0] for b in bboxes)
    y0 = min(b[1] for b in bboxes)
    x1 = max(b[2] for b in bboxes)
    y1 = max(b[3] for b in bboxes)

    combined_text = " ".join(all_texts)
    avg_font_size = (
        sum(font_sizes) / len(font_sizes) if font_sizes else DEFAULT_FONT_SIZE
    )

    return ((x0, y0, x1, y1), combined_text, avg_font_size)


def extract_text_ocr_region(
    page,
    bbox: Tuple[float, float, float, float],
    dpi: int = 300,
    padding: int = 5,
) -> str:
    """
    OCR a specific region of the page.

    @param page: pymupdf page object
    @param bbox: bounding box (x0, y0, x1, y1)
    @param dpi: resolution for OCR
    @param padding: pixels to add around bbox for better text capture
    @return: OCR'd text from the region
    """
    try:
        x0, y0, x1, y1 = bbox

        scale = dpi / 72.0
        padding_scaled = padding * scale

        clip = pymupdf.Rect(
            x0 - padding_scaled / scale,
            y0 - padding_scaled / scale,
            x1 + padding_scaled / scale,
            y1 + padding_scaled / scale,
        )

        clip = clip & page.rect

        pix = page.get_pixmap(dpi=dpi, clip=clip)

        new_doc = pymupdf.open()
        new_page = new_doc.new_page(width=pix.width, height=pix.height)
        new_page.insert_image(new_page.rect, pixmap=pix)
        tp = new_page.get_textpage_ocr(language="eng", dpi=dpi)
        ocr_text = new_page.get_text(textpage=tp)
        new_doc.close()

        return ocr_text.strip() if isinstance(ocr_text, str) and ocr_text else ""

    except Exception as e:
        logging.error(f"OCR region extraction failed: {e}")
        return ""


def extract_text_legacy_ocr(
    page, dpi: int = 300, padding: int = 5
) -> List[Tuple[Tuple[float, float, float, float], str, float]]:
    """
    Try legacy extraction per block, OCR only garbled blocks.

    This checks each block individually for garbled text and only
    runs OCR on the specific regions that need it, preserving
    correctly extracted text and bboxes.
    """
    legacy_blocks = extract_text_legacy(page)
    result_blocks: List[Tuple[Tuple[float, float, float, float], str, float]] = []

    garbled_count = 0

    for bbox, text, font_size in legacy_blocks:
        if is_garbled_text(text):
            garbled_count += 1
            logging.info(
                f"LegacyOCR: Garbled block detected, running OCR for region {bbox}"
            )
            try:
                ocr_text = extract_text_ocr_region(page, bbox, dpi=dpi, padding=padding)
                if ocr_text:
                    result_blocks.append((bbox, ocr_text, font_size))
                else:
                    result_blocks.append((bbox, text.replace("\ufffd", "?"), font_size))
            except Exception as e:
                logging.error(f"LegacyOCR: OCR failed for block, using original: {e}")
                result_blocks.append((bbox, text.replace("\ufffd", "?"), font_size))
        else:
            result_blocks.append((bbox, text, font_size))

    if garbled_count > 0:
        logging.info(
            f"LegacyOCR: Processed {garbled_count} garbled blocks out of {len(legacy_blocks)}"
        )

    return result_blocks


def extract_text_easyocr_region(
    page,
    bbox: Tuple[float, float, float, float],
    dpi: int = 300,
    padding: int = 5,
) -> str:
    """
    OCR a specific region of the page using easyOCR.

    @param page: pymupdf page object
    @param bbox: bounding box (x0, y0, x1, y1)
    @param dpi: resolution for OCR
    @param padding: pixels to add around bbox for better text capture
    @return: OCR'd text from the region
    """
    try:
        import easyocr
    except ImportError:
        logging.error("easyOCR not installed. Run: pip install easyocr")
        return ""

    try:
        x0, y0, x1, y1 = bbox

        scale = dpi / 72.0
        padding_scaled = padding * scale

        clip = pymupdf.Rect(
            x0 - padding_scaled / scale,
            y0 - padding_scaled / scale,
            x1 + padding_scaled / scale,
            y1 + padding_scaled / scale,
        )

        clip = clip & page.rect

        pix = page.get_pixmap(dpi=dpi, clip=clip)
        img_data = pix.tobytes("png")

        reader = easyocr.Reader(["en"], gpu=False)
        results = reader.readtext(img_data)

        ocr_text = " ".join([result[1] for result in results])
        return ocr_text.strip() if ocr_text else ""

    except Exception as e:
        logging.error(f"easyOCR region extraction failed: {e}")
        return ""


def extract_text_legacy_easyocr(
    page, dpi: int = 300, padding: int = 5
) -> List[Tuple[Tuple[float, float, float, float], str, float]]:
    """
    Try legacy extraction per block, OCR only garbled blocks using easyOCR.

    This checks each block individually for garbled text and only
    runs easyOCR on the specific regions that need it, preserving
    correctly extracted text and bboxes.
    """
    legacy_blocks = extract_text_legacy(page)
    result_blocks: List[Tuple[Tuple[float, float, float, float], str, float]] = []

    garbled_count = 0

    for bbox, text, font_size in legacy_blocks:
        if is_garbled_text(text):
            garbled_count += 1
            logging.info(
                f"Legacy+easyOCR: Garbled block detected, running OCR for region {bbox}"
            )
            try:
                ocr_text = extract_text_easyocr_region(
                    page, bbox, dpi=dpi, padding=padding
                )
                if ocr_text:
                    result_blocks.append((bbox, ocr_text, font_size))
                else:
                    result_blocks.append((bbox, text.replace("\ufffd", "?"), font_size))
            except Exception as e:
                logging.error(
                    f"Legacy+easyOCR: OCR failed for block, using original: {e}"
                )
                result_blocks.append((bbox, text.replace("\ufffd", "?"), font_size))
        else:
            result_blocks.append((bbox, text, font_size))

    if garbled_count > 0:
        logging.info(
            f"Legacy+easyOCR: Processed {garbled_count} garbled blocks out of {len(legacy_blocks)}"
        )

    return result_blocks


_docling_parser_cache = {}
_docling_pdf_doc_cache = {}


def _get_docling_parser():
    from docling_parse.pdf_parser import DoclingPdfParser

    return DoclingPdfParser()


def extract_text_docling(
    pdf_path: str, page_num: int
) -> List[Tuple[Tuple[float, float, float, float], str, float]]:
    from docling_core.types.doc.page import TextCellUnit

    global _docling_parser_cache, _docling_pdf_doc_cache

    parser = _docling_parser_cache.get("parser")
    if parser is None:
        parser = _get_docling_parser()
        _docling_parser_cache["parser"] = parser

    pdf_doc = _docling_pdf_doc_cache.get(pdf_path)
    if pdf_doc is None:
        pdf_doc = parser.load(path_or_stream=pdf_path)
        _docling_pdf_doc_cache[pdf_path] = pdf_doc

    items: List[Tuple[Tuple[float, float, float, float], str, float]] = []

    pages_list = list(pdf_doc.iterate_pages())
    if page_num >= len(pages_list):
        return items

    _, pred_page = pages_list[page_num]

    for cell in pred_page.iterate_cells(unit_type=TextCellUnit.LINE):
        rect = cell.rect
        x0 = min(rect.r_x0, rect.r_x1, rect.r_x2, rect.r_x3)
        y0 = min(rect.r_y0, rect.r_y1, rect.r_y2, rect.r_y3)
        x1 = max(rect.r_x0, rect.r_x1, rect.r_x2, rect.r_x3)
        y1 = max(rect.r_y0, rect.r_y1, rect.r_y2, rect.r_y3)

        text = cell.text
        if text and isinstance(text, str) and text.strip():
            items.append(((x0, y0, x1, y1), text, DEFAULT_FONT_SIZE))

    return items


def clear_docling_cache(pdf_path: Optional[str] = None) -> None:
    global _docling_parser_cache, _docling_pdf_doc_cache

    if pdf_path is None:
        _docling_parser_cache.clear()
        for doc in _docling_pdf_doc_cache.values():
            try:
                doc.unload()
            except Exception:
                pass
        _docling_pdf_doc_cache.clear()
    elif pdf_path in _docling_pdf_doc_cache:
        try:
            _docling_pdf_doc_cache[pdf_path].unload()
        except Exception:
            pass
        del _docling_pdf_doc_cache[pdf_path]


def extract_text_hybrid(
    page, pdf_path: str, page_num: int
) -> List[Tuple[Tuple[float, float, float, float], str, float]]:
    legacy_blocks = extract_text_legacy(page)

    all_text = " ".join(text for _, text, _ in legacy_blocks)

    if is_garbled_text(all_text):
        logging.info(
            f"Hybrid: Garbled text detected on page {page_num + 1}, switching to Docling"
        )
        try:
            return extract_text_docling(pdf_path, page_num)
        except Exception as e:
            logging.error(f"Hybrid: Docling failed, falling back to legacy: {e}")
            return [
                (bbox, text.replace("\ufffd", "?"), font_size)
                for bbox, text, font_size in legacy_blocks
            ]

    return legacy_blocks


def extract_pdf_text(
    page,
    pdf_path: Optional[str],
    page_num: int,
    mode: Optional[ParserMode] = None,
) -> List[Tuple[Tuple[float, float, float, float], str, float]]:
    parser_mode = mode or get_parser_mode()

    if parser_mode == ParserMode.LEGACY:
        return extract_text_legacy(page)
    elif parser_mode == ParserMode.LEGACYOCR:
        return extract_text_legacy_ocr(page)
    elif parser_mode == ParserMode.EASYOCR:
        return extract_text_legacy_easyocr(page)
    elif parser_mode == ParserMode.DOCLING:
        try:
            if pdf_path is None:
                return extract_text_legacy(page)
            return extract_text_docling(pdf_path, page_num)
        except Exception as e:
            logging.error(f"Docling extraction failed, falling back to legacy: {e}")
            return extract_text_legacy(page)
    else:  # HYBRID
        if pdf_path is None:
            return extract_text_legacy(page)
        return extract_text_hybrid(page, pdf_path, page_num)


def get_horizontal_lines(
    page, min_width: float = 30.0, max_height: float = 5.0
) -> List[dict]:
    """
    Extract horizontal lines from page (e.g., footnote separators).

    Filters drawings for:
    - Lines with near-horizontal slope (small height difference)
    - Thin horizontal rectangles

    @param page: pymupdf page object
    @param min_width: minimum line width to consider (avoid short dashes)
    @param max_height: maximum height to consider as a "line" (not a box)
    @return: list of drawing dicts representing horizontal lines
    """
    try:
        drawings = page.get_drawings()
    except Exception as e:
        logging.warning(f"Could not extract drawings from page: {e}")
        return []

    horizontal_lines = []

    for path in drawings:
        rect = path.get("rect")
        if rect is None:
            continue

        width = rect.width
        height = rect.height

        if width >= min_width and height <= max_height:
            items = path.get("items", [])

            has_horizontal = False

            for item in items:
                item_type = item[0] if item else None
                if item_type == "l":
                    p1, p2 = item[1], item[2]
                    line_height = abs(p2.y - p1.y)
                    line_width = abs(p2.x - p1.x)
                    if line_height <= max_height and line_width >= min_width:
                        has_horizontal = True
                        break
                elif item_type == "re":
                    if width >= min_width and height <= max_height:
                        has_horizontal = True
                        break
                elif item_type == "c":
                    points = item[1:]
                    if len(points) >= 2:
                        y_coords = [p.y for p in points]
                        y_min, y_max = min(y_coords), max(y_coords)
                        curve_height = y_max - y_min
                        if curve_height <= max_height and width >= min_width:
                            has_horizontal = True
                            break

            if has_horizontal:
                horizontal_lines.append(path)
                logging.debug(f"Found horizontal line: rect={rect}, items={len(items)}")

    return horizontal_lines


def redraw_horizontal_lines(page, lines: List[dict]) -> None:
    """
    Redraw horizontal lines on the page.

    @param page: pymupdf page object
    @param lines: list of line dicts from get_horizontal_lines()
    """
    if not lines:
        return

    for path in lines:
        shape = page.new_shape()
        has_drawings = False

        for item in path.get("items", []):
            item_type = item[0] if item else None

            if item_type == "l":
                p1, p2 = item[1], item[2]
                shape.draw_line(p1, p2)
                has_drawings = True

            elif item_type == "re":
                rect = item[1]
                shape.draw_rect(rect)
                has_drawings = True

        if has_drawings:
            shape.finish(
                color=path.get("color"),
                fill=path.get("fill"),
                width=path.get("width", 0.5),
                lineCap=2,
            )
            shape.commit()
