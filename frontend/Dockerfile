# --- stage 1: build the React bundle -----------------------------------------
FROM node:20-slim AS build

WORKDIR /app

# Install dependencies against the lockfile for reproducible builds.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# --- stage 2: serve the static bundle ----------------------------------------
FROM nginx:1.27-alpine

# Replace the default site with one that serves the SPA and proxies /api to
# the backend container, so the browser only ever talks to one origin.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx stops if a config typo slips in - fails fast rather than serving 404s.
CMD ["nginx", "-g", "daemon off;"]
