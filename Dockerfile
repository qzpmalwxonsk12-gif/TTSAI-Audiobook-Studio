FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TTSAI_DATA=/var/data
WORKDIR /app
COPY requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements-cloud.txt
COPY app ./app
COPY static ./static
COPY samples ./samples
COPY scripts/serve_cloud.py ./scripts/serve_cloud.py
EXPOSE 8767
CMD ["python", "scripts/serve_cloud.py"]
