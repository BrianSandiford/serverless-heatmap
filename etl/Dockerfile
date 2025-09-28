# Start from GDAL image (with Python installed)
FROM ghcr.io/osgeo/gdal:ubuntu-full-latest

# Install Python + venv tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (to leverage Docker cache)
COPY requirements.txt .

# Create a virtual environment and install dependencies
RUN python3 -m venv /opt/venv \
 && . /opt/venv/bin/activate \
 && pip install --no-cache-dir -r requirements.txt

# Add venv to PATH (so `python` and `pip` default to venv)
ENV PATH="/opt/venv/bin:$PATH"

# Copy the rest of the app
COPY . .

# Default command
CMD ["python", "etl/etl.py"]
