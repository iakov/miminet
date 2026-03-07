FROM debian:stable-slim

RUN apt-get update \
&& apt-get install -y --no-install-recommends \
    curl \
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
    git\
    dnsmasq \
    isc-dhcp-client \
    gcc \
    make \
    libpcap-dev \
    libbsd-dev \
    openvswitch-switch \
 && rm -rf /var/lib/apt/lists/* \
 && touch /etc/network/interfaces \
 && mkdir /opt/mininet_dependencies

RUN git clone https://github.com/mimi-net/mimidump.git \
    && cd mimidump && git checkout 32e6e5e && make prefix=/usr install && cd .. && rm -rf mimidump


WORKDIR /app

# Copy dependency files
COPY --from=project_root pyproject.toml uv.lock /app/
RUN bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
# Install dependencies
RUN $HOME/.local/bin/uv venv --seed && $HOME/.local/bin/uv sync --group backend --group prod --no-install-project

# Copy application code
COPY ./src /app
COPY ./ENTRYPOINT.sh /app/ENTRYPOINT.sh
RUN chmod +x /app/ENTRYPOINT.sh

ENTRYPOINT ["/app/ENTRYPOINT.sh"]
