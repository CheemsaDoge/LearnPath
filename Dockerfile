# ---- frontend build
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- backend runtime
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 LEARNPATH_FRONTEND_DIST=/app/frontend/dist LEARNPATH_DATABASE_URL=sqlite:////data/learnpath.db
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY --from=web /web/dist ./frontend/dist
VOLUME ["/data"]
EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
