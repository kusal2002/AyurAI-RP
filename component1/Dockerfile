# Component 1 API (screening intake: questionnaire, webcam images, analysis), production image.
#
# Layout matters: the code finds its data at <repo>/../datasets, computed from its
# own file path. With the code at /app/component1, that is /datasets, which
# docker-compose.prod.yml mounts as a volume (model weights + session records).
FROM python:3.12-slim

WORKDIR /app

# 1) CPU-only PyTorch and torchvision (the default build bundles CUDA libraries)
RUN pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 \
        --index-url https://download.pytorch.org/whl/cpu

# 2) Other packages. On a server:
#    - opencv-python-headless replaces opencv-python (no desktop GUI libraries needed)
#    - streamlit is left out: only the local Streamlit pages use it, not the API
#    - python-multipart is added: FastAPI needs it for the image upload route,
#      and requirements.txt does not list it
COPY requirements.txt /tmp/requirements.txt
RUN grep -vE '^(torch|torchvision|opencv-python|streamlit)==' /tmp/requirements.txt > /tmp/req-api.txt \
    && pip install --no-cache-dir -r /tmp/req-api.txt opencv-python-headless==5.0.0.93 python-multipart==0.0.20 \
    && rm /tmp/requirements.txt /tmp/req-api.txt

# 3) The code, as the "component1" package (imports use component1.api..., component1.fusion...)
COPY . component1/

ENV PYTHONUNBUFFERED=1 \
    # PPG figures are written to files; never try to open a window
    MPLBACKEND=Agg

EXPOSE 8001
CMD ["uvicorn", "component1.api.server:app", "--host", "0.0.0.0", "--port", "8001"]
