# ---------- build stage ----------
FROM node:20-alpine AS builder
WORKDIR /app

# Install deps first (better cache)
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000

COPY . .

# Empty REACT_APP_BACKEND_URL so the app calls "/api/..." (same-origin via nginx proxy)
ENV REACT_APP_BACKEND_URL=""
ENV DISABLE_ESLINT_PLUGIN=true
ENV CI=false

RUN yarn build

# ---------- serve stage ----------
FROM nginx:1.27-alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
