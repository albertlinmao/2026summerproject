FROM python:3.11-slim

WORKDIR /app

# Install dependencies from pyproject.toml
COPY . .
RUN pip install --no-cache-dir .

# Expose port
EXPOSE 8000

# Run FastAPI app with Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
