FROM ubuntu:22.04

RUN apt-get update \
&& apt-get install -y --no-install-recommends \
    curl \
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
    python3-pip \
    dnsmasq \
    isc-dhcp-client \
    python3-setuptools \
    gcc \
    make \
    libpcap-dev \
    libbsd-dev \
    openvswitch-switch \
 && pip3 install --upgrade pip \
 && rm -rf /var/lib/apt/lists/* \
 && touch /etc/network/interfaces \
 && mkdir /opt/mininet_dependencies

RUN git clone https://github.com/mimi-net/mimidump.git \
    && cd mimidump && git checkout 32e6e5e && make prefix=/usr install && cd .. && rm -rf mimidump

# Install Poetry
RUN pip3 install poetry

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-dev --no-root --no-directory

# Copy application code
COPY ./src /app
COPY ./ENTRYPOINT.sh /app/ENTRYPOINT.sh
RUN chmod +x /app/ENTRYPOINT.sh

ENTRYPOINT ["/app/ENTRYPOINT.sh"]
