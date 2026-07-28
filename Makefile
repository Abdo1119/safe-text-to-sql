.PHONY: install init run test lint format typecheck evaluate verify docker

install:
	python -m pip install -r requirements.lock

init:
	python scripts/initialize_demo_db.py

run: init
	streamlit run app.py

test:
	pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy src tests scripts app.py

evaluate: init
	python scripts/run_evaluation.py

verify:
	python scripts/verify_release.py

docker:
	docker build -t safe-text-to-sql .
