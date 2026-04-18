FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY band_plans.py .
COPY main.py .
COPY templates/ templates/
COPY static/ static/
RUN mkdir -p /opt/dx_monitor_docker
EXPOSE 8765
CMD ["python", "-u", "main.py"]
