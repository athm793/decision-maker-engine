# Build Stage for Frontend
FROM node:18-slim as frontend-build
WORKDIR /app/frontend

# Ensure we install dev dependencies
ENV NODE_ENV=development

# Copy all frontend files first to ensure context is complete
COPY frontend/ ./

# Install dependencies (including devDependencies like tailwindcss)
RUN npm install

# Run build
RUN npm run build

# Runtime Stage
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install playwright
RUN playwright install --with-deps chromium

# Copy Backend Code
COPY backend/ ./backend/

# Copy Frontend Build from previous stage
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Environment variables
ENV PYTHONPATH=/app/backend
ENV PORT=8000

# Run Command
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
