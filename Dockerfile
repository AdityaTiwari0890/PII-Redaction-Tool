FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pii_redactor/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm

COPY pii_redactor ./pii_redactor
COPY run.py ./run.py

VOLUME ["/app/docs", "/app/output"]

ENTRYPOINT ["python", "run.py"]
