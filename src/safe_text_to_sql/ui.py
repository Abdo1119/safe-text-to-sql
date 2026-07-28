"""Professional Streamlit workbench and safe presentation helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import streamlit as st

from safe_text_to_sql.bootstrap import AppComponents
from safe_text_to_sql.config import LLMProviderMode, Settings
from safe_text_to_sql.database.sqlite import DatabaseError
from safe_text_to_sql.models import QueryResult, ValidatedSQLQuery, WorkflowResult
from safe_text_to_sql.service import ServiceError

_SAMPLE_QUESTIONS = (
    "How many customers are in the USA?",
    "Find the top 5 customers by total spending",
    "Which country generated the highest revenue?",
    "Count how many tracks exist in each genre",
    "Find the hierarchy depth for each employee",
)

_CSS = """
<style>
:root {
  --ink: #132238;
  --muted: #5e6b7a;
  --cobalt: #335cff;
  --cyan: #0f9f92;
  --paper: #ffffff;
  --canvas: #f5f7fb;
  --line: #dce3ee;
}
.stApp {
  background:
    radial-gradient(circle at 88% 8%, rgba(51, 92, 255, 0.08), transparent 25rem),
    var(--canvas);
  color: var(--ink);
}
html, body, [class*="css"] {
  font-family: "Aptos", "Segoe UI", sans-serif;
}
h1, h2, h3 {
  color: var(--ink);
  letter-spacing: -0.035em;
}
[data-testid="stSidebar"] {
  background: #edf1f8;
  border-right: 1px solid var(--line);
}
.workbench-kicker {
  color: var(--cobalt);
  font: 700 0.72rem/1.2 "Cascadia Code", monospace;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.trust-trace {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.55rem;
  margin: 1.25rem 0 1.5rem;
}
.trace-step {
  background: var(--paper);
  border: 1px solid var(--line);
  border-top: 3px solid var(--cyan);
  border-radius: 0.65rem;
  color: var(--ink);
  padding: 0.7rem 0.8rem;
  box-shadow: 0 8px 24px rgba(19, 34, 56, 0.05);
}
.trace-step b {
  display: block;
  font: 700 0.74rem/1.3 "Cascadia Code", monospace;
  margin-bottom: 0.15rem;
}
.trace-step span {
  color: var(--muted);
  font-size: 0.78rem;
}
[data-testid="stForm"] {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  padding: 1rem 1.1rem 0.45rem;
  box-shadow: 0 12px 36px rgba(19, 34, 56, 0.06);
}
.stButton > button, [data-testid="stFormSubmitButton"] button {
  border-radius: 0.55rem;
  font-weight: 700;
}
.stButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"] {
  background: var(--cobalt);
  border-color: var(--cobalt);
}
code, pre {
  font-family: "Cascadia Code", "SFMono-Regular", monospace !important;
}
@media (max-width: 760px) {
  .trust-trace { grid-template-columns: 1fr 1fr; }
}
</style>
"""


def safe_configuration_summary(
    settings: Settings,
    *,
    example_count: int,
) -> dict[str, str]:
    """Return display-safe configuration labels only."""

    provider = "Gemini" if settings.llm_provider is LLMProviderMode.GEMINI else "Fake (offline)"
    model = (
        settings.gemini_model
        if settings.llm_provider is LLMProviderMode.GEMINI
        else "Deterministic presets"
    )
    return {
        "Provider": provider,
        "Model": model,
        "Database": "Synthetic music store · read-only",
        "Row cap": str(settings.max_returned_rows),
        "Repair attempts": str(settings.max_repair_attempts),
        "Examples": f"{example_count} reviewed / top {settings.example_top_k}",
    }


def validation_summary(
    query: ValidatedSQLQuery,
    *,
    repair_attempts: int,
) -> dict[str, str]:
    """Summarize guard decisions without exposing internal objects."""

    if query.limit_was_added:
        row_limit = f"Added ({query.effective_limit})"
    elif query.limit_was_clamped:
        row_limit = f"Clamped ({query.effective_limit})"
    else:
        row_limit = f"Preserved ({query.effective_limit})"
    tables = ", ".join(query.referenced_tables) or "No physical tables"
    return {
        "Policy": "Passed",
        "Row limit": row_limit,
        "Repair attempts": str(repair_attempts),
        "Tables": tables,
    }


def safe_error_message(error: ServiceError) -> str:
    """Attach a safe support reference to an already-sanitized service error."""

    return f"{error} Reference: {error.request_id} ({error.code.value})."


def render_app(
    settings: Settings,
    components: AppComponents,
) -> None:
    """Render the complete interactive workbench."""

    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="workbench-kicker">Guardrailed analytics workbench</div>',
        unsafe_allow_html=True,
    )
    st.title("Ask the music store")
    mode_caption = (
        f"Gemini · {settings.gemini_model}"
        if settings.llm_provider is LLMProviderMode.GEMINI
        else "Offline fake mode"
    )
    st.caption(f"{mode_caption} · {components.example_count} reviewed examples · read-only SQLite")
    st.markdown(
        """
        <div class="trust-trace">
          <div class="trace-step">
            <b>01 · GENERATE</b><span>Gemini or deterministic fake</span>
          </div>
          <div class="trace-step"><b>02 · GUARD</b><span>SQLGlot AST policy</span></div>
          <div class="trace-step"><b>03 · EXECUTE</b><span>Read-only SQLite</span></div>
          <div class="trace-step"><b>04 · ANSWER</b><span>Grounded in returned rows</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    database_ready, database_message = _database_status(components)
    with st.sidebar:
        st.subheader("Runtime")
        summary = safe_configuration_summary(
            settings,
            example_count=components.example_count,
        )
        for label, value in summary.items():
            st.caption(label)
            st.write(value)
        st.divider()
        if database_ready:
            st.success("Database ready")
        else:
            st.warning(database_message)
        if st.button("Reset session", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    with st.form("analytics_question"):
        sample = st.selectbox(
            "Try a reviewed question",
            ("Write my own question", *_SAMPLE_QUESTIONS),
        )
        question = st.text_area(
            "Analytics question",
            placeholder="For example: Which country generated the highest revenue?",
            max_chars=settings.max_question_chars,
            height=110,
        )
        submitted = st.form_submit_button(
            "Run guarded query",
            type="primary",
            disabled=not database_ready,
            use_container_width=True,
        )

    if submitted:
        selected_question = question.strip() or (
            sample if sample != "Write my own question" else ""
        )
        with st.status("Running the guarded workflow…", expanded=True) as status:
            st.write("Selecting reviewed examples and generating SQL")
            try:
                result = asyncio.run(components.service.ask(selected_question))
            except ServiceError as exc:
                status.update(label="Request stopped safely", state="error")
                st.error(safe_error_message(exc))
            else:
                status.update(label="Validated query completed", state="complete")
                st.session_state["workflow_result"] = result

    stored_result = st.session_state.get("workflow_result")
    if isinstance(stored_result, WorkflowResult):
        _render_result(stored_result)


def _database_status(components: AppComponents) -> tuple[bool, str]:
    try:
        return components.repository.healthcheck(), "Database ready"
    except DatabaseError:
        return False, "Initialize the local demo database before running a query."


def _render_result(result: WorkflowResult) -> None:
    st.subheader("Validated SQL")
    st.code(result.validated_query.sql, language="sql")

    summary = validation_summary(
        result.validated_query,
        repair_attempts=result.repair_attempts,
    )
    columns = st.columns(4)
    for column, (label, value) in zip(columns, summary.items(), strict=True):
        column.metric(label, value)

    st.subheader("Result")
    st.dataframe(
        _result_records(result.query_result),
        use_container_width=True,
        hide_index=True,
    )
    if result.query_result.truncated:
        st.info("The displayed result was capped by the configured row policy.")

    st.subheader("Answer")
    st.markdown(result.answer.answer)

    with st.expander("Technical details"):
        st.write(f"Request reference: `{result.request_id}`")
        st.write(f"Provider mode: `{result.candidate.provider}`")
        st.write(f"Selected examples: `{len(result.selected_examples)}`")
        st.write(f"Repair attempts: `{result.repair_attempts}`")
        st.write("Validation: `passed`")


def _result_records(result: QueryResult) -> list[Mapping[str, Any]]:
    return [dict(zip(result.columns, row, strict=True)) for row in result.rows]
