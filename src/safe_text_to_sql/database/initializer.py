"""Create the deterministic synthetic music-store demo database."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

EXPECTED_TABLES = frozenset(
    {
        "Album",
        "Artist",
        "Customer",
        "Employee",
        "Genre",
        "Invoice",
        "InvoiceLine",
        "Track",
    }
)

_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE "Artist" (
    "ArtistId" INTEGER PRIMARY KEY,
    "Name" TEXT NOT NULL
);
CREATE TABLE "Album" (
    "AlbumId" INTEGER PRIMARY KEY,
    "Title" TEXT NOT NULL,
    "ArtistId" INTEGER NOT NULL REFERENCES "Artist" ("ArtistId")
);
CREATE TABLE "Genre" (
    "GenreId" INTEGER PRIMARY KEY,
    "Name" TEXT NOT NULL
);
CREATE TABLE "Track" (
    "TrackId" INTEGER PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "AlbumId" INTEGER NOT NULL REFERENCES "Album" ("AlbumId"),
    "GenreId" INTEGER NOT NULL REFERENCES "Genre" ("GenreId"),
    "Milliseconds" INTEGER NOT NULL,
    "UnitPrice" REAL NOT NULL
);
CREATE TABLE "Employee" (
    "EmployeeId" INTEGER PRIMARY KEY,
    "FirstName" TEXT NOT NULL,
    "LastName" TEXT NOT NULL,
    "Title" TEXT NOT NULL,
    "ReportsTo" INTEGER REFERENCES "Employee" ("EmployeeId")
);
CREATE TABLE "Customer" (
    "CustomerId" INTEGER PRIMARY KEY,
    "FirstName" TEXT NOT NULL,
    "LastName" TEXT NOT NULL,
    "City" TEXT NOT NULL,
    "Country" TEXT NOT NULL,
    "SupportRepId" INTEGER REFERENCES "Employee" ("EmployeeId")
);
CREATE TABLE "Invoice" (
    "InvoiceId" INTEGER PRIMARY KEY,
    "CustomerId" INTEGER NOT NULL REFERENCES "Customer" ("CustomerId"),
    "InvoiceDate" TEXT NOT NULL,
    "BillingCountry" TEXT NOT NULL,
    "Total" REAL NOT NULL
);
CREATE TABLE "InvoiceLine" (
    "InvoiceLineId" INTEGER PRIMARY KEY,
    "InvoiceId" INTEGER NOT NULL REFERENCES "Invoice" ("InvoiceId"),
    "TrackId" INTEGER NOT NULL REFERENCES "Track" ("TrackId"),
    "UnitPrice" REAL NOT NULL,
    "Quantity" INTEGER NOT NULL
);
"""

