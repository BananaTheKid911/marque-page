# --- build front ---
FROM node:24-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build              # -> /web/dist

# --- runtime ---
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
# Migrations Alembic : nécessaires au démarrage (création du schéma sur base
# vierge). Sans `alembic.ini` + `alembic/` copiés, `upgrade head` échouerait
# dans le conteneur — le volume data/ est vide au premier déploiement.
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY --from=web /web/dist ./static
ENV TZ=Europe/Paris
EXPOSE 8000
# `alembic upgrade head` AVANT uvicorn : idempotent (ne rejoue que ce qui
# manque), donc sûr à chaque redémarrage. Le healthcheck Docker n'appelle que
# /api/v1/health qui ne touche pas la base — sans cette ligne, le conteneur
# serait marqué "healthy" alors que toutes les routes métier planteraient.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
