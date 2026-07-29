# Streamlit Blueprint Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a portfolio-grade Blueprint AI Workbench UI, verify its safe offline workflow, replace the tracked screenshot, and publish the update to GitHub.

**Architecture:** Keep Streamlit as a thin presentation layer over the existing `AppComponents` and `WorkflowResult` contracts. Add one pure helper for safe runtime badges, reshape only the rendering order and CSS, and keep all provider, SQL guard, database, configuration, and error behavior unchanged.

**Tech Stack:** Python 3.11+, Streamlit, pytest, Streamlit `AppTest`, Ruff, mypy, Git, GitHub CLI.

## Global Constraints

- Use blueprint ink `#10233F`, drafting blue `#2F6BFF`, signal teal `#16A394`, warm paper `#F7F5F0`, panel white `#FFFFFF`, and rule gray `#D8DEE9`.
- Use `Aptos Display`/`Segoe UI` for display text, `Aptos`/`Segoe UI` for body text, and `Cascadia Code`/system monospace for utility text.
- Do not change Text-to-SQL workflow behavior, security boundaries, provider behavior, or runtime configuration.
- Render result content only from `WorkflowResult`; never expose raw provider responses, secret values, local paths, or unexpected exception details.
- Keep visible labels, keyboard focus, responsive stacking, and reduced-motion support.
- Capture the public screenshot in deterministic offline fake mode with a reviewed question and completed result.
- Never track `.env`, `.venv`, local databases, logs, caches, secrets, or Gemini output.

---

### Task 1: Define the safe Blueprint UI contract with failing tests

**Files:**
- Modify: `tests/unit/test_ui_helpers.py`
- Modify: `tests/integration/test_streamlit_app.py`

**Interfaces:**
- Consumes: `Settings`, `render_app()`, and the offline `AppTest` fixture pattern.
- Produces: expected public interface for `safe_runtime_badges(settings, example_count, database_ready) -> tuple[str, ...]` and the new Streamlit copy/layout.

- [ ] **Step 1: Add a failing unit test for safe runtime badges**

```python
from safe_text_to_sql.ui import safe_runtime_badges


def test_runtime_badges_are_safe_and_reviewer_friendly() -> None:
    private_path = "private/local/demo.sqlite"
    private_key = "dummy-private-key"
    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": private_key,
            "DATABASE_PATH": private_path,
        }
    )

    badges = safe_runtime_badges(
        settings,
        example_count=25,
        database_ready=True,
    )

    assert badges == (
        "Gemini · gemini-2.5-flash",
        "SQLite · read-only",
        "25 reviewed examples",
        "Database ready",
    )
    assert private_path not in repr(badges)
    assert private_key not in repr(badges)
```

- [ ] **Step 2: Add failing integration expectations for the redesigned shell**

Update `test_streamlit_app_renders_safe_offline_workbench` to assert:

```python
assert app.title[0].value == "Safe Text-to-SQL"
assert any(
    "Ask questions. Inspect the query. Trust the boundary." in item.value for item in app.markdown
)
assert any(button.label == "Generate guarded answer" for button in app.button)
for phase in ("Generate", "Guard", "Execute", "Answer"):
    assert phase in rendered
```

- [ ] **Step 3: Add a failing completed-workflow integration test**

```python
def test_streamlit_app_renders_grounded_result_from_reviewed_question(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_path = tmp_path / "demo.sqlite"
    initialize_database(database_path)
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    app = AppTest.from_file("app.py", default_timeout=20)
    app.run()
    app.selectbox[0].select("Find the top 5 customers by total spending")
    app.button(key="FormSubmitter:analytics_question-Generate guarded answer").click()
    app.run()

    assert not app.exception
    rendered = " ".join(item.value for item in app.markdown)
    assert "Grounded answer" in rendered
    assert "Validation passed" in rendered
    assert len(app.dataframe) == 1
    assert len(app.code) == 1
```

