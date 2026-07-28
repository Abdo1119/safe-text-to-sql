"""Initialize the deterministic synthetic demo database."""

from __future__ import annotations

import argparse
from pathlib import Path

from safe_text_to_sql.database.initializer import initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/demo/chinook_demo.sqlite"),
        help="Destination database path.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing generated database.",
    )
    arguments = parser.parse_args()
    initialize_database(arguments.database, overwrite=arguments.force)
    print("Synthetic demo database initialized.")


if __name__ == "__main__":
    main()
