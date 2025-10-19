# Start from GDAL image (includes ogr2ogr, Parquet driver, etc.)
FROM ghcr.io/osgeo/gdal:ubuntu-full-latest

ENV DEBIAN_FRONTEND=noninteractive

# Install Python, PostgreSQL client, and Parquet dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv postgresql-client ca-certificates \
    libarrow-dev libparquet-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies inside a virtual environment
COPY requirements.txt .
RUN python3 -m venv /opt/venv \
 && . /opt/venv/bin/activate \
 && pip install --no-cache-dir -r requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

# Copy your ETL app code
COPY . .

# Default command (runs ETL automatically in your compose)
CMD ["python", "etl/etl.py"]