- [ ] **Step 4: Run the focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ui_helpers.py tests/integration/test_streamlit_app.py -v
```

Expected: failures for the missing `safe_runtime_badges`, old title/button copy, and old result order.

---

### Task 2: Implement the Blueprint shell and result hierarchy

**Files:**
- Modify: `src/safe_text_to_sql/ui.py`
- Modify: `.streamlit/config.toml`
- Test: `tests/unit/test_ui_helpers.py`
- Test: `tests/integration/test_streamlit_app.py`

**Interfaces:**
- Consumes: the failing contract from Task 1 and existing `Settings`, `AppComponents`, and `WorkflowResult`.
- Produces: `safe_runtime_badges(settings, *, example_count, database_ready) -> tuple[str, ...]`, Blueprint CSS, and the redesigned Streamlit render tree.

- [ ] **Step 1: Implement the pure runtime-badge helper**

```python
def safe_runtime_badges(
    settings: Settings,
    *,
    example_count: int,
    database_ready: bool,
) -> tuple[str, ...]:
    provider = (
        f"Gemini · {settings.gemini_model}"
        if settings.llm_provider is LLMProviderMode.GEMINI
        else "Offline demo · deterministic"
    )
    return (
        provider,
        "SQLite · read-only",
        f"{example_count} reviewed examples",
        "Database ready" if database_ready else "Database unavailable",
    )
```

- [ ] **Step 2: Replace the generic page CSS with the approved token system**

Implement:

- A maximum readable content width and responsive side padding.
- A light blueprint canvas with one restrained grid treatment.
- A dark `.query-console` visual region around the form.
- A connected four-node `.trust-rail` that never exceeds the content width.
- Status chips, an answer callout, compact evidence cards, strong focus styles, and responsive breakpoints at 900px and 640px.
- `@media (prefers-reduced-motion: reduce)` that disables nonessential transitions.

- [ ] **Step 3: Reshape the application header and runtime hierarchy**

Render:

```text
SAFE TEXT-TO-SQL / GUARDED ANALYTICS
Safe Text-to-SQL
Ask questions. Inspect the query. Trust the boundary.
[provider] [SQLite · read-only] [25 reviewed examples] [Database ready]
Generate ─ Guard ─ Execute ─ Answer
```

Keep the sidebar for the detailed safe summary and reset action, but reduce its visual weight.

- [ ] **Step 4: Reshape the query form without changing submission behavior**

Keep the existing selectbox, text area, safe database-disable behavior, and sample fallback. Change only the visible action label to `Generate guarded answer` and wrap the form with Blueprint-specific structure and copy.

- [ ] **Step 5: Reorder successful output for reviewer scanning**

Render in this order:

1. `Grounded answer` callout from `result.answer.answer`.
2. `Validation passed` and the existing validation summary.
3. Result dataframe and truncation notice.
4. Expanded-by-default `SQL evidence` area containing the validated SQL.
5. Collapsed technical details with request reference and safe counters.

- [ ] **Step 6: Align Streamlit theme tokens**

Set `.streamlit/config.toml` to:

```toml
[theme]
base = "light"
primaryColor = "#2F6BFF"
backgroundColor = "#F7F5F0"
secondaryBackgroundColor = "#EEF2F7"
textColor = "#10233F"
font = "sans-serif"
```

- [ ] **Step 7: Run focused tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ui_helpers.py tests/integration/test_streamlit_app.py -v
```

Expected: all focused tests pass.

- [ ] **Step 8: Run static checks for changed Python files**

Run:

```powershell
.\.venv\Scripts\ruff.exe check src/safe_text_to_sql/ui.py tests/unit/test_ui_helpers.py tests/integration/test_streamlit_app.py
.\.venv\Scripts\ruff.exe format --check src/safe_text_to_sql/ui.py tests/unit/test_ui_helpers.py tests/integration/test_streamlit_app.py
.\.venv\Scripts\mypy.exe src tests scripts app.py
```

Expected: exit code 0 for all commands.

- [ ] **Step 9: Commit the tested UI**

```powershell
git add -- src/safe_text_to_sql/ui.py .streamlit/config.toml tests/unit/test_ui_helpers.py tests/integration/test_streamlit_app.py
git commit -m "Redesign Streamlit blueprint workbench"
```

---

### Task 3: Perform live visual QA and capture the reproducible screenshot

**Files:**
- Modify if visual defects are found: `src/safe_text_to_sql/ui.py`
- Replace: `assets/screenshots/workbench.png`

**Interfaces:**
- Consumes: the offline Streamlit application and reviewed fake-provider examples.
- Produces: a verified desktop screenshot with a completed guarded query and no secret-bearing runtime.

