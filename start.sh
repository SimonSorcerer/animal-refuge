#!/bin/bash
set -e
alembic upgrade 0001
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
