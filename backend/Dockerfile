# backend/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies first
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy both backend and ews directories
COPY backend/ ./backend/
COPY ews/ ./ews/

# Default working directory is backend for the API
WORKDIR /app/backend

# Default command for the backend service
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
