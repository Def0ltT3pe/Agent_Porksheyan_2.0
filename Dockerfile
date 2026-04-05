# Этап 1: сборка фронтенда
FROM node:18-alpine AS frontend-builder

WORKDIR /front
# Копируем package.json из вложенной папки
COPY front/agent-porksheyan-frontend/package*.json ./
RUN npm ci
# Копируем весь код фронтенда
COPY front/agent-porksheyan-frontend/ .
RUN npm run build   # создаст /front/dist

# Этап 2: бэкенд + статика
FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости бэкенда
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бэкенда (включая app/, agent/, main.py и т.д.)
COPY . .

# Копируем собранный фронтенд в папку static (бэкенд будет её раздавать)
COPY --from=frontend-builder /front/dist /app/static

EXPOSE 8000
CMD ["python", "main.py"]