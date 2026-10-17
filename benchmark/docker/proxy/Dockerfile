# abb-proxy: tinyproxy allow-list sidecar. Attached to both the internal `abb-agent` network and the
# default bridge; agent containers reach the model API only through it (specs/docker-images.md).
FROM alpine:3.20
RUN apk add --no-cache tinyproxy
COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
COPY allow /etc/tinyproxy/allow
EXPOSE 8888
CMD ["tinyproxy", "-d"]
