# syntax=docker/dockerfile:1

FROM python:3.11-slim

# Install uv for dependency management
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy only dependency files to leverage build cache
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv
RUN uv venv .venv && \
    uv pip install --system -r <(uv pip compile --generate-hashes --output-format=requirements.txt pyproject.toml)

# Runtime: mount source code and media directory as volumes from host
# Static/media directories served from mounted host, nothing copied in

# Expose the development server port
EXPOSE 8000

# Entrypoint: run Django dev server, expect code to be mounted at /app/htr_seg_select
CMD ["python", "-m", "htr_seg_select.manage", "runserver", "0.0.0.0:8000"]