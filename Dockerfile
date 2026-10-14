FROM debian:bookworm-slim AS singbox

ARG TARGETARCH=arm64
ARG SING_BOX_VERSION=1.13.8
ARG SING_BOX_SHA256_ARM64=0ad8ffcf1b8463322ef7c6b11dd16767fc0bffe181190206bebb4cb04b4997e8
ARG SING_BOX_SHA256_AMD64=766abdefb4c0e62fbfed6fe2d2502731afb8fa578fae6219bd62982a66741341

RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates curl tar \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    case "${TARGETARCH}" in \
      arm64) asset="sing-box-${SING_BOX_VERSION}-linux-arm64-glibc.tar.gz"; sha256="${SING_BOX_SHA256_ARM64}" ;; \
      amd64) asset="sing-box-${SING_BOX_VERSION}-linux-amd64-glibc.tar.gz"; sha256="${SING_BOX_SHA256_AMD64}" ;; \
      *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl --fail --location --silent --show-error \
      --output /tmp/sing-box.tar.gz \
      "https://github.com/SagerNet/sing-box/releases/download/v${SING_BOX_VERSION}/${asset}"; \
    echo "${sha256}  /tmp/sing-box.tar.gz" | sha256sum --check --strict; \
    mkdir /tmp/sing-box; \
    tar --extract --gzip --file /tmp/sing-box.tar.gz --directory /tmp/sing-box --strip-components=1; \
    test -x /tmp/sing-box/sing-box; \
    install --mode=0755 /tmp/sing-box/sing-box /sing-box

FROM debian:bookworm-slim

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    GNUPGHOME=/run/singbox/gnupg

RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/singbox/profiles /run/singbox /var/lib/singbox /run/secrets

COPY --from=singbox /sing-box /usr/local/bin/sing-box
COPY profiles/ /opt/singbox/profiles/
COPY container/entrypoint.sh /usr/local/bin/singbox-entrypoint

RUN chmod 0755 /usr/local/bin/sing-box /usr/local/bin/singbox-entrypoint \
    && chmod 0644 /opt/singbox/profiles/*.gpg

ENTRYPOINT ["/usr/local/bin/singbox-entrypoint"]
CMD ["run"]
