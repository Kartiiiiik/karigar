# syntax=docker/dockerfile:1
# ===========================================================================
# Multi-stage production image for the React frontend.
#   Stage 1 (builder): install deps and produce a static Vite build.
#   Stage 2 (runtime): serve the build with nginx, proxying /api to backend.
# ===========================================================================

# --------------------------- Stage 1: builder ------------------------------
FROM node:22-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# --------------------------- Stage 2: runtime ------------------------------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
