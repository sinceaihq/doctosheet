"""Damaged input must produce a clear error (a ValueError subclass), never a crash with a library exception."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from doctosheet.extract import extract

SAMPLES = Path(__file__).parent / "samples"


def _variants(data: bytes, seed: int, n: int = 25) -> list[bytes]:
    rng = random.Random(seed)
    out = [data[: len(data) * k // 10] for k in range(1, 10)]
    for _ in range(n):
        b = bytearray(data)
        for _ in range(rng.randrange(1, 40)):
            b[rng.randrange(len(b))] = rng.randrange(256)
        out.append(bytes(b))
    return out


@pytest.mark.parametrize("name", ["invoice-fi.pdf", "invoice-de-zugferd.pdf", "invoice-nl-peppol.xml"])
def test_damaged_documents_fail_cleanly(name: str) -> None:
    for i, data in enumerate(_variants((SAMPLES / name).read_bytes(), seed=len(name))):
        try:
            extract(data, name)
        except ValueError as exc:
            assert str(exc), f"variant {i}: empty error message"


@pytest.mark.parametrize("data", [b"", b"%PDF-", b"\x89PNG\r\n\x1a\n" + b"\0" * 64, bytes(range(256)) * 4])
def test_garbage_fails_cleanly(data: bytes) -> None:
    with pytest.raises(ValueError):
        extract(data, "upload.png")
