# Security architecture

## Assets

The protected assets are database integrity and confidentiality, provider credentials,
and safe application availability. The demo contains synthetic public data, but the
same boundaries matter if another adapter is introduced later.

## Enforcement chain

1. Questions have bounded length and reject empty input.
2. The service introspects only the configured fixed database.
3. Retrieved examples and schema are delimited as untrusted prompt context.
4. Model output is normalized without executing or evaluating it.
5. SQLGlot must parse exactly one supported query.
6. The guard permits a read-only AST, checks referenced tables, rejects system
   catalogs and locking, and applies a row limit.
7. Invalid generated SQL may receive one bounded repair; repaired SQL must cross the
   complete guard again.
8. The repository re-enforces read-only access in SQLite and caps fetched rows.
9. Answer generation receives only bounded, serialized results.

No prompt instruction can bypass steps 5–8.

## Operational guidance

- Use fake mode for public demos unless sending questions and result context to Gemini
  is acceptable.
- Rotate a key immediately if it is ever committed or displayed.
- Keep database files outside user-controlled paths.
- For PostgreSQL, add a dedicated read-only role, explicit schema grants, transaction
  read-only mode, statement timeouts, and a controlled search path.
- Re-run `python scripts/verify_release.py` before every release.

## Residual risks

AST policies can contain parser or policy defects. Valid read-only SQL can still be
expensive, disclose allowed data, or communicate an incorrect interpretation.
Provider requests leave the local trust boundary. A production deployment therefore
also needs authentication, authorization, rate limiting, monitoring, query-cost
controls, and data-governance review.
