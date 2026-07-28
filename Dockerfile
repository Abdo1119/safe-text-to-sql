FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    LLM_PROVIDER=fake \
    DATABASE_PATH=/app/data/demo/chinook_demo.sqlite \
    PORT=8501

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY requirements.lock ./
RUN python -m pip install --no-cache-dir -r requirements.lock

COPY app.py ./
COPY src ./src
COPY scripts ./scripts
COPY data/examples.json ./data/examples.json
COPY .streamlit ./.streamlit

RUN python scripts/initialize_demo_db.py \
    && chown -R app:app /app

USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8501') + '/_stcore/health', timeout=3)"

CMD ["sh", "-c", "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]
