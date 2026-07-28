"""Typed database-schema representation for prompting and policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    """One public database column."""

    name: str
    declared_type: str
    nullable: bool
    primary_key: bool

    def render(self) -> str:
        """Render a compact, deterministic prompt representation."""

        parts = [f'"{self.name}"', self.declared_type or "TEXT"]
        if self.primary_key:
            parts.append("PRIMARY KEY")
        elif not self.nullable:
            parts.append("NOT NULL")
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class TableSchema:
    """One public table and its columns."""

    name: str
    columns: tuple[ColumnSchema, ...]


@dataclass(frozen=True, slots=True)
class DatabaseSchema:
    """Immutable public schema used by the guard and providers."""

    tables: tuple[TableSchema, ...]

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(table.name for table in self.tables)

    @property
    def allowed_tables(self) -> frozenset[str]:
        return frozenset(table.name.casefold() for table in self.tables)

    def render_for_prompt(self) -> str:
        """Render tables without local paths, row data, or internal metadata."""

        lines = []
        for table in self.tables:
            columns = ", ".join(column.render() for column in table.columns)
            lines.append(f'"{table.name}" ({columns})')
        return "\n".join(lines)
