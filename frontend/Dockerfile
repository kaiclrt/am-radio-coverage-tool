# Multi-stage: build the static Vite bundle, then serve it with nginx -
# nginx also reverse-proxies /api/* to the api container (see nginx.conf),
# so the browser only ever talks to one origin and flask-cors's
# restriction never comes into play for the containerized setup.

FROM node:20-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
