# --- Etapa de build ---
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Railway expone las variables del servicio como build args.
# VITE_API_URL debe apuntar a la URL publica del backend + /api.
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# --- Etapa de servicio ---
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# El entrypoint de nginx expande ${PORT} sobre la plantilla al arrancar.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
# NGINX_ENVSUBST_FILTER limita la sustitucion a PORT para no romper $uri.
ENV NGINX_ENVSUBST_FILTER=^PORT$
ENV PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD wget --spider -q "http://127.0.0.1:${PORT}/" || exit 1
