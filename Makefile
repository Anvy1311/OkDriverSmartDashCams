.PHONY: install install-dev run test compile lint typecheck check clean

install:
	python -m pip install -r requirements.txt

install-dev:
	python -m pip install -r requirements-dev.txt

run:
	uvicorn app.main:app --reload

test:
	pytest -q

compile:
	python -m compileall -q app

lint:
	ruff check app tests

typecheck:
	mypy app

check: compile lint typecheck test

clean:
	rm -f okdriver.db smoke*.db rootcheck.db
	rm -rf __pycache__ app/__pycache__ app/api/__pycache__ app/api/routes/__pycache__ app/services/__pycache__ tests/__pycache__ .pytest_cache .mypy_cache .ruff_cache
