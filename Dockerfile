FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

# Same layout as the repo (backend/ and data/ side by side),
# because the evaluation code looks for the data folder next to backend/.
WORKDIR /srv/backend

# Dependencies first: this layer is cached until requirements.txt changes.
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
COPY data/ /srv/data/

# Download the embedding model at build time so a cold start never has to.
RUN DATABASE_URL=sqlite:// SECRET_KEY=build-only \
    python -c "from app.services.embeddings import embed_text; embed_text('warm up')"

RUN useradd --create-home appuser && chown -R appuser /srv
USER appuser

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]