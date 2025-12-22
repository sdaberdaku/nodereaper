FROM python:3.11-alpine

# Create non-root user
RUN adduser -D -s /bin/sh nodereaper

WORKDIR /app

# Copy package files
COPY pyproject.toml README.md requirements.txt ./
COPY src/ src/

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

USER nodereaper

CMD ["nodereaper"]
