FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.8.0

RUN pip install --no-cache-dir \
    transformers==4.57.4 \
    sentencepiece==0.2.1 \
    sacremoses==0.1.1

COPY server.py /app/server.py

RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8080
CMD ["python", "/app/server.py"]
