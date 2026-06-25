FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.2.1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app/backend

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY README.md ../README.md
COPY backend/pyproject.toml backend/poetry.lock backend/poetry.toml ./
RUN poetry install --only main --no-root

COPY backend/donerbench ./donerbench

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "donerbench.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
