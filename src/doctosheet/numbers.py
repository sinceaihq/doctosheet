"""European amounts, dates and percentages.

Amounts: "1.234,56", "1 234,56", "1,234.56", "1'234.56", "1234,56", "-12,50".
The decimal separator is the last "." or "," followed by exactly two digits.
Ambiguous strings ("1.234" — thousands or decimals?) are not amounts.
Dates are read day first, as everywhere in the EU, and must exist.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import re
import unicodedata
from decimal import Decimal, InvalidOperation

SPACE = "[    ]"
AMOUNT_RE = re.compile(
    rf"(?<![\d.,])[-−]?(?:\d{{1,3}}(?:(?:[.,']|{SPACE})\d{{3}})+|\d+)[.,]\d{{2}}(?![\d])(?:{SPACE}?-)?"
)
INTEGER_RE = re.compile(r"(?<![\d.,])\d{1,6}(?![\d.,]\d)")
PERCENT_RE = re.compile(r"(?<![\d.,])(\d{1,2}(?:[.,]\d{1,2})?)\s?%")
NUM_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\s?[./-]\s?(\d{1,2})\s?[./-]\s?(\d{4}|\d{2})(?![\d.])")
ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
LONG_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\.?\s+(?:de\s+)?([^\W\d_]+)\.?,?\s+(?:de\s+)?(\d{4})")
MONTH_FIRST_RE = re.compile(r"\b([^\W\d_]+)\.?\s+(\d{1,2}),?\s+(\d{4})\b")

MONTHS: dict[str, int] = {}
for _names in (
    "january february march april may june july august september october november december",
    "jan feb mar apr may jun jul aug sep oct nov dec",
    "tammikuuta helmikuuta maaliskuuta huhtikuuta toukokuuta kesäkuuta heinäkuuta elokuuta "
    "syyskuuta lokakuuta marraskuuta joulukuuta",
    "januari februari mars april maj juni juli augusti september oktober november december",
    "januar februar märz april mai juni juli august september oktober november dezember",
    "jänner feber märz april mai juni juli august september oktober november dezember",
    "janvier février mars avril mai juin juillet août septembre octobre novembre décembre",
    "januari februari maart april mei juni juli augustus september oktober november december",
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre",
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre",
    "stycznia lutego marca kwietnia maja czerwca lipca sierpnia września października listopada grudnia",
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro",
    "ledna února března dubna května června července srpna září října listopadu prosince",
    "januar februar marts april maj juni juli august september oktober november december",
    "januar februar mars april mai juni juli august september oktober november desember",
):
    for _i, _m in enumerate(_names.split(), 1):
        MONTHS.setdefault(_m, _i)


def fold(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold()


def parse_amount(token: str) -> Decimal | None:
    """Decimal value of an amount token, or None if it is not an unambiguous amount."""
    t = re.sub(SPACE, "", token).replace("'", "").replace("−", "-")
    negative = t.startswith("-") or t.endswith("-")
    t = t.strip("-")
    m = re.fullmatch(r"([\d.,]*?)[.,](\d{2})", t)
    if not m:
        return None
    whole = m.group(1)
    # The thousands separator must be consistent and different from the decimal one.
    seps = set(re.findall(r"[.,]", whole))
    if len(seps) > 1 or (seps and seps == {t[-3]}):
        return None
    try:
        value = Decimal(f"{re.sub(r'[.,]', '', whole) or 0}.{m.group(2)}")
    except InvalidOperation:
        return None
    return -value if negative else value


def amounts_in(text: str) -> list[tuple[int, int, Decimal]]:
    """(start, end, value) of every amount, ignoring percentages."""
    masked = PERCENT_RE.sub(lambda m: " " * len(m.group(0)), text)
    out = []
    for m in AMOUNT_RE.finditer(masked):
        value = parse_amount(m.group(0))
        if value is not None:
            out.append((m.start(), m.end(), value))
    return out


def parse_quantity(token: str) -> Decimal | None:
    """Quantities: "3", "2,5", "1.000", "12 pcs" (number only)."""
    t = re.sub(SPACE, "", token.strip())
    m = re.fullmatch(r"(\d{1,7})(?:[.,](\d{1,3}))?", t)
    if not m:
        return None
    if m.group(2) and len(m.group(2)) == 3 and "," not in t:
        # "1.000" is more likely one thousand than one; accept only as integer thousands
        return Decimal(m.group(1) + m.group(2))
    return Decimal(f"{m.group(1)}.{m.group(2)}") if m.group(2) else Decimal(m.group(1))


def percents_in(text: str) -> list[tuple[int, int, Decimal]]:
    return [(m.start(), m.end(), Decimal(m.group(1).replace(",", "."))) for m in PERCENT_RE.finditer(text)]


def _year(y: str) -> int:
    n = int(y)
    return n + 2000 if len(y) == 2 else n


def dates_in(text: str) -> list[tuple[int, int, dt.date]]:
    """(start, end, date) of every date, in reading order."""
    found: list[tuple[int, int, dt.date]] = []
    for m in ISO_DATE_RE.finditer(text):
        with contextlib.suppress(ValueError):
            found.append((m.start(), m.end(), dt.date(int(m[1]), int(m[2]), int(m[3]))))
    for m in NUM_DATE_RE.finditer(text):
        with contextlib.suppress(ValueError):
            found.append((m.start(), m.end(), dt.date(_year(m[3]), int(m[2]), int(m[1]))))
    for m in LONG_DATE_RE.finditer(text):
        month = MONTHS.get(fold(m[2]))
        if month:
            with contextlib.suppress(ValueError):
                found.append((m.start(), m.end(), dt.date(int(m[3]), month, int(m[1]))))
    for m in MONTH_FIRST_RE.finditer(text):
        month = MONTHS.get(fold(m[1]))
        if month:
            with contextlib.suppress(ValueError):
                found.append((m.start(), m.end(), dt.date(int(m[3]), month, int(m[2]))))
    # drop dates contained in another (e.g. ISO inside a longer match)
    found.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    kept: list[tuple[int, int, dt.date]] = []
    for f in found:
        if not kept or f[0] >= kept[-1][1]:
            kept.append(f)
    return kept


def fmt_amount(value: Decimal) -> str:
    return f"{value:.2f}"
