# Local development

## Requirements

- Python 3.11 or 3.12
- Git
- Docker Desktop (optional)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python scripts/initialize_demo_db.py
streamlit run app.py
```

On Windows PowerShell, use `.venv\Scripts\Activate.ps1`.

The lockfile captures the fully verified development environment. `pyproject.toml`
keeps bounded direct dependencies for maintainers. NumPy is capped below 2.5 because
the 2.5 type stubs require syntax newer than the project's Python 3.11 type-checking
target.

## Configuration

Copy `.env.example` to `.env`. Fake mode needs no secret. Configuration is read at
runtime; imports do not load `.env`.

| Variable | Purpose | Default |
| --- | --- | --- |
| `LLM_PROVIDER` | `fake` or `gemini` | `fake` |
| `GEMINI_API_KEY` | Gemini credential | none |
| `GEMINI_MODEL` | Gemini model identifier | `gemini-2.5-flash` |
| `DATABASE_PATH` | Fixed application database | `data/demo/chinook_demo.sqlite` |
| `MAX_RETURNED_ROWS` | Execution row cap | `200` |
| `MAX_REPAIR_ATTEMPTS` | Bounded repair count | `1` |
| `LOG_LEVEL` | Safe structured log level | `INFO` |

Do not put a real secret in commands, screenshots, tests, issue reports, or committed
files.

## Quality gates

Run the commands documented in the README before submitting changes. Tests must remain
offline by default; the real Gemini API is never called by the test suite or CI.
