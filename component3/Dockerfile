# Component 3 API (herb-drug safety assessment), production image.
FROM python:3.13-slim

WORKDIR /app

# 1) CPU-only PyTorch first, so requirements.txt (torch>=2.2) does not pull the CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 2) Other packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) Code, JSON data and model weights (all under app/)
COPY app/ app/

ENV PYTHONUNBUFFERED=1

EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
