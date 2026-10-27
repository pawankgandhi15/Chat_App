FROM nginx@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951
# Fixed Alpine packages for CVE-2026-111497 and CVE-2026-92392.
RUN apk add --no-cache --upgrade brotli-libs=1.2.1-r0 curl=8.23.0-r0 libcurl=8.23.0-r0
COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/css/style.css /usr/share/nginx/html/assets/style.css
COPY frontend/js /usr/share/nginx/html/assets/js
COPY frontend/icon.svg /usr/share/nginx/html/assets/icon.svg
USER 101:101
EXPOSE 8080
ENTRYPOINT ["nginx", "-g", "daemon off;"]
