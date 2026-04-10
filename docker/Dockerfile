FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy lib directory containing all wheel files
COPY lib/ /app/lib/

# Install all packages from local lib directory (list all packages explicitly)
RUN pip install --no-index --find-links=/app/lib/ \
    langchain \
    langchain-core \
    langgraph \
    langchain-openai \
    sqlalchemy \
    aiomysql \
    pymysql \
    websockets \
    aiohttp \
    paramiko \
    pydantic \
    pydantic-settings \
    croniter \
    pytest \
    pytest-asyncio \
    pytest-mock \
    python-dotenv

# Copy application code
COPY src/ /app/src/
COPY CLAUDE.md /app/
COPY README.md /app/
COPY .env.example /app/.env
COPY requirements.txt /app/

# Create non-root user
RUN useradd -m -u 1000 aiops && \
    chown -R aiops:aiops /app
USER aiops

# Expose WebSocket port
EXPOSE 8765

# Run the application
CMD ["python", "-m", "src.main"]