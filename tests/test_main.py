"""Unittests für unifi_dyndns.main"""

from unittest.mock import MagicMock, patch

import pytest

from unifi_dyndns.main import (
    _get_wan_ip_addr_by_proto,
    _update_ddns,
    _lookup_aaaa,
)

FAKE_DATA = {
    "wans": [
        {
            "interface": "eth4",
            "ipv4": "192.168.2.171",
            "ipv6": "2a01:0000:0000:0000:0000:0000:0000:0000",
        }
    ]
}

IPV6 = "2a01:0000:0000:0000:0000:0000:0000:0000"


# ---------------------------------------------------------------------------
# _get_wan_ip_addr_by_proto
# ---------------------------------------------------------------------------

class TestGetWanIpAddrByProto:
    def test_returns_ipv6(self):
        assert _get_wan_ip_addr_by_proto(FAKE_DATA, "ipv6", "eth4") == IPV6

    def test_returns_ipv4(self):
        assert _get_wan_ip_addr_by_proto(FAKE_DATA, "ipv4", "eth4") == "192.168.2.171"

    def test_unknown_iface_raises(self):
        with pytest.raises(ValueError, match="interface='eth0'"):
            _get_wan_ip_addr_by_proto(FAKE_DATA, "ipv6", "eth0")

    def test_unknown_proto_raises(self):
        with pytest.raises(ValueError, match="ipv99"):
            _get_wan_ip_addr_by_proto(FAKE_DATA, "ipv99", "eth4")

    def test_empty_wans_raises(self):
        with pytest.raises(ValueError):
            _get_wan_ip_addr_by_proto({"wans": []}, "ipv6", "eth4")


# ---------------------------------------------------------------------------
# _update_ddns
# ---------------------------------------------------------------------------

class TestUpdateDdns:
    def test_calls_correct_url(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "good"

        with patch("unifi_dyndns.main.requests.get", return_value=mock_response) as mock_get:
            with patch.multiple(
                "unifi_dyndns.main",
                DDNS_DOMAIN="my.domain.de",
                PROVIDER_API="dyndns.example.de/nic/update?hostname=%h&myip=%i",
                PROVIDER_USERNAME="user",
                PROVIDER_PASSWORD="secret",
            ):
                _update_ddns(IPV6)

        called_url = mock_get.call_args[0][0]
        assert "my.domain.de" in called_url
        assert IPV6 in called_url
        assert "%h" not in called_url
        assert "%i" not in called_url

    def test_uses_basic_auth(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "good"

        with patch("unifi_dyndns.main.requests.get", return_value=mock_response) as mock_get:
            with patch.multiple(
                "unifi_dyndns.main",
                PROVIDER_USERNAME="myuser",
                PROVIDER_PASSWORD="mypass",
            ):
                _update_ddns(IPV6)

        assert mock_get.call_args[1]["auth"] == ("myuser", "mypass")

    def test_raises_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("503 Service Unavailable")

        with patch("unifi_dyndns.main.requests.get", return_value=mock_response):
            with pytest.raises(Exception, match="503"):
                _update_ddns(IPV6)


# ---------------------------------------------------------------------------
# _lookup_aaaa
# ---------------------------------------------------------------------------

class TestLookupAaaa:
    def test_returns_first_address(self):
        mock_answer = MagicMock()
        mock_answer.__str__ = lambda self: IPV6

        mock_answers = [mock_answer]

        with patch("unifi_dyndns.main.dns.resolver.Resolver") as MockResolver:
            instance = MockResolver.return_value
            instance.resolve.return_value = mock_answers

            result = _lookup_aaaa("my.domain.de", "8.8.8.8")

        assert result == IPV6
        instance.resolve.assert_called_once_with("my.domain.de", "AAAA")

    def test_sets_nameserver(self):
        mock_answer = MagicMock()
        mock_answer.__str__ = lambda self: IPV6

        with patch("unifi_dyndns.main.dns.resolver.Resolver") as MockResolver:
            instance = MockResolver.return_value
            instance.resolve.return_value = [mock_answer]

            _lookup_aaaa("my.domain.de", "1.1.1.1")

        assert instance.nameservers == ["1.1.1.1"]
