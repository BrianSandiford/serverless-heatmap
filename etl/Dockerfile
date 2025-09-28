FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY etl.py .

CMD ["python", "etl.py", "--towers-csv", "/app/opencellid_barbados_towers.csv"]
