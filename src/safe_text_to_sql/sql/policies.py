"""Configuration for SQL validation and row limiting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExcessiveLimitPolicy(StrEnum):
    """How to handle a literal LIMIT above the configured maximum."""

    CLAMP = "clamp"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class SQLPolicy:
    """Application-layer SQL restrictions.

    This policy is defense in depth, not a database security boundary. The
    final system must also use a dedicated read-only PostgreSQL role,
    read-only transactions, a statement timeout, and database permissions.
    """

    allowed_schemas: frozenset[str] = frozenset({"public"})
    allowed_tables: frozenset[str] | None = None
    max_rows: int = 100
    excessive_limit: ExcessiveLimitPolicy = ExcessiveLimitPolicy.CLAMP

    def __post_init__(self) -> None:
        if self.max_rows <= 0:
            raise ValueError("max_rows must be positive.")
        object.__setattr__(
            self,
            "allowed_schemas",
            frozenset(schema.strip().casefold() for schema in self.allowed_schemas),
        )
        if self.allowed_tables is not None:
            object.__setattr__(
                self,
                "allowed_tables",
                frozenset(table.strip().casefold() for table in self.allowed_tables),
            )
