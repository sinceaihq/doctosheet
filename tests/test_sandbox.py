import sys

import pytest

from doctosheet import sandbox


@pytest.mark.skipif(sys.platform == "win32", reason="no resource limits on Windows")
def test_memory_limit_failure_is_tolerated(monkeypatch):
    import resource

    # macOS refuses RLIMIT_AS ("current limit exceeds maximum limit"); extraction must still run.
    def refuse(*_args):
        raise ValueError("current limit exceeds maximum limit")

    monkeypatch.setattr(resource, "setrlimit", refuse)
    assert sandbox.limit_memory(1024) is False


@pytest.mark.skipif(sys.platform == "win32", reason="no resource limits on Windows")
def test_memory_limit_respects_hard_limit(monkeypatch):
    import resource

    calls = []
    monkeypatch.setattr(resource, "getrlimit", lambda _r: (resource.RLIM_INFINITY, 512 * 1024 * 1024))
    monkeypatch.setattr(resource, "setrlimit", lambda r, lim: calls.append(lim))
    assert sandbox.limit_memory(8192) is True
    assert calls == [(512 * 1024 * 1024, 512 * 1024 * 1024)]


def test_isolated_extraction_runs(tmp_path):
    from pathlib import Path

    data = (Path(__file__).parent / "samples" / "invoice-nl-peppol.xml").read_bytes()
    out = sandbox.extract_isolated(data, "invoice-nl-peppol.xml", timeout=60)
    assert out["fields"]["total_amount"]["value"]
