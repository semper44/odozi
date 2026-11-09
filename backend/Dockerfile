FROM python:3.12-slim AS builder

WORKDIR /app

# adding additional system build tools and development libraries required by some Python packages.
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libffi-dev \
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*
    
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

WORKDIR /app


# Copying installed packages only
COPY --from=builder /usr/local /usr/local

COPY backend/ .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]