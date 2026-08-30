FROM python:3.11-slim

WORKDIR /app

# Install uv for fast, reliable package management
RUN pip install --no-cache-dir uv

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install python dependencies for the API group
RUN uv sync --group api --no-install-project

# Copy source code and processed data artifacts
COPY src/ ./src/
COPY data/processed/ ./data/processed/

# Install the cella package
RUN uv sync --group api

# Default port for Render (Render sets $PORT dynamically)
ENV PORT=10000
EXPOSE 10000

# Start FastAPI server binding dynamically to $PORT
CMD ["sh", "-c", "uv run --group api uvicorn cella.api.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
