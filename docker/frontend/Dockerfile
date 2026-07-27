FROM node:22-bookworm-slim AS base

WORKDIR /app
ENV NPM_CONFIG_UPDATE_NOTIFIER=false

FROM base AS dev

COPY frontend/package.json frontend/package-lock.json ./
RUN npm install

COPY frontend /app

EXPOSE 5173

CMD ["sh", "-lc", "npm install && npm run dev"]

FROM base AS build

ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend /app
RUN npm run build

FROM base AS e2e

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci && npx playwright install --with-deps chromium

COPY frontend /app

FROM nginx:1.28-alpine AS prod

COPY docker/frontend/nginx.default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
