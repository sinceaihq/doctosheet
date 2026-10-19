"""OCR of scanned pages and photos with RapidOCR (PaddleOCR models on ONNX Runtime).

Optional: install with ``pip install "doctosheet[ocr]"``. The models (about
20 MB) are downloaded once by RapidOCR on first use and then run offline.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from .layout import Word
from .model import Box


class OcrUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _engine() -> Any:
    try:
        from rapidocr import ModelType, OCRVersion, RapidOCR
    except ImportError as exc:
        raise OcrUnavailable(
            'This document needs OCR. Install it with: pip install "doctosheet[ocr]"'
        ) from exc
    threads = int(os.environ.get("DOCTOSHEET_OCR_THREADS", "4"))
    return RapidOCR(
        params={
            "Global.log_level": "error",
            "Global.return_word_box": True,
            "Det.ocr_version": OCRVersion.PPOCRV5,
            "Det.model_type": ModelType.MOBILE,
            # Multilingual recogniser covering the EU's Latin-script languages.
            "Rec.ocr_version": OCRVersion.PPOCRV6,
            "Rec.model_type": ModelType.SMALL,
            "EngineConfig.onnxruntime.intra_op_num_threads": threads,
        }
    )


def ocr_image(image: Any, page: int, scale: float = 1.0) -> list[Word]:
    """Words with boxes (in the page's coordinate system) and confidences."""
    result = _engine()(image)
    words: list[Word] = []
    if result.txts is None:
        return words
    word_results = getattr(result, "word_results", None)
    for i, (box, text, score) in enumerate(zip(result.boxes, result.txts, result.scores)):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        parts = word_results[i] if word_results is not None and i < len(word_results) else None
        if parts:
            # Split a detected text line into words with their own boxes.
            for part_text, part_score, part_box in parts:
                if not str(part_text).strip():
                    continue
                pxs = [p[0] for p in part_box]
                pys = [p[1] for p in part_box]
                words.append(
                    Word(
                        str(part_text),
                        Box(page, min(pxs) * scale, min(pys) * scale, max(pxs) * scale, max(pys) * scale),
                        float(part_score),
                    )
                )
            continue
        for token in _split_tokens(str(text), min(xs), max(xs)):
            tok, x0, x1 = token
            words.append(Word(tok, Box(page, x0 * scale, min(ys) * scale, x1 * scale, max(ys) * scale), float(score)))
    return words


def _split_tokens(text: str, x0: float, x1: float) -> list[tuple[str, float, float]]:
    """Fallback: split a line into words, distributing the width by character count."""
    tokens = text.split()
    if not tokens:
        return []
    per_char = (x1 - x0) / max(len(text), 1)
    out, pos = [], 0
    for tok in tokens:
        start = text.index(tok, pos)
        out.append((tok, x0 + start * per_char, x0 + (start + len(tok)) * per_char))
        pos = start + len(tok)
    return out
