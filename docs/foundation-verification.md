# Offline Foundation Verification (Historical Milestone)

Verified on 2026-07-28.

This record captures the earlier 62-test foundation checkpoint. It is retained for
traceability and does not describe the current release; use the README and current CI
workflow for the complete application and latest verification commands.

## Environment

- Python: 3.13.5
- Environment: project-local `.venv`
- Installation command:

  ```powershell
  .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
  ```

- Installed SQL parser: SQLGlot 29.0.1
- No dependency constraint changes or additional project dependencies were required.

## Quality results

| Check | Command | Result |
|---|---|---|
| Unit tests | `.\.venv\Scripts\python.exe -m pytest` | 62 passed |
| Ruff lint | `.\.venv\Scripts\ruff.exe check .` | All checks passed |
| Ruff format | `.\.venv\Scripts\ruff.exe format --check .` | 15 files already formatted |
| mypy | `.\.venv\Scripts\mypy.exe src tests` | No issues in 14 source files |

All tests are offline. They require no Azure credentials, external API, PostgreSQL
server, Docker daemon, or paid service.

## Issues discovered and changes made

- The initial dependency installation was observed before its slow package downloads
  completed. The same declared editable-install command was allowed to finish; no
  dependency was added or changed.
- Ruff found one import-order issue and four Python files requiring deterministic
  formatting. Ruff's import organizer and formatter were applied only to permitted
  clean-project files.
- mypy found a test variable reused for coroutines with different result types. The
  failure-path test now executes each provider coroutine directly inside its matching
  branch without changing provider behavior.
- A recursive CTE allowlist test was added. It confirms that the recursive CTE alias is
  not mistaken for a physical table while the underlying qualified table remains
  enforced by the allowlist.

## SQLGlot 29.0.1 compatibility

Observed PostgreSQL AST behavior:

- ordinary and recursive `WITH ... SELECT` queries have a `Select` root;
- recursive `WITH` is marked with `recursive=True`;
- CTEs are represented by `CTE` nodes and recursive self-references by `Table` nodes;
- qualified tables expose catalog, schema, and name separately;
- data-modifying CTEs retain their DML node, such as `Delete`, below the CTE;
- `SELECT INTO` exposes an `Into` node;
- `FOR UPDATE` populates the select's lock collection;
- a literal `LIMIT` uses a `Limit` node containing a `Literal`;
- semicolon-separated input is returned as multiple parsed statements.

These representations match the guard's fail-closed checks. The complete guard suite
covers selects, joins, aggregations, window functions, ordinary and recursive CTEs,
limits, prohibited mutations, locking, malformed SQL, system catalogs, and schema and
table allowlists.

## Scope at this milestone

- This checkpoint covered the offline SQL policy and provider-independent foundation.
- Database execution, Streamlit, Gemini, Docker, CI, and evaluation were added after
  this record.
- No performance, accuracy, deployment, or production-readiness claim was established
  by this checkpoint.

Network access was limited to installing the dependencies declared in
`pyproject.toml` from the Python package index. No application network service,
external API, database, or Docker service was contacted.
