FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances d'abord (cache de build), puis le code.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e .

CMD ["python", "-m", "episode_id_map"]
