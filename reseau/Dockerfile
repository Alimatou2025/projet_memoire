FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    hostapd \
    dnsmasq \
    iw \
    net-tools \
    iproute2 \
    iptables \
    && rm -rf /var/lib/apt/lists/*

COPY demarrer.sh /demarrer.sh
RUN chmod +x /demarrer.sh

EXPOSE 53/udp 67/udp

CMD ["/demarrer.sh"]
