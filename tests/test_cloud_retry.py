"""Tests for cloud_retry.py: which failures leave the credentials unjudged."""

from unittest.mock import MagicMock

import aiohttp
import pytest
from pybluetti import HttpStatusException

from custom_components.bluetti.cloud_retry import is_transient_failure


def _response_error(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(MagicMock(), (), status=status)


@pytest.mark.parametrize("status", [500, 502, 503, 504, 408, 429])
def test_a_cloud_that_answers_badly_says_nothing_about_the_token(status):
    assert is_transient_failure(_response_error(status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_a_refused_grant_is_the_credentials_answer(status):
    # Home Assistant's OAuth helper calls raise_for_status(), so an SSO that
    # will not honour the refresh token arrives here as a 400 - the one case
    # that has to reach the user as a sign-in request.
    assert is_transient_failure(_response_error(status)) is False


def test_an_unreachable_cloud_is_transient():
    assert is_transient_failure(aiohttp.ClientConnectionError("dns")) is True
    assert is_transient_failure(TimeoutError()) is True


@pytest.mark.parametrize(
    ("status", "expected"),
    [(502, True), (503, True), (504, True), (401, False), (500, False)],
)
def test_gateway_statuses_follow_the_exception_s_own_verdict(status, expected):
    # HttpStatusException knows which of its statuses are worth a retry;
    # is_transient_failure defers to it rather than second-guessing.
    assert is_transient_failure(HttpStatusException(status, "reason")) is expected


def test_anything_else_is_not_transient():
    assert is_transient_failure(RuntimeError("boom")) is False