- [ ] **Step 1: Start a dedicated offline screenshot server**

Run with process-local environment overrides:

```powershell
$env:LLM_PROVIDER = "fake"
$env:DATABASE_PATH = "data/demo/chinook_demo.sqlite"
$env:LOG_LEVEL = "ERROR"
.\.venv\Scripts\streamlit.exe run app.py --server.port 8502 --server.headless true
```

- [ ] **Step 2: Verify server health**

Run:

```powershell
Invoke-WebRequest http://127.0.0.1:8502/_stcore/health -UseBasicParsing
```

Expected: HTTP 200 with `ok`.

- [ ] **Step 3: Inspect desktop layout in the browser**

At 1440×1000, verify the masthead, four trust nodes, complete query console, and runtime chips fit without horizontal clipping.

- [ ] **Step 4: Exercise a reviewed question**

Select `Find the top 5 customers by total spending`, submit `Generate guarded answer`, and verify the answer, validation facts, table, and SQL evidence render.

- [ ] **Step 5: Inspect responsive layout**

At approximately 390×844, verify controls stack, labels remain visible, no horizontal overflow appears, and the trust rail becomes one column.

- [ ] **Step 6: Fix only observed visual defects and rerun focused checks**

For any CSS-only correction, rerun:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ui_helpers.py tests/integration/test_streamlit_app.py -q
.\.venv\Scripts\ruff.exe check src/safe_text_to_sql/ui.py
```

- [ ] **Step 7: Capture the final desktop screenshot**

Save the browser screenshot directly to `assets/screenshots/workbench.png` at a stable desktop viewport. Confirm it contains offline fake mode, safe synthetic data only, a successful result, no local filesystem path, and no API key.

- [ ] **Step 8: Inspect the saved image**

Open the tracked PNG and verify legibility, cropping, and absence of secret or client content.

---

### Task 4: Update repository presentation, verify release, and publish

**Files:**
- Modify: `README.md`
- Replace: `assets/screenshots/workbench.png`
- Include: `docs/superpowers/plans/2026-07-29-streamlit-blueprint-workbench.md`

**Interfaces:**
- Consumes: the verified screenshot and existing README.
- Produces: a clean, tested Git commit and updated public GitHub repository.

- [ ] **Step 1: Update screenshot context in the README**

Keep the existing relative image URL and add one factual sentence:

```markdown
The screenshot shows the deterministic offline workflow with a reviewed question,
AST validation, read-only execution, and a grounded answer.
```

- [ ] **Step 2: Run the complete local quality gate**

Run:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests scripts app.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/run_evaluation.py
.\.venv\Scripts\python.exe scripts/verify_release.py
```

Expected: every command exits 0 without weakening any check.

- [ ] **Step 3: Inspect the final diff and tracked-file safety**

Run:

```powershell
git diff --check
git status -sb
git diff --stat main...HEAD
git ls-files
```

Confirm no tracked `.env`, `.venv`, `legacy_reference`, `.migration`, cache, database, log, key, credential, or generated evaluation result is present.

- [ ] **Step 4: Commit the screenshot and repository presentation**

```powershell
git add -- README.md assets/screenshots/workbench.png docs/superpowers/plans/2026-07-29-streamlit-blueprint-workbench.md
git commit -m "Refresh workbench portfolio presentation"
```

- [ ] **Step 5: Verify GitHub authentication and remote scope**

Run:

```powershell
gh --version
gh auth status
git remote -v
gh repo view Abdo1119/safe-text-to-sql --json nameWithOwner,defaultBranchRef,url
```

Confirm the only push target is `Abdo1119/safe-text-to-sql`.

- [ ] **Step 6: Push the reviewed branch**

```powershell
git push -u origin agent/blueprint-workbench
```

- [ ] **Step 7: Publish the approved update to `main`**

Create the GitHub change for `agent/blueprint-workbench` against `main`, verify its checks, then merge without force-pushing. Pull the resulting `main` and verify that the README references the replaced screenshot.

- [ ] **Step 8: Verify the public repository and CI**

Check the public README, screenshot URL, final `main` commit, and GitHub Actions conclusion. If CI fails because of the project, diagnose and fix it without weakening tests, Ruff, mypy, security checks, or secret scanning.

