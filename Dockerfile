# ---- stage 1: build static frontend -------------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN NEXT_OUTPUT=export npm run build

# ---- stage 2: python runtime serving API + static site ------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 \
    UTM_DATA_DIR=/app/data STATIC_DIR=/app/frontend/out
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /app/frontend/out frontend/out
# input files: copied if present in the build context (data/raw is git-ignored by default)
COPY data/ data/
RUN mkdir -p /app/data/raw /app/data/processed /app/data/uploads
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+__import__('os').environ.get('PORT','8000')+'/api/health').status==200 else 1)"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
