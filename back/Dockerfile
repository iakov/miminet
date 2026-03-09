FROM debian:stable-slim AS builder 
RUN --mount=type=cache,target=/var/lib/apt/lists --mount=type=cache,sharing=locked,target=/var/cache/apt \
  rm -f /var/lib/apt/lists/lock /var/cache/apt/archives/lock /var/lib/dpkg/lock-frontend \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    mininet \
    kmod \
    git\
    gcc \
    make \
    libpcap-dev \
    libbsd-dev \
    python3-dev

RUN --mount=type=cache,target=/var/mimidump \
    git -C /var/mimidump/src status || { rm -rf /var/mimidump/src ; git clone --single-branch --depth=1 https://github.com/mimi-net/mimidump.git /var/mimidump/src ; } \
    && cd /var/mimidump/src && make prefix=/usr install

RUN --mount=type=cache,target=/var/lib/astral \
    mkdir -p /var/lib/astral \
    && curl -LsSf https://astral.sh/uv/install.sh > /var/lib/astral/install_uv.sh \
    && sh /var/lib/astral/install_uv.sh


COPY ./src /app
WORKDIR /app

# Copy dependency files
COPY --from=project_root pyproject.toml uv.lock /app/
# Install dependencies
RUN --mount=type=cache,sharing=locked,target=/root/.cache/uv \
    $HOME/.local/bin/uv venv --seed \
    && $HOME/.local/bin/uv sync --group backend --group prod --no-install-project

FROM debian:stable-slim

RUN --mount=type=cache,sharing=locked,target=/var/lib/apt/lists --mount=type=cache,sharing=locked,target=/var/cache/apt \
  apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    dnsutils \
    netcat-openbsd \
    openssh-client \
    ifupdown \
    iproute2 \
    iptables \
    traceroute \
    iputils-ping \
    mininet \
    net-tools \
    kmod \
    bridge-utils \
    tcpdump \
    dnsmasq \
    isc-dhcp-client \
    openvswitch-switch \
 && touch /etc/network/interfaces \
 && mkdir /opt/mininet_dependencies

# Copy application code
COPY --from=builder /app /app
COPY --from=builder /usr/bin/mimidump /bin/mimidump
COPY --from=builder /root/.local/bin/uv /bin/uv
COPY ./ENTRYPOINT.sh /app/ENTRYPOINT.sh

WORKDIR /app

RUN --mount=type=cache,sharing=locked,target=/root/.cache/uv \
    /bin/uv sync --group backend --group prod --no-install-project

ENTRYPOINT ["/bin/uv", "run", "--no-sync", "/app/ENTRYPOINT.sh"]
