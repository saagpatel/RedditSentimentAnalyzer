.PHONY: install test lint clean run

install:
	python -m pip install -e ".[dev]" httpx

test:
	python -m pytest tests/ -v

lint:
	npm --prefix frontend run lint

run:
	python -m uvicorn backend.main:app --reload

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; rm -rf .pytest_cache
