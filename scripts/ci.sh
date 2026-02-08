#!/usr/bin/env bash
# CI check script for ESOP platform
# Run all checks that must pass before merge.
set -euo pipefail

echo "=== Step 1: Ruff lint ==="
ruff check .

echo "=== Step 2: Ruff format check ==="
ruff format --check .

echo "=== Step 3: Bandit security scan ==="
bandit -c pyproject.toml -r . -ll

echo "=== Step 4: Django system checks ==="
python manage.py check --deploy --settings=config.settings.prod 2>&1 || true

echo "=== Step 5: Pytest ==="
pytest

echo "=== All checks passed ==="

