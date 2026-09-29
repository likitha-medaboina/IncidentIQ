FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend, data, and demo scripts
COPY backend/ ./backend/
COPY data/ ./data/
COPY demo.py .

# Copy built frontend assets
COPY frontend/dist/ ./frontend/dist/

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV HINDSIGHT_URL=http://hindsight:8888
ENV HINDSIGHT_BANK_ID=team-payments

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
