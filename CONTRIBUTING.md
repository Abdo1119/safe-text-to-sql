# Contributing

Thank you for improving Safe Text-to-SQL.

1. Open an issue describing the change and its security implications.
2. Create a focused branch.
3. Add or update tests before changing trust-boundary behavior.
4. Run all local quality gates:

   ```bash
   ruff check .
   ruff format --check .
   mypy src tests scripts app.py
   pytest
   python scripts/run_evaluation.py
   python scripts/verify_release.py
   ```

5. Keep fake mode deterministic and ensure every CI test remains credential-free.
6. Do not commit `.env`, credentials, private data, generated databases, evaluation
   outputs, or provider responses.

Changes to SQL policy, prompt construction, database authorization, or release scanning
should include adversarial tests. Pull requests should explain tradeoffs and avoid
unsupported accuracy or performance claims.
