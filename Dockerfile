FROM python:3.11-slim

WORKDIR /app

COPY app /app/app
COPY static /app/static
COPY config /app/config

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    requests \
    pyyaml

EXPOSE 8787

CMD ["uvicorn", "app.web:app", "--host", "0.0.0.0", "--port", "8787"]