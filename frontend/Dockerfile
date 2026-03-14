# frontend/Dockerfile
# ====================
# Multi-stage build for the React frontend.
#
# Stage 1 (builder): runs `npm run build` to produce /build static files
# Stage 2 (runtime): serves those static files with nginx (no Node.js needed)
#
# Result: a tiny ~25MB nginx image instead of a heavy Node.js dev container.

# ---- Stage 1: Build React app ----------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first (cache layer — only reinstalls if package.json changes)
COPY package.json package-lock.json* ./

# Install all npm dependencies (including devDependencies for the build)
RUN npm ci --silent

# Copy the rest of the source code
COPY . .

# Build the production bundle into /app/build
# REACT_APP_API_URL is injected at build time — set it via docker-compose environment
ARG REACT_APP_API_URL=http://localhost:8000
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

# ---- Stage 2: Serve with nginx ----------------------------------------
FROM nginx:1.25-alpine AS runtime

# Remove the default nginx welcome page
RUN rm -rf /usr/share/nginx/html/*

# Copy our built React app into nginx's web root
COPY --from=builder /app/build /usr/share/nginx/html

# Copy a custom nginx config that handles React Router (client-side routing)
# Without this, refreshing any page other than / gives a 404.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# nginx runs in the foreground (daemon off) so Docker sees the process
CMD ["nginx", "-g", "daemon off;"]
