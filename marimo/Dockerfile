# Use a lightweight Python image
FROM python:3.10-slim-buster

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy pyproject.toml and uv.lock to leverage uv's caching
COPY pyproject.toml ./pyproject.toml
COPY uv.lock ./uv.lock

# Install dependencies
RUN uv sync --frozen

# Copy the marimo files
COPY marimo/ ./marimo/

# Create a non-root user for security
RUN adduser --disabled-password --gecos '' marimouser
RUN chown -R marimouser:marimouser /app
USER marimouser

# Expose the port marimo runs on
EXPOSE 2718

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MARIMO_HOST=0.0.0.0
ENV MARIMO_PORT=2718

# Command to run marimo
CMD [".venv/bin/marimo", "run", "marimo/test_data_generator.py", "--host", "0.0.0.0", "--port", "2718"] 