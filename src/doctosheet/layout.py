"""Words with positions, grouped into lines; text spans map back to page boxes."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Box


@dataclass
class Word:
    text: str
    box: Box
    confidence: float = 1.0  # OCR confidence; 1.0 for the PDF text layer


@dataclass
class Line:
    words: list[Word]
    text: str = ""
    # (start, end) character span of each word in ``text``
    spans: list[tuple[int, int]] = field(default_factory=list)

    @staticmethod
    def build(words: list[Word]) -> Line:
        words = sorted(words, key=lambda w: w.box.x0)
        text = ""
        spans = []
        prev: Word | None = None
        for w in words:
            if prev is not None:
                gap = w.box.x0 - prev.box.x1
                height = max(prev.box.y1 - prev.box.y0, 1.0)
                # A wide gap separates table columns; keep it visible as two spaces.
                text += "  " if gap > height * 1.2 else " "
            spans.append((len(text), len(text) + len(w.text)))
            text += w.text
            prev = w
        return Line(words, text, spans)

    @property
    def box(self) -> Box:
        b = Box.union([w.box for w in self.words])
        assert b is not None
        return b

    @property
    def page(self) -> int:
        return self.words[0].box.page

    def span_box(self, start: int, end: int) -> Box | None:
        """Box covering the words that overlap characters [start, end)."""
        return Box.union([w.box for w, (s, e) in zip(self.words, self.spans) if s < end and e > start])

    def span_confidence(self, start: int, end: int) -> float:
        confs = [w.confidence for w, (s, e) in zip(self.words, self.spans) if s < end and e > start]
        return min(confs) if confs else 1.0

    def words_in(self, x0: float, x1: float) -> list[tuple[Word, tuple[int, int]]]:
        """Words whose horizontal centre lies in [x0, x1)."""
        return [
            (w, sp)
            for w, sp in zip(self.words, self.spans)
            if x0 <= (w.box.x0 + w.box.x1) / 2 < x1
        ]


def group_lines(words: list[Word]) -> list[Line]:
    """Group words into lines by vertical overlap, page by page, top to bottom."""
    lines: list[Line] = []
    for page in sorted({w.box.page for w in words}):
        rows: list[list[Word]] = []
        for w in sorted((w for w in words if w.box.page == page), key=lambda w: (w.box.y0, w.box.x0)):
            mid = (w.box.y0 + w.box.y1) / 2
            for row in rows:
                top = min(x.box.y0 for x in row)
                bottom = max(x.box.y1 for x in row)
                # Same line if the word's centre lies within the row's vertical extent
                # and the row is not far to the right of a different text block.
                if top - 1 <= mid <= bottom + 1:
                    row.append(w)
                    break
            else:
                rows.append([w])
        rows.sort(key=lambda r: min(x.box.y0 for x in r))
        lines.extend(Line.build(r) for r in rows)
    return lines
