# Build Stage for Frontend
FROM node:18-alpine as frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Runtime Stage
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for Playwright
# We use the playwright install-deps command or install manually
# Using the official playwright python image is safer but large. 
# Let's start with slim and install what's needed.
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
