# Start from GDAL image (with Python installed)
FROM ghcr.io/osgeo/gdal:ubuntu-full-latest

ENV DEBIAN_FRONTEND=noninteractive

# Install Python + Postgres client
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv postgresql-client ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements first (cache-friendly)
COPY requirements.txt .
RUN python3 -m venv /opt/venv \
 && . /opt/venv/bin/activate \
 && pip install --no-cache-dir -r requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

# App code
COPY . .

CMD ["python", "etl/etl.py"]
