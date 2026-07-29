"""Professional Streamlit workbench and safe presentation helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from html import escape
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
  --blueprint-ink: #10233f;
  --drafting-blue: #2f6bff;
  --signal-teal: #16a394;
  --warm-paper: #f7f5f0;
  --panel-white: #ffffff;
  --rule-gray: #d8dee9;
  --muted-ink: #667085;
  --soft-blue: #eef3ff;
}
.stApp {
  background:
    linear-gradient(rgba(16, 35, 63, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(16, 35, 63, 0.025) 1px, transparent 1px),
    var(--warm-paper);
  background-size: 32px 32px;
  color: var(--blueprint-ink);
}
html, body, [class*="css"] {
  font-family: "Aptos", "Segoe UI", sans-serif;
}
.main .block-container {
  max-width: 1180px;
  padding-top: 2.6rem;
  padding-bottom: 5rem;
}
h1, h2, h3 {
  color: var(--blueprint-ink);
  font-family: "Aptos Display", "Segoe UI", sans-serif;
  letter-spacing: -0.045em;
}
h1 {
  font-size: clamp(2.7rem, 5vw, 4.8rem) !important;
  font-weight: 750 !important;
  line-height: 0.95 !important;
  margin: 0.55rem 0 0.9rem !important;
}
[data-testid="stSidebar"] {
  background: #eef2f6;
  border-right: 1px solid var(--rule-gray);
}
[data-testid="stSidebar"] > div:first-child {
  width: 17.5rem;
}
[data-testid="stSidebar"] h2 {
  font-size: 1.25rem;
  letter-spacing: -0.02em;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
  color: #7a8494;
  font: 700 0.68rem/1.2 "Cascadia Code", monospace;
  letter-spacing: 0.08em;
  margin-top: 0.5rem;
  text-transform: uppercase;
}
.blueprint-kicker {
  align-items: center;
  color: var(--drafting-blue);
  display: flex;
  font: 700 0.7rem/1.2 "Cascadia Code", monospace;
  gap: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.blueprint-kicker::before {
  background: var(--drafting-blue);
  content: "";
  display: inline-block;
  height: 2px;
  width: 2.4rem;
}
.hero-deck {
  color: #526174;
  font-size: clamp(1rem, 1.8vw, 1.22rem);
  line-height: 1.6;
  margin: 0 0 1.2rem;
  max-width: 42rem;
}
.status-rack {
  display: flex;
  flex-wrap: wrap;
  gap: 0.48rem;
  margin: 0 0 1.6rem;
}
.status-chip {
  align-items: center;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--rule-gray);
  border-radius: 999px;
  color: #455267;
  display: inline-flex;
  font: 650 0.72rem/1 "Cascadia Code", monospace;
  gap: 0.48rem;
  padding: 0.58rem 0.78rem;
}
.status-chip::before {
  background: var(--signal-teal);
  border-radius: 999px;
  box-shadow: 0 0 0 3px rgba(22, 163, 148, 0.12);
  content: "";
  height: 0.42rem;
  width: 0.42rem;
}
.trust-shell {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--rule-gray);
  border-radius: 1rem;
  box-shadow: 0 18px 45px rgba(16, 35, 63, 0.06);
  margin: 0 0 1.25rem;
  padding: 0.8rem;
}
.trust-rail {
  display: grid;
  gap: 0;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  width: 100%;
}
.trust-node {
  min-width: 0;
  padding: 0.65rem 0.85rem;
  position: relative;
}
.trust-node:not(:last-child)::after {
  background: var(--rule-gray);
  content: "";
  height: 1px;
  position: absolute;
  right: -0.3rem;
  top: 1.18rem;
  width: 0.6rem;
  z-index: 1;
}
.trust-index {
  align-items: center;
  background: var(--soft-blue);
  border: 1px solid #cbd8ff;
  border-radius: 50%;
  color: var(--drafting-blue);
  display: inline-flex;
  font: 700 0.65rem/1 "Cascadia Code", monospace;
  height: 1.65rem;
  justify-content: center;
  margin-right: 0.45rem;
  width: 1.65rem;
}
.trust-node b {
  color: var(--blueprint-ink);
  font-size: 0.82rem;
}
.trust-node p {
  color: var(--muted-ink);
  font-size: 0.72rem;
  line-height: 1.4;
  margin: 0.35rem 0 0 2.15rem;
}
.query-intro {
  align-items: end;
  display: flex;
  justify-content: space-between;
  margin: 1.9rem 0 0.65rem;
}
.query-intro h2 {
  font-size: 1.25rem;
  letter-spacing: -0.02em;
  margin: 0;
}
.query-intro span {
  color: #7a8494;
  font: 700 0.66rem/1.2 "Cascadia Code", monospace;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
[data-testid="stForm"] {
  background:
    radial-gradient(circle at 96% 0%, rgba(47, 107, 255, 0.22), transparent 18rem),
    var(--blueprint-ink);
  border: 1px solid #1d3a61;
  border-radius: 1rem;
  box-shadow: 0 24px 55px rgba(16, 35, 63, 0.18);
  padding: 1.15rem 1.2rem 0.65rem;
}
[data-testid="stForm"] label p,
[data-testid="stForm"] [data-testid="stWidgetLabel"] p {
  color: #e9eff7 !important;
  font-weight: 650;
}
[data-testid="stForm"] [data-baseweb="select"] > div,
[data-testid="stForm"] textarea {
  background: rgba(255, 255, 255, 0.96) !important;
  border-color: rgba(255, 255, 255, 0.2) !important;
  color: var(--blueprint-ink) !important;
}
[data-testid="stForm"] textarea:focus,
[data-testid="stForm"] [data-baseweb="select"] > div:focus-within {
  border-color: #8caaff !important;
  box-shadow: 0 0 0 3px rgba(140, 170, 255, 0.22) !important;
}
.stButton > button, [data-testid="stFormSubmitButton"] button {
  border-radius: 0.55rem;
  font-weight: 700;
  min-height: 2.75rem;
}
[data-testid="stFormSubmitButton"] button[kind="primary"] {
  background: var(--drafting-blue);
  border-color: var(--drafting-blue);
  box-shadow: 0 10px 24px rgba(47, 107, 255, 0.3);
}
[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
  background: #2459dc;
  border-color: #2459dc;
  transform: translateY(-1px);
}
button:focus-visible,
textarea:focus-visible,
[role="combobox"]:focus-visible {
  outline: 3px solid rgba(47, 107, 255, 0.34) !important;
  outline-offset: 2px;
}
.result-kicker {
  color: var(--signal-teal);
  font: 700 0.68rem/1.2 "Cascadia Code", monospace;
  letter-spacing: 0.12em;
  margin-top: 2.2rem;
  text-transform: uppercase;
}
.answer-card {
  background: var(--panel-white);
  border: 1px solid var(--rule-gray);
  border-left: 4px solid var(--signal-teal);
  border-radius: 0.85rem;
  box-shadow: 0 16px 38px rgba(16, 35, 63, 0.07);
  margin: 0.55rem 0 1.35rem;
  padding: 1.15rem 1.25rem;
}
.answer-card p {
  color: var(--blueprint-ink);
  font-size: 1.08rem;
  line-height: 1.6;
  margin: 0;
}
.validation-heading {
  align-items: center;
  color: var(--blueprint-ink);
  display: flex;
  font-size: 1rem;
  font-weight: 750;
  gap: 0.55rem;
  margin: 1.5rem 0 0.45rem;
}
.validation-heading::before {
  align-items: center;
  background: rgba(22, 163, 148, 0.12);
  border-radius: 50%;
  color: var(--signal-teal);
  content: "✓";
  display: inline-flex;
  font-size: 0.72rem;
  height: 1.55rem;
  justify-content: center;
  width: 1.55rem;
}
[data-testid="stMetric"] {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--rule-gray);
  border-radius: 0.7rem;
  min-height: 5.4rem;
  padding: 0.7rem 0.8rem;
}
[data-testid="stMetricLabel"] {
  color: var(--muted-ink);
  font: 700 0.65rem/1.2 "Cascadia Code", monospace;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
[data-testid="stMetricValue"] {
  font-size: clamp(1.05rem, 1.8vw, 1.45rem);
  line-height: 1.2;
  white-space: normal;
}
[data-testid="stDataFrame"] {
  border: 1px solid var(--rule-gray);
  border-radius: 0.75rem;
  overflow: hidden;
}
[data-testid="stExpander"] {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--rule-gray) !important;
  border-radius: 0.75rem !important;
}
code, pre {
  font-family: "Cascadia Code", "SFMono-Regular", monospace !important;
}
@media (max-width: 900px) {
  .main .block-container { padding-top: 2rem; }
  .trust-rail { grid-template-columns: 1fr 1fr; }
  .trust-node:nth-child(2)::after { display: none; }
}
@media (max-width: 640px) {
  .main .block-container {
    padding-left: 1rem;
    padding-right: 1rem;
  }
  h1 { font-size: 2.65rem !important; }
  .trust-rail { grid-template-columns: 1fr; }
  .trust-node::after { display: none; }
  .query-intro {
    align-items: start;
    flex-direction: column;
    gap: 0.35rem;
  }
  [data-testid="stForm"] { padding: 1rem 0.85rem 0.55rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    transition: none !important;
  }
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


def safe_runtime_badges(
    settings: Settings,
    *,
    example_count: int,
    database_ready: bool,
) -> tuple[str, ...]:
    """Return compact runtime labels without paths, credentials, or internal objects."""

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


def safe_unexpected_error_message(_error: Exception) -> str:
    """Return a constant boundary message without rendering exception details."""

    return "The request could not be completed safely. Try again."


def render_app(
    settings: Settings,
    components: AppComponents,
    *,
    database_created: bool = False,
) -> None:
    """Render the complete interactive workbench."""

    st.markdown(_CSS, unsafe_allow_html=True)
    database_ready, database_message = _database_status(components)
    st.markdown(
        '<div class="blueprint-kicker">Guarded analytics / music intelligence</div>',
        unsafe_allow_html=True,
    )
    st.title("Safe Text-to-SQL")
    st.markdown(
        '<p class="hero-deck">Ask questions. Inspect the query. Trust the boundary.</p>',
        unsafe_allow_html=True,
    )
    badges = safe_runtime_badges(
        settings,
        example_count=components.example_count,
        database_ready=database_ready,
    )
    rendered_badges = "".join(
        f'<span class="status-chip">{escape(badge)}</span>' for badge in badges
    )
    st.markdown(
        f'<div class="status-rack">{rendered_badges}</div>',
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown("### Safe Text-to-SQL")
        st.caption("Runtime controls")
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
            if database_created:
                st.caption("Synthetic demo data was generated for this deployment.")
        else:
            st.warning(database_message)
        if st.button("Reset session", width="stretch"):
            st.session_state.clear()
            st.rerun()

    st.markdown(
        """
        <div class="query-intro">
          <h2>Query the music store</h2>
          <span>Natural language → guarded SQL</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("analytics_question"):
        sample = st.selectbox(
            "Start with a reviewed question",
            ("Write my own question", *_SAMPLE_QUESTIONS),
        )
        question = st.text_area(
            "Or ask your own analytics question",
            placeholder="For example: Which country generated the highest revenue?",
            max_chars=settings.max_question_chars,
            height=110,
            help="Enter adds a new line. Use the button below, or Ctrl+Enter, to submit.",
        )
        submitted = st.form_submit_button(
            "Run guarded query",
            type="primary",
            disabled=not database_ready,
            width="stretch",
        )
        if not database_ready:
            st.caption(database_message)

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
            except Exception as exc:
                status.update(label="Request stopped safely", state="error")
                st.error(safe_unexpected_error_message(exc))
            else:
                status.update(label="Validated query completed", state="complete")
                st.session_state["workflow_result"] = result

    stored_result = st.session_state.get("workflow_result")
    if isinstance(stored_result, WorkflowResult):
        _render_result(stored_result)

    # Rendered after the form so the submit control stays above the fold.
    st.markdown(
        """
        <div class="trust-shell">
          <div class="trust-rail">
            <div class="trust-node">
              <span class="trust-index">01</span><b>Generate</b>
              <p>Model proposes one query</p>
            </div>
            <div class="trust-node">
              <span class="trust-index">02</span><b>Guard</b>
              <p>SQLGlot validates the AST</p>
            </div>
            <div class="trust-node">
              <span class="trust-index">03</span><b>Execute</b>
              <p>SQLite stays read-only</p>
            </div>
            <div class="trust-node">
              <span class="trust-index">04</span><b>Answer</b>
              <p>Response uses returned rows</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _database_status(components: AppComponents) -> tuple[bool, str]:
    try:
        return components.repository.healthcheck(), "Database ready"
    except DatabaseError:
        return False, "The demo database is unavailable, so queries are disabled."


def _render_result(result: WorkflowResult) -> None:
    st.markdown('<div class="result-kicker">Grounded answer</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="answer-card"><p>{escape(result.answer.answer)}</p></div>',
        unsafe_allow_html=True,
    )

    summary = validation_summary(
        result.validated_query,
        repair_attempts=result.repair_attempts,
    )
    st.markdown(
        '<div class="validation-heading">Validation passed</div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(4)
    for column, (label, value) in zip(columns, summary.items(), strict=True):
        column.metric(label, value)

    st.subheader("Result rows")
    st.dataframe(
        _result_records(result.query_result),
        width="stretch",
        hide_index=True,
    )
    if result.query_result.truncated:
        st.info("The displayed result was capped by the configured row policy.")

    with st.expander("SQL evidence", expanded=True):
        st.code(result.validated_query.sql, language="sql")

    with st.expander("Technical details"):
        st.write(f"Request reference: `{result.request_id}`")
        st.write(f"Provider mode: `{result.candidate.provider}`")
        st.write(f"Selected examples: `{len(result.selected_examples)}`")
        st.write(f"Repair attempts: `{result.repair_attempts}`")
        st.write("Validation: `passed`")


def _result_records(result: QueryResult) -> list[Mapping[str, Any]]:
    return [dict(zip(result.columns, row, strict=True)) for row in result.rows]
