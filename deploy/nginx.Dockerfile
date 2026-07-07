# Stage 1: 프론트엔드 빌드
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: nginx (정적 서빙 + API 리버스 프록시)
FROM nginx:1.27-alpine
COPY --from=frontend-build /app/dist /usr/share/nginx/html
# templates/*.template은 nginx 엔트리포인트가 envsubst로 ${DOMAIN}을 치환해 /etc/nginx/conf.d/에 배치
COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
