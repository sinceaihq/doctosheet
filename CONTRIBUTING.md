# Contributing to DocToSheet

The most valuable contributions are **invoices that DocToSheet reads badly** — described or attached with all personal
and business details replaced — and **vocabulary for your language** (invoice labels in `src/doctosheet/vocab.py`).

```bash
git clone https://github.com/sinceaihq/doctosheet && cd doctosheet
python -m venv .venv && source .venv/bin/activate
pip install -e ".[ocr,dev]" && playwright install chromium
pytest && ruff check . && ruff format --check . && mypy
```

The review app is TypeScript in `ui/` (`npm ci && npm run build` writes into `src/doctosheet/static`).

## Changing extraction

1. Add a failing test with a synthetic example (`tests/test_core.py`, or a new sample in `scripts/make_samples.py`).
2. Fix the rule; keep evidence messages meaningful — users see them.
3. Run the evaluations in `eval/` on the **dev** splits and report the change in the pull request. Do not tune on test
   splits: their numbers are only re-measured for releases (`docs/EVALUATION.md`).

## Rules

- Never commit real invoices or personal data. Never guess amounts silently.
- Conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`).
- Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
