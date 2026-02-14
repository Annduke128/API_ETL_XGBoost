FROM python:3.11-slim

WORKDIR /app

# Cài đặt dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY *.py .

CMD ["python", "train_models.py"]
