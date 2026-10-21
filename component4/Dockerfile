# Image for the federated nodes: one image, used by the server and all clinic containers.
# Python 3.11 matches the local venv (3.11.9).
FROM python:3.11-slim

WORKDIR /app

# 1) CPU-only PyTorch: far smaller than the default build, which bundles CUDA (GPU) libraries.
#    --no-cache-dir stops pip keeping a copy of every download inside the image.
RUN pip install --no-cache-dir torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu

# 2) The remaining packages. Copied on their own first so Docker can reuse this
#    layer when only the code changes (faster rebuilds).
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# 3) The federated code itself (server.py, client.py, config.py, data.py, model.py, ...)
COPY federated/ federated/

# Print output immediately (no buffering), so `docker compose logs` shows progress live
ENV PYTHONUNBUFFERED=1

# Default command; docker-compose.yml overrides it for each service
CMD ["python", "federated/server.py"]
