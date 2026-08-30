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

# Hugging Face Spaces default port is 7860
ENV PORT=7860
EXPOSE 7860

# Start FastAPI server
CMD ["uv", "run", "--group", "api", "uvicorn", "cella.api.main:app", "--host", "0.0.0.0", "--port", "7860"]

