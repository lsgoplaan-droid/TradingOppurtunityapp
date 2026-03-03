FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies for pandas-ta and numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

FROM base AS dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

FROM dependencies AS runtime
COPY . .

EXPOSE 8000
CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
