#!/usr/bin/env python3
"""Split a PDF into chapter/page-range files based on a mapping file.

Mapping file format (one entry per line):
    chapter_name:start_page-end_page

Example mapping file (pages.txt):
    1:1-15
    2:16-32
    appendix:33-40

Usage:
    python split_pdf.py book.pdf pages.txt
    python split_pdf.py book.pdf pages.txt -o output_dir/
    python split_pdf.py book.pdf pages.txt --prefix "ch-" --zero-padded
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pymupdf


def parse_mapping(mapping_path: str) -> List[Tuple[str, int, int]]:
    entries = []
    with open(mapping_path, "r", encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                name_part, range_part = line.split(":", 1)
                start_str, end_str = range_part.split("-", 1)
                name = name_part.strip()
                start_page = int(start_str.strip())
                end_page = int(end_str.strip())
                if start_page < 1 or end_page < 1:
                    print(
                        f"Warning: line {line_num}: page numbers must be >= 1, skipping"
                    )
                    continue
                if start_page > end_page:
                    print(
                        f"Warning: line {line_num}: start page > end page, skipping"
                    )
                    continue
                entries.append((name, start_page, end_page))
            except ValueError:
                print(
                    f"Warning: line {line_num}: invalid format "
                    f"'{raw_line.strip()}', expected 'name:start-end'"
                )
                continue
    return entries


def split_pdf(
    pdf_path: str,
    entries: List[Tuple[str, int, int]],
    output_dir: str,
    prefix: str,
    zero_padded: bool,
) -> List[str]:
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    created_files = []

    for name, start_page, end_page in entries:
        pdf_start = start_page - 1
        pdf_end = end_page - 1

        if pdf_start >= total_pages:
            print(
                f"Warning: '{name}' start page {start_page} exceeds "
                f"PDF length ({total_pages}), skipping"
            )
            continue

        pdf_end = min(pdf_end, total_pages - 1)
        actual_end = pdf_end + 1

        new_doc = pymupdf.open()
        new_doc.insert_pdf(doc, from_page=pdf_start, to_page=pdf_end)

        if zero_padded and name.isdigit():
            filename = f"{prefix}{name.zfill(3)}.pdf"
        else:
            filename = f"{prefix}{name}.pdf"

        out_path = os.path.join(output_dir, filename)
        new_doc.save(out_path)
        new_doc.close()
        created_files.append(out_path)
        print(
            f"Created: {out_path}  (pages {start_page}-{actual_end}, "
            f"{actual_end - start_page + 1} pages)"
        )

    doc.close()
    return created_files


def main():
    parser = argparse.ArgumentParser(
        description="Split a PDF into sections based on a page mapping file."
    )
    parser.add_argument("pdf", help="Path to the input PDF file")
    parser.add_argument(
        "mapping", help="Path to mapping file (format: name:start-end)"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help="Output directory (default: same as input PDF)",
    )
    parser.add_argument(
        "--prefix",
        default="ch-",
        help="Filename prefix for output files (default: 'ch-')",
    )
    parser.add_argument(
        "--zero-padded",
        action="store_true",
        help="Zero-pad numeric chapter names to 3 digits (e.g. ch-001.pdf)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"Error: PDF file not found: {args.pdf}")
        sys.exit(1)

    if not os.path.isfile(args.mapping):
        print(f"Error: Mapping file not found: {args.mapping}")
        sys.exit(1)

    output_dir = args.output_dir or str(Path(args.pdf).parent)
    os.makedirs(output_dir, exist_ok=True)

    entries = parse_mapping(args.mapping)
    if not entries:
        print("Error: No valid entries found in mapping file.")
        sys.exit(1)

    created = split_pdf(args.pdf, entries, output_dir, args.prefix, args.zero_padded)
    print(f"\nDone. Created {len(created)} file(s).")


if __name__ == "__main__":
    main()