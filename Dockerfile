# ============================================
# DiscordTicketBot Dockerfile
# ============================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libopus0 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY views.py .
COPY database.py .
COPY models.py .
COPY commands.py .
COPY transcript.py .
COPY config.py .
COPY utils.py .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DATABASE_PATH=/app/data/tickets.db

# Run the bot
CMD ["python", "main.py"]
