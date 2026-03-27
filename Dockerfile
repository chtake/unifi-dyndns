FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

ENV UNIFI_GATEWAY_IP=192.168.1.1
ENV UNIFI_USERNAME=admin
ENV UNIFI_PASSWORD=password

ENV FETCH_PROTO=ipv6
ENV FETCH_IFACE=eth4

ENV DDNS_DOMAIN=home-v6.example.com
ENV RUN_INTERVAL_SECONDS=300
ENV DNS_LOOKUP_NAMESERVER=8.8.8.8

ENV PROVIDER_API=dyndns.variomedia.de/nic/update?hostname=%h&myip=%i
ENV PROVIDER_USERNAME=user
ENV PROVIDER_PASSWORD=password

CMD ["python", "-m", "unifi_dyndns"]
