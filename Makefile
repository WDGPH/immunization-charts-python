# Makefile for Immunization Charts Python Package

.PHONY: help install install-dev test clean run-preprocess run-pipeline lint format web

# Default target
help:
	@echo "Available targets:"
	@echo "  install       Install the package in development mode"
	@echo "  install-dev   Install development dependencies"
	@echo "  test          Run tests"
	@echo "  lint          Run linting checks"
	@echo "  format        Format code with black"
	@echo "  clean         Clean up temporary files"
	@echo "  run-preprocess INPUT_FILE LANG  Run preprocessing only"
	@echo "  run-pipeline  INPUT_FILE LANG   Run full pipeline"
	@echo "  web           Start web interface"

# Install the package in development mode
install:
	pip install -e .

# Install development dependencies
install-dev:
	pip install -e ".[dev]"

# Run tests
test:
	python -m pytest tests/ -v

# Run linting
lint:
	python -m flake8 src/
	python -m mypy src/

# Format code
format:
	python -m black src/ tests/
	python -m isort src/ tests/

# Clean up temporary files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

# Run preprocessing only
run-preprocess:
	@if [ -z "$(INPUT_FILE)" ] || [ -z "$(LANG)" ]; then \
		echo "Usage: make run-preprocess INPUT_FILE=<file> LANG=<english|french>"; \
		exit 1; \
	fi
	python -m immunization_charts.cli.main "$(INPUT_FILE)" "$(LANG)" --preprocess-only

# Run full pipeline
run-pipeline:
	@if [ -z "$(INPUT_FILE)" ] || [ -z "$(LANG)" ]; then \
		echo "Usage: make run-pipeline INPUT_FILE=<file> LANG=<english|french>"; \
		exit 1; \
	fi
	python -m immunization_charts.cli.main "$(INPUT_FILE)" "$(LANG)"

# Start web interface
web:
	python run_web.py

# Development setup
setup-dev: install-dev
	@echo "Development environment setup complete!"
	@echo "Run 'make test' to run tests"
	@echo "Run 'make lint' to check code quality"
	@echo "Run 'make web' to start the web interface"
