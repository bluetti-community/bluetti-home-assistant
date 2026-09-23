"""Tests for gateway.py - which data center serves the account."""

from types import SimpleNamespace

import pytest
from pybluetti import UnifyResponse

from custom_components.bluetti.gateway import (
    CONF_GATEWAY,
    GATEWAY_GLOBAL,
    GATEWAY_URLS,
    TOKEN_REJECTED,
    async_probe_gateway,
    entry_gateway,
    gateway_url,
)

GLOBAL_URL = "https://gw.bluettipower.com"


def _rejected() -> UnifyResponse:
    return UnifyResponse(msgId="1", msgCode=TOKEN_REJECTED)


def _ok() -> UnifyResponse:
    return UnifyResponse(msgId="1", msgCode=0, data=[])


def _fetcher(answers: dict[str, object]):
    calls: list[str] = []

    async def fetch(url: str):
        calls.append(url)
        answer = answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    return fetch, calls


async def test_the_preferred_gateway_answering_ends_the_search():
    fetch, calls = _fetcher({GLOBAL_URL: _ok()})

    region, response = await async_probe_gateway(fetch, GATEWAY_GLOBAL)

    assert region == GATEWAY_GLOBAL
    assert response.is_ok()
    assert calls == [GLOBAL_URL]


async def test_a_rejected_token_moves_on_to_the_next_data_center():
    # A German account (bluetti-official/bluetti-home-assistant#172): the
    # global gateway answers 805 to a token the sign-in just issued, the EU
    # one serves the account.
    fetch, calls = _fetcher({GLOBAL_URL: _rejected(), GATEWAY_URLS["eu"]: _ok()})

    region, response = await async_probe_gateway(fetch, GATEWAY_GLOBAL)

    assert region == "eu"
    assert response.is_ok()
    assert calls == [GLOBAL_URL, GATEWAY_URLS["eu"]]


async def test_the_recorded_data_center_is_asked_first():
    fetch, calls = _fetcher({GATEWAY_URLS["eu"]: _ok()})

    region, _ = await async_probe_gateway(fetch, "eu")

    assert region == "eu"
    assert calls == [GATEWAY_URLS["eu"]]


async def test_rejected_everywhere_returns_the_preferred_gateways_answer():
    # A genuinely expired token: every data center says 805, and the caller
    # gets the same 805 it always did, for the same handling.
    fetch, calls = _fetcher({url: _rejected() for url in (GLOBAL_URL, *GATEWAY_URLS.values())})

    region, response = await async_probe_gateway(fetch, GATEWAY_GLOBAL)

    assert region == GATEWAY_GLOBAL
    assert response.msgCode == TOKEN_REJECTED
    assert len(calls) == 1 + len(GATEWAY_URLS)


async def test_another_application_error_is_not_a_reason_to_try_elsewhere():
    fetch, calls = _fetcher({GLOBAL_URL: UnifyResponse(msgId="1", msgCode=500)})

    region, response = await async_probe_gateway(fetch, GATEWAY_GLOBAL)

    assert region == GATEWAY_GLOBAL
    assert response.msgCode == 500
    assert calls == [GLOBAL_URL]


async def test_an_exception_surfaces_unchanged():
    fetch, _ = _fetcher({GLOBAL_URL: RuntimeError("boom")})

    with pytest.raises(RuntimeError, match="boom"):
        await async_probe_gateway(fetch, GATEWAY_GLOBAL)


async def test_a_response_without_a_msgcode_counts_as_an_answer():
    fetch, calls = _fetcher({GLOBAL_URL: SimpleNamespace(data=[], is_ok=lambda: True)})

    region, _ = await async_probe_gateway(fetch, GATEWAY_GLOBAL)

    assert region == GATEWAY_GLOBAL
    assert calls == [GLOBAL_URL]


def test_gateway_url_per_region():
    assert gateway_url("eu") == GATEWAY_URLS["eu"]
    assert gateway_url("us") == GATEWAY_URLS["us"]


def test_entry_gateway_defaults_and_ignores_unknown_values():
    assert entry_gateway({}) == GATEWAY_GLOBAL
    assert entry_gateway({CONF_GATEWAY: "eu"}) == "eu"
    assert entry_gateway({CONF_GATEWAY: "mars"}) == GATEWAY_GLOBAL
