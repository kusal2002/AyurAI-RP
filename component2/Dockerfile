# Component 2 API (Ayurvedic KG reasoning), production image.
# Python 3.13 matches the local .venv.
FROM python:3.13-slim

WORKDIR /app

# 1) CPU-only PyTorch (the default build bundles large CUDA libraries)
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu

# 2) Other packages, in their own layer so code-only changes rebuild fast
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) Code and the small committed knowledge files
COPY app/ app/
COPY knowledge/ knowledge/

ENV PYTHONUNBUFFERED=1 \
    # Embedding models download here on first use; compose mounts a volume
    # so they are not downloaded again after every rebuild.
    HF_HOME=/models

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
