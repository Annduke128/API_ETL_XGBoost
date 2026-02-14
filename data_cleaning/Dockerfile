FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc-dev \
    libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY *.py .

# Create directories
RUN mkdir -p /csv_input /csv_output /csv_input/processed /csv_input/error

# Default: run auto processor in continuous mode
CMD ["python", "auto_process_csv.py", "--input", "/csv_input", "--output", "/csv_output", "--continuous"]
