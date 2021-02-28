FROM ghcr.io/linuxserver/wireguard

RUN apt-get update && apt-get install -y \
  openvpn \
  python3 \
  python3-pip \
  fping \
  && rm -rf /var/lib/apt/lists/* rm -r /etc/services.d/wireguard && rm -r /etc/services.d/coredns && /usr/bin/python3 -m pip install ifcfg speedtest-cli

COPY defaults/server.conf /defaults/server.conf
COPY defaults/peer.conf /defaults/peer.conf
COPY app/add-peer /app/add-peer
COPY services.d/openvpn /etc/services.d/openvpn
COPY services.d/manager /etc/services.d/manager
COPY cont-init.d/40-openvpncreds /etc/cont-init.d/40-openvpncreds
COPY cont-init.d/30-config /etc/cont-init.d/30-config
