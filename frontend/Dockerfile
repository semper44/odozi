FROM node:22-slim AS builder

WORKDIR /app
    
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .

RUN npm run build

FROM nginx:alpine

# Copy built React files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80