_ARTISTS = (
    (1, "Northstar Quartet"),
    (2, "Cairo Transit"),
    (3, "Blue Harbor"),
    (4, "Atlas Echo"),
    (5, "Neon Bazaar"),
)
_ALBUMS = (
    (1, "Midnight Lines", 1),
    (2, "Desert Signals", 2),
    (3, "Tidal Memory", 3),
    (4, "Mountain Radio", 4),
    (5, "Electric Souk", 5),
    (6, "Northern Rooms", 1),
    (7, "After the Ferry", 3),
)
_GENRES = (
    (1, "Rock"),
    (2, "Jazz"),
    (3, "Electronic"),
    (4, "World"),
    (5, "Ambient"),
)
_TRACKS = (
    (1, "Glass Avenue", 1, 2, 248000, 1.29),
    (2, "Last Platform", 1, 2, 305000, 1.29),
    (3, "Signal at Dawn", 2, 4, 221000, 0.99),
    (4, "Copper Sky", 2, 4, 274000, 0.99),
    (5, "Harbor Lights", 3, 1, 263000, 1.29),
    (6, "Low Tide", 3, 1, 318000, 1.29),
    (7, "Thin Air", 4, 5, 356000, 0.99),
    (8, "Weather Station", 4, 5, 289000, 0.99),
    (9, "Neon Courtyard", 5, 3, 242000, 1.49),
    (10, "Market Pulse", 5, 3, 267000, 1.49),
    (11, "Quiet Geometry", 6, 2, 331000, 1.29),
    (12, "Snow Frequency", 6, 5, 298000, 0.99),
    (13, "Breakwater", 7, 1, 251000, 1.29),
    (14, "Return Ticket", 7, 1, 284000, 1.29),
)
_EMPLOYEES = (
    (1, "Lina", "Haddad", "General Manager", None),
    (2, "Omar", "Nasser", "Sales Manager", 1),
    (3, "Salma", "Fathy", "Support Lead", 1),
    (4, "Youssef", "Karim", "Sales Support Agent", 3),
    (5, "Mariam", "Adel", "Sales Support Agent", 3),
    (6, "Daniel", "Moore", "Sales Support Agent", 3),
    (7, "Nora", "Aziz", "Data Analyst", 2),
)
_CUSTOMERS = (
    (1, "Ava", "Turner", "Boston", "USA", 4),
    (2, "Noah", "Williams", "Seattle", "USA", 5),
    (3, "Emma", "Roy", "Toronto", "Canada", 4),
    (4, "Liam", "Martin", "Montreal", "Canada", 6),
    (5, "Maya", "Patel", "London", "United Kingdom", 5),
    (6, "Lucas", "Bernard", "Paris", "France", 6),
    (7, "Sofia", "Rossi", "Milan", "Italy", 4),
    (8, "Yara", "Hassan", "Cairo", "Egypt", 5),
    (9, "Ethan", "Clark", "Austin", "USA", 6),
    (10, "Nadia", "Saleh", "Alexandria", "Egypt", 4),
)
_INVOICES = (
    (1, 1, "2024-01-12", "USA", 5.16),
    (2, 2, "2024-01-27", "USA", 3.47),
    (3, 3, "2024-02-08", "Canada", 6.94),
    (4, 4, "2024-02-19", "Canada", 2.98),
    (5, 5, "2024-03-04", "United Kingdom", 7.45),
    (6, 6, "2024-03-22", "France", 4.56),
    (7, 7, "2024-04-11", "Italy", 5.16),
    (8, 8, "2024-04-29", "Egypt", 8.43),
    (9, 9, "2024-05-17", "USA", 6.45),
    (10, 1, "2024-06-03", "USA", 9.72),
    (11, 3, "2024-07-15", "Canada", 4.27),
    (12, 5, "2024-08-21", "United Kingdom", 5.96),
    (13, 8, "2024-09-09", "Egypt", 7.74),
    (14, 10, "2024-10-18", "Egypt", 3.27),
    (15, 2, "2024-11-06", "USA", 8.94),
    (16, 7, "2024-12-14", "Italy", 6.15),
    (17, 6, "2025-01-10", "France", 4.98),
)
_INVOICE_LINES = (
    (1, 1, 1, 1.29, 2),
    (2, 1, 2, 1.29, 2),
    (3, 2, 3, 0.99, 2),
    (4, 2, 9, 1.49, 1),
    (5, 3, 5, 1.29, 3),
    (6, 3, 10, 1.49, 2),
    (7, 4, 9, 1.49, 2),
    (8, 5, 9, 1.49, 3),
    (9, 5, 10, 1.49, 2),
    (10, 6, 1, 1.29, 2),
    (11, 6, 7, 0.99, 2),
    (12, 7, 5, 1.29, 2),
    (13, 7, 6, 1.29, 2),
    (14, 8, 9, 1.49, 3),
    (15, 8, 10, 1.49, 2),
    (16, 8, 3, 0.99, 1),
    (17, 9, 1, 1.29, 3),
    (18, 9, 2, 1.29, 2),
    (19, 10, 6, 1.29, 4),
    (20, 10, 11, 1.29, 2),
    (21, 10, 8, 0.99, 2),
    (22, 11, 3, 0.99, 3),
    (23, 11, 1, 1.29, 1),
    (24, 12, 9, 1.49, 4),
    (25, 13, 5, 1.29, 6),
    (26, 14, 12, 0.99, 2),
    (27, 14, 1, 1.29, 1),
    (28, 15, 10, 1.49, 6),
    (29, 16, 2, 1.29, 3),
    (30, 16, 7, 0.99, 2),
    (31, 17, 4, 0.99, 2),
    (32, 17, 9, 1.49, 2),
)


