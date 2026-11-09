FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
RUN python -m whitenoise.compress /app/frontend/dist

# One worker with threads, so the in-memory forecast cache is shared by every request.
CMD gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 8 --timeout 120
