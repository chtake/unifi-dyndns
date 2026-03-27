import logging
import os
import time
import requests
import urllib3
import dns.resolver

from urllib.parse import parse_qs, urlparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)


FETCH_PROTO = os.environ.get("FETCH_PROTO", "ipv6")
FETCH_IFACE = os.environ.get("FETCH_IFACE", "eth4")
DDNS_DOMAIN = os.environ.get("DDNS_DOMAIN", "home-v6.example.com")
RUN_INTERVAL_SECONDS = int(os.environ.get("RUN_INTERVAL_SECONDS", '300'))
DNS_LOOKUP_NAMESERVER = os.environ.get("DNS_LOOKUP_NAMESERVER", "8.8.8.8")

PROVIDER_API = os.environ.get("PROVIDER_API", "dyndns.variomedia.de/nic/update?hostname=%h&myip=%i")
PROVIDER_USERNAME = os.environ.get("PROVIDER_USERNAME")
PROVIDER_PASSWORD = os.environ.get("PROVIDER_PASSWORD")

GATEWAY_IP = os.environ.get("UNIFI_GATEWAY_IP", "192.168.1.1")
USERNAME = os.environ.get("UNIFI_USERNAME", "admin")
PASSWORD = os.environ.get("UNIFI_PASSWORD", "password")

LOGIN_URL = f"https://{GATEWAY_IP}/api/auth/login"
SYSTEM_URL = f"https://{GATEWAY_IP}/api/system"


def _get_wan_ip () -> str:
    data = _fetch_data()
    return _get_wan_ip_addr_by_proto(data, FETCH_PROTO, FETCH_IFACE)

def _get_wan_ip_addr_by_proto(data: dict, proto: str, iface: str) -> str:
    wans: list = data.get("wans", [])
    entry = next((e for e in wans if e.get("interface") == iface), None)
    if entry is None:
        raise ValueError(f"No WAN entry with interface='{iface}' found.")
    if proto not in entry:
        raise ValueError(f"Protocol '{proto}' not present in WAN entry for interface='{iface}'.")
    return entry[proto]

def _update_ddns(fetch_ip: str) -> None:
    """Updates the DDNS record via GET request with HTTP Basic Auth."""
    url = "https://" + PROVIDER_API.replace("%h", DDNS_DOMAIN).replace("%i", fetch_ip)
    log.debug("DDNS update URL: %s", url)
    auth = (PROVIDER_USERNAME, PROVIDER_PASSWORD) if PROVIDER_USERNAME and PROVIDER_PASSWORD else None
    response = requests.get(url, auth=auth, timeout=10)
    response.raise_for_status()
    log.info("DDNS update successful: %s %s", response.status_code, response.text.strip())


def _lookup_aaaa(hostname: str, nameserver: str) -> str:
    """Returns the first native IPv6 address (AAAA record).

    Args:
        hostname:   Hostname for which the AAAA record is looked up.
        nameserver: IP address of the DNS server to use.
    """
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [nameserver]

    answers = resolver.resolve(hostname, "AAAA")
    return str(answers[0])

def _fetch_data() -> dict:
    """Logs in to the gateway and returns the network health status."""

    session = requests.Session()
    session.verify = False
    session.headers.update({
        "Content-Type": "application/json",
        "Origin": f"https://{GATEWAY_IP}",
        "Referer": f"https://{GATEWAY_IP}/",
        "User-Agent": (
            "Mozilla/5.0 (compatible; unifi-dyndns/0.1)"
        ),
    })

    session.post(
        LOGIN_URL,
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    ).raise_for_status()

    response = session.get(SYSTEM_URL, timeout=10)
    response.raise_for_status()
    return response.json()

def main() -> None:
    log.info("=== unifi-dyndns started ===")
    log.info("  UNIFI_GATEWAY_IP       = %s", GATEWAY_IP)
    log.info("  UNIFI_USERNAME         = %s", USERNAME)
    log.info("  FETCH_IFACE            = %s", FETCH_IFACE)
    log.info("  FETCH_PROTO            = %s", FETCH_PROTO)
    log.info("  DNS_LOOKUP_NAMESERVER  = %s", DNS_LOOKUP_NAMESERVER)
    log.info("  DDNS_DOMAIN            = %s", DDNS_DOMAIN)
    log.info("  RUN_INTERVAL_SECONDS   = %s", RUN_INTERVAL_SECONDS)
    log.info("  PROVIDER_API           = %s", PROVIDER_API)
    log.info("  PROVIDER_USERNAME      = %s", PROVIDER_USERNAME)
    log.info("  LOG_LEVEL              = %s", _LOG_LEVEL)
    log.info("==========================================")

    iteration = 0
    while True:
        try:
            lookup_ip = _lookup_aaaa(DDNS_DOMAIN, DNS_LOOKUP_NAMESERVER)
            fetch_ip = _get_wan_ip()

            periodic = (iteration % 10 == 0)
            status_log = log.info if periodic else log.debug

            status_log("DNS lookup for %s returned: %s", DDNS_DOMAIN, lookup_ip)
            status_log("WAN IP at gateway: %s", fetch_ip)

            if lookup_ip != fetch_ip:
                log.info("WAN IP (%s) does not match DNS (%s) – starting update", fetch_ip, lookup_ip)
                _update_ddns(fetch_ip)
            else:
                status_log("IP unchanged (%s) – no update needed", fetch_ip)
        except Exception:
            log.exception("Error during update – retrying in %s seconds", RUN_INTERVAL_SECONDS)

        iteration += 1
        time.sleep(RUN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
