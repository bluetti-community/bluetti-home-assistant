"""The websocket endpoint follows the data center the cloud names in the token."""

import pytest

from custom_components.bluetti import _websocket_url

DEFAULT = "wss://gw.bluettipower.com/api/edgeiotgw/ws-coordination"


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("https://gw-eu.bluettipower.com", "wss://gw-eu.bluettipower.com/api/edgeiotgw/ws-coordination"),
        ("http://gw-eu.bluettipower.com", "ws://gw-eu.bluettipower.com/api/edgeiotgw/ws-coordination"),
        ("wss://gw-eu.bluettipower.com", "wss://gw-eu.bluettipower.com/api/edgeiotgw/ws-coordination"),
        ("gw-eu.bluettipower.com", "wss://gw-eu.bluettipower.com/api/edgeiotgw/ws-coordination"),
        ("gw-eu.bluettipower.com:8443", "wss://gw-eu.bluettipower.com:8443/api/edgeiotgw/ws-coordination"),
        (" https://gw-eu.bluettipower.com/ ", "wss://gw-eu.bluettipower.com/api/edgeiotgw/ws-coordination"),
        ("https://gw-eu.bluettipower.com/api/edgeiotgw", "wss://gw-eu.bluettipower.com/api/edgeiotgw/ws-coordination"),
    ],
)
def test_token_host_becomes_the_websocket_endpoint(host, expected):
    assert _websocket_url({"access_token": "tok", "host": host}, DEFAULT) == expected


@pytest.mark.parametrize("token", [{}, {"host": None}, {"host": ""}, {"host": "   "}, {"host": 42}, {"host": "https://"}])
def test_without_a_usable_host_the_profile_url_is_used(token):
    assert _websocket_url({"access_token": "tok", **token}, DEFAULT) == DEFAULT
