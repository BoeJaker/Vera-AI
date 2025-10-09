FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# # Copy requirements just before for better caching
# COPY llm-requirements.txt .
# # Install LLM dependencies
# RUN pip install --no-cache-dir -r llm-requirements.txt

COPY requirements.txt .
# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 verauser && chown -R verauser:verauser /app
USER verauser

# Expose port
EXPOSE 8500
EXPOSE 8501
EXPOSE 8502

# Health check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
#     CMD curl -f http://localhost:8080/api/shim/health || exit 1

# Run the application
CMD ["start.sh"]