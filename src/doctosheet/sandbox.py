"""Run extraction of an untrusted file in a separate process with limits.

A malformed or malicious PDF must not hang or exhaust the application: each
file is processed in a child process that is killed after ``timeout`` seconds
and (on Linux and macOS) cannot allocate more than ``memory_mb``.
"""

from __future__ import annotations

import multiprocessing as mp
import sys
from multiprocessing.connection import Connection
from typing import Any

DEFAULT_TIMEOUT = 120.0
# Address space, not resident memory: ONNX Runtime (OCR) reserves several GB of
# virtual memory for thread stacks and arenas that it never touches. The cap
# still stops runaway allocations such as decompression bombs.
DEFAULT_MEMORY_MB = 8192


class ExtractionFailed(RuntimeError):
    pass


def _child(conn: Connection, data: bytes, name: str, memory_mb: int) -> None:
    if sys.platform != "win32":
        import resource

        limit = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    try:
        from .extract import extract

        conn.send(("ok", extract(data, name).to_dict()))
    except MemoryError:
        conn.send(("error", "The document needs too much memory to process."))
    except Exception as exc:
        conn.send(("error", str(exc) or type(exc).__name__))
    finally:
        conn.close()


def extract_isolated(
    data: bytes, name: str, timeout: float = DEFAULT_TIMEOUT, memory_mb: int = DEFAULT_MEMORY_MB
) -> dict[str, Any]:
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(child, data, name, memory_mb), daemon=True)
    proc.start()
    child.close()
    try:
        if not parent.poll(timeout):
            raise ExtractionFailed(f"Processing took longer than {timeout:.0f} seconds and was stopped.")
        try:
            status, payload = parent.recv()
        except EOFError as exc:
            raise ExtractionFailed("The document could not be processed (the worker stopped).") from exc
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join(5)
        parent.close()
    if status != "ok":
        raise ExtractionFailed(payload)
    return payload  # type: ignore[no-any-return]
