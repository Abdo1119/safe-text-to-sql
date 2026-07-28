"""PostgreSQL-aware, AST-based validation for generated SQL."""

from __future__ import annotations

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from safe_text_to_sql.models import (
    ValidatedSQLQuery,
    ValidationError,
    ValidationErrorCode,
    ValidationResult,
)
from safe_text_to_sql.sql.normalization import (
    SQLNormalizationError,
    normalize_sql,
)
from safe_text_to_sql.sql.policies import ExcessiveLimitPolicy, SQLPolicy

_MUTATING_NODE_KEYS = frozenset(
    {
        "alter",
        "call",
        "command",
        "commit",
        "copy",
        "create",
        "delete",
        "do",
        "drop",
        "execute",
        "grant",
        "insert",
        "merge",
        "revoke",
        "rollback",
        "set",
        "transaction",
        "truncate",
        "update",
        "use",
    }
)
_SYSTEM_SCHEMAS = frozenset({"information_schema", "pg_catalog"})


class SQLGuard:
    """Validate and safely limit one PostgreSQL SELECT statement."""

    def __init__(self, policy: SQLPolicy | None = None) -> None:
        self._policy = policy or SQLPolicy()

    def validate(self, raw_sql: str) -> ValidationResult:
        """Return a structured validation result without executing SQL."""

        try:
            normalized = normalize_sql(raw_sql)
        except SQLNormalizationError:
            return _failure(
                ValidationErrorCode.EMPTY_SQL,
                "SQL output is empty.",
            )

        try:
            parsed = parse(normalized, read="postgres")
        except ParseError:
            return _failure(
                ValidationErrorCode.PARSE_ERROR,
                "SQL could not be parsed as PostgreSQL.",
            )

        statements = [statement for statement in parsed if statement is not None]
        if len(statements) != 1:
            return _failure(
                ValidationErrorCode.MULTIPLE_STATEMENTS,
                "Exactly one SQL statement is required.",
            )

        tree = statements[0]
        if not isinstance(tree, exp.Select):
            return _failure(
                ValidationErrorCode.DISALLOWED_STATEMENT,
                "Only a SELECT or read-only WITH ... SELECT query is permitted.",
            )

        mutating_nodes = [
            node for node in tree.walk() if node.key.casefold() in _MUTATING_NODE_KEYS
        ]
        if mutating_nodes:
            if any(_has_cte_ancestor(node) for node in mutating_nodes):
                return _failure(
                    ValidationErrorCode.DATA_MODIFYING_CTE,
                    "Data-modifying common table expressions are prohibited.",
                )
            return _failure(
                ValidationErrorCode.DISALLOWED_STATEMENT,
                "The query contains a prohibited SQL operation.",
            )

        if tree.find(exp.Into) is not None or tree.args.get("into") is not None:
            return _failure(
                ValidationErrorCode.SELECT_INTO,
                "SELECT INTO is prohibited.",
            )

        if _contains_locking_clause(tree):
            return _failure(
                ValidationErrorCode.LOCKING_CLAUSE,
                "Row-locking clauses are prohibited.",
            )

        table_result = self._validate_tables(tree)
        if isinstance(table_result, ValidationResult):
            return table_result

        limited_tree, effective_limit, added, clamped_or_error = self._apply_limit(tree)
        if isinstance(clamped_or_error, ValidationResult):
            return clamped_or_error

        return ValidationResult.success(
            ValidatedSQLQuery(
                sql=limited_tree.sql(dialect="postgres"),
                referenced_tables=table_result,
                effective_limit=effective_limit,
                limit_was_added=added,
                limit_was_clamped=clamped_or_error,
            )
        )

    def _validate_tables(
        self,
        tree: exp.Select,
    ) -> tuple[str, ...] | ValidationResult:
        cte_names = {
            cte.alias_or_name.casefold() for cte in tree.find_all(exp.CTE) if cte.alias_or_name
        }
        references: set[str] = set()

        for table in tree.find_all(exp.Table):
            name = table.name.casefold()
            schema = table.db.casefold() if table.db else ""
            catalog = table.catalog.casefold() if table.catalog else ""

            if not schema and not catalog and name in cte_names:
                continue

            if (schema in _SYSTEM_SCHEMAS and schema not in self._policy.allowed_schemas) or (
                not schema
                and name.startswith("pg_")
                and "pg_catalog" not in self._policy.allowed_schemas
            ):
                return _failure(
                    ValidationErrorCode.SYSTEM_CATALOG,
                    "System catalogs are not available to this query.",
                )

            if catalog:
                return _failure(
                    ValidationErrorCode.UNAUTHORIZED_SCHEMA,
                    "Catalog-qualified access is not permitted.",
                )

            if schema and schema not in self._policy.allowed_schemas:
                return _failure(
                    ValidationErrorCode.UNAUTHORIZED_SCHEMA,
                    "The query references an unauthorized schema.",
                )

            qualified_name = f"{schema}.{name}" if schema else name
            if self._policy.allowed_tables is not None:
                allowed = self._policy.allowed_tables
                if name not in allowed and qualified_name not in allowed:
                    return _failure(
                        ValidationErrorCode.UNAUTHORIZED_TABLE,
                        "The query references an unauthorized table.",
                    )
            references.add(qualified_name)

        return tuple(sorted(references))

    def _apply_limit(
        self,
        tree: exp.Select,
    ) -> tuple[exp.Select, int, bool, bool | ValidationResult]:
        limited_tree = tree.copy()
        limit_node = limited_tree.args.get("limit")
        if limit_node is None:
            limited_tree.set(
                "limit",
                exp.Limit(expression=exp.Literal.number(self._policy.max_rows)),
            )
            return limited_tree, self._policy.max_rows, True, False

        limit_value = _literal_limit(limit_node)
        if limit_value is None or limit_value < 0:
            return (
                limited_tree,
                self._policy.max_rows,
                False,
                _failure(
                    ValidationErrorCode.INVALID_LIMIT,
                    "LIMIT must be a non-negative integer literal.",
                ),
            )

        if limit_value <= self._policy.max_rows:
            return limited_tree, limit_value, False, False

        if self._policy.excessive_limit is ExcessiveLimitPolicy.REJECT:
            return (
                limited_tree,
                self._policy.max_rows,
                False,
                _failure(
                    ValidationErrorCode.EXCESSIVE_LIMIT,
                    "LIMIT exceeds the configured maximum.",
                ),
            )

        limited_tree.set(
            "limit",
            exp.Limit(expression=exp.Literal.number(self._policy.max_rows)),
        )
        return limited_tree, self._policy.max_rows, False, True


def _has_cte_ancestor(node: exp.Expression) -> bool:
    parent = node.parent
    while parent is not None:
        if isinstance(parent, exp.CTE):
            return True
        parent = parent.parent
    return False


def _contains_locking_clause(tree: exp.Select) -> bool:
    if tree.args.get("locks"):
        return True
    return any(node.key.casefold() == "lock" for node in tree.walk())


def _literal_limit(limit_node: exp.Expression) -> int | None:
    expression = limit_node.args.get("expression")
    if not isinstance(expression, exp.Literal) or expression.is_string:
        return None
    try:
        return int(expression.this)
    except (TypeError, ValueError):
        return None


def _failure(
    code: ValidationErrorCode,
    message: str,
) -> ValidationResult:
    return ValidationResult.failure(ValidationError(code=code, message=message))