class DatabaseInitializationError(RuntimeError):
    """Raised when the deterministic database cannot be initialized."""


class DatabaseProvisionState(StrEnum):
    """Outcome of an idempotent provisioning attempt."""

    CREATED = "created"
    ALREADY_PRESENT = "already_present"


def verify_database_schema(path: Path) -> None:
    """Confirm a database file exposes every expected demo table.

    Raises DatabaseInitializationError without the path or driver text, so callers can
    surface the failure in a public interface.
    """

    try:
        uri_path = quote(path.resolve().as_posix(), safe="/:")
        # closing() matters here: sqlite3's own context manager commits but never
        # closes, and an open handle blocks the replace step on Windows.
        with closing(
            sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True, timeout=5)
        ) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
    except (OSError, sqlite3.DatabaseError) as exc:
        raise DatabaseInitializationError("The demo database could not be verified.") from exc
    if EXPECTED_TABLES - {str(row[0]) for row in rows}:
        raise DatabaseInitializationError("The demo database is missing required tables.")


def ensure_database(path: Path) -> DatabaseProvisionState:
    """Provision the demo database once, without overwriting an existing valid one.

    Safe to call on every application start. A new database is built in a temporary
    file and moved into place, so an interrupted run never leaves a half-written
    database that later starts would treat as real.
    """

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DatabaseInitializationError(
            "The demo database location could not be created."
        ) from exc

    if path.is_file() and path.stat().st_size > 0:
        verify_database_schema(path)
        return DatabaseProvisionState.ALREADY_PRESENT

    # A zero-length file is not a database, so replacing it destroys nothing.
    temporary = path.with_name(f"{path.name}.provisioning")
    try:
        temporary.unlink(missing_ok=True)
    except OSError as exc:
        raise DatabaseInitializationError("The demo database could not be prepared.") from exc
    initialize_database(temporary, overwrite=True)
    verify_database_schema(temporary)
    try:
        os.replace(temporary, path)
    except OSError as exc:
        raise DatabaseInitializationError("The demo database could not be published.") from exc
    return DatabaseProvisionState.CREATED


def initialize_database(path: Path, *, overwrite: bool = False) -> None:
    """Create a deterministic database without reading legacy datasets."""

    if path.exists() and not overwrite:
        raise DatabaseInitializationError("Demo database already exists.")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.executescript(_SCHEMA_SQL)
            connection.executemany('INSERT INTO "Artist" VALUES (?, ?)', _ARTISTS)
            connection.executemany('INSERT INTO "Album" VALUES (?, ?, ?)', _ALBUMS)
            connection.executemany('INSERT INTO "Genre" VALUES (?, ?)', _GENRES)
            connection.executemany('INSERT INTO "Track" VALUES (?, ?, ?, ?, ?, ?)', _TRACKS)
            connection.executemany('INSERT INTO "Employee" VALUES (?, ?, ?, ?, ?)', _EMPLOYEES)
            connection.executemany('INSERT INTO "Customer" VALUES (?, ?, ?, ?, ?, ?)', _CUSTOMERS)
            connection.executemany('INSERT INTO "Invoice" VALUES (?, ?, ?, ?, ?)', _INVOICES)
            connection.executemany(
                'INSERT INTO "InvoiceLine" VALUES (?, ?, ?, ?, ?)',
                _INVOICE_LINES,
            )
    except (OSError, sqlite3.DatabaseError) as exc:
        raise DatabaseInitializationError("Demo database initialization failed.") from exc
