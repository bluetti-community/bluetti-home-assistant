"""Tests for profile/application_profile.py."""

import pytest

from custom_components.bluetti.profile.application_profile import ApplicationProfile


def test_active_profile_prefixes_config_filename():
    profile = ApplicationProfile(active="staging")
    assert profile._ApplicationProfile__configFile == "application-staging.yaml"


async def test_load_config_missing_file_raises_and_logs(hass):
    profile = ApplicationProfile(active="does-not-exist")

    with pytest.raises(OSError):
        await profile.load_config(hass)


async def test_default_profile_wss_url_has_no_trailing_slash(hass):
    """
    The default (prod) profile's wss URL must have no trailing slash.

    Regression test: pybluetti's StompClient appends "/websocket" to this
    URL via plain string concatenation, so a trailing slash here produced
    a double slash (".../ws-coordination//websocket"), which could prevent
    the push-update websocket from connecting.
    """
    profile = ApplicationProfile()
    await profile.load_config(hass)

    assert not profile.config["server"]["wss"].endswith("/")
