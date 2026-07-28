from __future__ import annotations

import pytest

from safe_text_to_sql.models import ValidationErrorCode
from safe_text_to_sql.sql.guard import SQLGuard
from safe_text_to_sql.sql.policies import ExcessiveLimitPolicy, SQLPolicy


def _guard(
    *,
    tables: frozenset[str] | None = None,
    schemas: frozenset[str] = frozenset({"public"}),
    max_rows: int = 100,
    excessive_limit: ExcessiveLimitPolicy = ExcessiveLimitPolicy.CLAMP,
) -> SQLGuard:
    return SQLGuard(
        SQLPolicy(
            allowed_schemas=schemas,
            allowed_tables=tables,
            max_rows=max_rows,
            excessive_limit=excessive_limit,
        )
    )


def _assert_error(sql: str, code: ValidationErrorCode) -> None:
    result = _guard().validate(sql)

    assert not result.is_valid
    assert result.query is None
    assert result.errors[0].code is code


def test_accepts_simple_select_and_adds_limit() -> None:
    result = _guard().validate('SELECT "CustomerId" FROM "Customer"')

    assert result.is_valid
    assert result.query is not None
    assert result.query.effective_limit == 100
    assert result.query.limit_was_added
    assert not result.query.limit_was_clamped
    assert result.query.sql.upper().endswith("LIMIT 100")


def test_accepts_join_with_allowed_tables() -> None:
    guard = _guard(tables=frozenset({"customer", "invoice"}))

    result = guard.validate(
        'SELECT c."CustomerId", i."Total" '
        'FROM "Customer" AS c '
        'JOIN "Invoice" AS i ON i."CustomerId" = c."CustomerId"'
    )

    assert result.is_valid
    assert result.query is not None
    assert result.query.referenced_tables == ("customer", "invoice")


def test_accepts_aggregation() -> None:
    result = _guard().validate('SELECT "Country", COUNT(*) FROM "Customer" GROUP BY "Country"')

    assert result.is_valid


def test_accepts_read_only_cte_and_ignores_cte_alias_for_allowlist() -> None:
    guard = _guard(tables=frozenset({"public.invoice"}))

    result = guard.validate(
        'WITH totals AS (SELECT "Total" FROM public."Invoice") SELECT SUM("Total") FROM totals'
    )

    assert result.is_valid
    assert result.query is not None
    assert result.query.referenced_tables == ("public.invoice",)


def test_accepts_recursive_cte_and_ignores_recursive_alias_for_allowlist() -> None:
    guard = _guard(tables=frozenset({"public.employee"}))

    result = guard.validate(
        "WITH RECURSIVE hierarchy AS ("
        'SELECT "EmployeeId", "ReportsTo" FROM public."Employee" '
        'WHERE "ReportsTo" IS NULL '
        "UNION ALL "
        'SELECT employee."EmployeeId", employee."ReportsTo" '
        'FROM public."Employee" AS employee '
        'JOIN hierarchy ON employee."ReportsTo" = hierarchy."EmployeeId"'
        ') SELECT "EmployeeId" FROM hierarchy'
    )

    assert result.is_valid
    assert result.query is not None
    assert result.query.referenced_tables == ("public.employee",)
    assert result.query.limit_was_added


def test_accepts_window_function() -> None:
    result = _guard().validate(
        'SELECT "CustomerId", RANK() OVER (ORDER BY "Total" DESC) FROM "Invoice"'
    )

    assert result.is_valid


def test_accepts_explicit_allowed_schema_and_table() -> None:
    guard = _guard(tables=frozenset({"analytics.sales"}), schemas=frozenset({"analytics"}))

    result = guard.validate("SELECT amount FROM analytics.sales")

    assert result.is_valid
    assert result.query is not None
    assert result.query.referenced_tables == ("analytics.sales",)


def test_preserves_existing_safe_limit() -> None:
    result = _guard(max_rows=100).validate("SELECT * FROM customer LIMIT 10")

    assert result.is_valid
    assert result.query is not None
    assert result.query.effective_limit == 10
    assert not result.query.limit_was_added
    assert not result.query.limit_was_clamped


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT 1; DELETE FROM customer",
    ],
)
def test_rejects_multiple_statements(sql: str) -> None:
    _assert_error(sql, ValidationErrorCode.MULTIPLE_STATEMENTS)


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("INSERT INTO customer(id) VALUES (1)", ValidationErrorCode.DISALLOWED_STATEMENT),
        ("UPDATE customer SET name = 'x'", ValidationErrorCode.DISALLOWED_STATEMENT),
        ("DELETE FROM customer", ValidationErrorCode.DISALLOWED_STATEMENT),
        ("DROP TABLE customer", ValidationErrorCode.DISALLOWED_STATEMENT),
    ],
)
def test_rejects_non_select_statements(sql: str, code: ValidationErrorCode) -> None:
    _assert_error(sql, code)


def test_rejects_data_modifying_cte() -> None:
    _assert_error(
        "WITH removed AS (DELETE FROM customer RETURNING id) SELECT * FROM removed",
        ValidationErrorCode.DATA_MODIFYING_CTE,
    )


def test_rejects_select_into() -> None:
    _assert_error(
        "SELECT * INTO customer_backup FROM customer",
        ValidationErrorCode.SELECT_INTO,
    )


def test_rejects_for_update() -> None:
    _assert_error(
        "SELECT * FROM customer FOR UPDATE",
        ValidationErrorCode.LOCKING_CLAUSE,
    )


def test_rejects_unauthorized_schema() -> None:
    _assert_error(
        "SELECT * FROM private.customer",
        ValidationErrorCode.UNAUTHORIZED_SCHEMA,
    )


def test_rejects_unauthorized_table() -> None:
    guard = _guard(tables=frozenset({"customer"}))

    result = guard.validate("SELECT * FROM invoice")

    assert not result.is_valid
    assert result.errors[0].code is ValidationErrorCode.UNAUTHORIZED_TABLE


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM pg_catalog.pg_class",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM pg_class",
    ],
)
def test_rejects_system_catalogs_by_default(sql: str) -> None:
    _assert_error(sql, ValidationErrorCode.SYSTEM_CATALOG)


def test_allows_system_catalog_only_when_explicitly_configured() -> None:
    guard = _guard(
        schemas=frozenset({"pg_catalog"}),
        tables=frozenset({"pg_catalog.pg_class"}),
    )

    result = guard.validate("SELECT relname FROM pg_catalog.pg_class")

    assert result.is_valid


def test_rejects_malformed_sql() -> None:
    _assert_error("SELECT * FROM (", ValidationErrorCode.PARSE_ERROR)


def test_clamps_excessive_limit_by_default() -> None:
    result = _guard(max_rows=100).validate("SELECT * FROM customer LIMIT 1000")

    assert result.is_valid
    assert result.query is not None
    assert result.query.effective_limit == 100
    assert result.query.limit_was_clamped
    assert result.query.sql.upper().endswith("LIMIT 100")


def test_can_reject_excessive_limit_by_policy() -> None:
    guard = _guard(
        max_rows=100,
        excessive_limit=ExcessiveLimitPolicy.REJECT,
    )

    result = guard.validate("SELECT * FROM customer LIMIT 1000")

    assert not result.is_valid
    assert result.errors[0].code is ValidationErrorCode.EXCESSIVE_LIMIT


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM customer LIMIT ALL",
        "SELECT * FROM customer LIMIT $1",
        "SELECT * FROM customer LIMIT -1",
    ],
)
def test_rejects_non_literal_or_invalid_limits(sql: str) -> None:
    _assert_error(sql, ValidationErrorCode.INVALID_LIMIT)
