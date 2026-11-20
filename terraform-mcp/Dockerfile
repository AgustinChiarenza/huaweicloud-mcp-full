# Dockerfile para terraform-mcp-server — clona el upstream oficial de
# hashicorp/terraform-mcp-server (MPL-2.0) y lo compila. Self-contained:
# no requiere que los fuentes Go vivan en este repo.
#
# Uso:
#   docker build -t terraform-mcp-server:dev ./terraform-mcp
#   docker run -p 8088:8080 terraform-mcp-server:dev \
#     streamable-http --transport-host 0.0.0.0 --transport-port 8080

# Stage 1: clonar el upstream
FROM alpine:3.22 AS clone
RUN apk add --no-cache git
WORKDIR /src
RUN git clone --depth 1 https://github.com/hashicorp/terraform-mcp-server.git .

# Stage 2: compilar el binario (desde el Dockerfile del upstream)
FROM golang:1.26.10-alpine AS devbuild
WORKDIR /build
RUN go env -w GOMODCACHE=/root/.cache/go-build
COPY --from=clone /src/go.mod /src/go.sum ./
RUN --mount=type=cache,target=/root/.cache/go-build go mod download
COPY --from=clone /src/ ./
RUN --mount=type=cache,target=/root/.cache/go-build CGO_ENABLED=0 go build -ldflags="-s -w" \
    -o terraform-mcp-server ./cmd/terraform-mcp-server

# Stage 3: certificados
FROM alpine:3.22 AS certbuild
RUN apk add --no-cache ca-certificates

# Stage 4: imagen final minimal
FROM scratch AS dev
WORKDIR /server
COPY --from=devbuild /build/terraform-mcp-server .
COPY --from=certbuild /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
USER 65532:65532
ENTRYPOINT ["./terraform-mcp-server"]
