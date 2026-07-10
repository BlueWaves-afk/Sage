# SAGE frontend (System 5 UI) — multi-stage: Vite build → nginx static serve.
# Stage 1: build the React/deck.gl app.
FROM node:20-slim AS build
WORKDIR /app
COPY visualizer_agent/frontend/package*.json ./
RUN npm ci
COPY visualizer_agent/frontend/ ./
RUN npm run build

# Stage 2: serve the static bundle with nginx, proxying /api and /ws to the gateway.
FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
# Healthcheck via the busybox wget that ships with nginx:alpine (the previous
# form reported false "unhealthy"). --spider = HEAD request, no body written.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD wget -q --spider http://127.0.0.1:80/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
