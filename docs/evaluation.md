# Evaluation methodology

The checked-in evaluation cases exercise the complete fake-provider workflow against
the generated synthetic database. Categories include filtering, aggregation, joins,
grouping, ordering, nested queries, CTEs, window functions, unsupported requests,
prompt injection, and destructive requests.

Run:

```bash
python scripts/initialize_demo_db.py
python scripts/run_evaluation.py
```

Each result records the case ID, question, SQL, validation and execution status,
expected-result match, safe error category, elapsed time, provider mode, and timestamp.
Generated results are local artifacts under `evaluation/results/` and are not committed.

The fake provider maps known questions to reviewed SQL. Consequently, its result is
labeled **deterministic functional verification**. It verifies orchestration,
validation, execution, and expected outputs; it is not a statistical measure of model
accuracy. A meaningful Gemini evaluation would require a larger frozen benchmark,
repeated runs, documented model version and parameters, manual error analysis, and
separate reporting. One live smoke test is not evidence of accuracy or latency.
