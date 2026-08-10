FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY harness/ harness/
COPY ui/ ui/
COPY demo/ demo/

EXPOSE 8501

ENV PYTHONUNBUFFERED=1

CMD streamlit run ui/app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.headless=true
