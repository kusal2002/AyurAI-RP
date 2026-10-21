# AyurAI dashboard: build the static site, then serve it with nginx.
# nginx also forwards /c2-api, /c3-api and /c4-api to the backend containers
# (the job the Vite dev proxy does locally).

# ---------- 1) Build ----------
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Browser-side API paths: same-origin, handled by nginx
ENV VITE_C1_API_BASE_URL=/c1-api \
    VITE_C2_API_BASE_URL=/c2-api \
    VITE_C3_API_BASE_URL=/c3-api \
    VITE_C4_API_BASE_URL=/c4-api \
    VITE_API_TIMEOUT_MS=20000 \
    VITE_C2_REASONING_TIMEOUT_MS=180000
RUN npm run build

# ---------- 2) Serve ----------
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# The site config comes from deploy/nginx (mounted by docker-compose.prod.yml)
EXPOSE 80 443
