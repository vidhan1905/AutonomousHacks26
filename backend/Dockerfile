# Backend Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml README.md ./

# Install Python dependencies using uv
RUN uv pip install --system --no-cache -e .

# Copy alembic configuration
COPY alembic.ini ./

# Copy scripts directory (for data loading)
COPY scripts/ ./scripts/

# Copy backend source code
COPY backend/ ./backend/

# Copy generated data files to the location expected by insert_generated_data.py
# The script expects: backend/src/data/generated/
# Files are located at: backend/data/generated/
RUN mkdir -p ./backend/src/data/generated && \
    cp -r ./backend/data/generated/* ./backend/src/data/generated/ 2>/dev/null || true

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
