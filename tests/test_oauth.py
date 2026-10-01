"""Tests for oauth.py: OAuth2FlowHandler helpers and AuthTokenRefresh."""

import logging
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import issue_registry as ir
from pybluetti import UserProduct
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluetti import _async_update_listener
from custom_components.bluetti.cloud_retry import (
    CloudUnreachableError,
    RefreshDeferredError,
)
from custom_components.bluetti.const import DOMAIN
from custom_components.bluetti.oauth import (
    ISSUE_ID_OAUTH_EXPIRED,
    AsyncConfigEntryAuth,
    AuthTokenRefresh,
    OAuth2FlowHandler,
)


def _refresher(hass, token: dict) -> tuple[AuthTokenRefresh, MockConfigEntry]:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = token
    return AuthTokenRefresh(hass, entry, session), entry


def test_logger_property():
    flow = OAuth2FlowHandler()
    assert flow.logger.name == "custom_components.bluetti.oauth"


async def test_async_oauth_create_entry_delegates_to_select_devices(hass):
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.async_step_select_devices = AsyncMock(return_value={"type": "abort", "reason": "success"})

    result = await flow.async_oauth_create_entry({"token": {"access_token": "x"}})

    assert flow._oauth_data == {"token": {"access_token": "x"}}
    flow.async_step_select_devices.assert_awaited_once_with()
    assert result["reason"] == "success"


async def test_async_step_reconfigure_missing_entry_aborts(hass):
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {"entry_id": "does-not-exist"}

    result = await flow.async_step_reconfigure()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_failed"


async def test_async_step_reconfigure_delegates_to_async_step_user(hass):
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {"entry_id": entry.entry_id}
    flow.async_step_user = AsyncMock(return_value={"type": "form"})

    result = await flow.async_step_reconfigure()

    assert flow.entry.entry_id == entry.entry_id
    flow.async_step_user.assert_awaited_once()
    assert result["type"] == "form"


async def test_token_refresh_init_subscribes_and_unsubs_on_unload(hass):
    refresher, entry = _refresher(hass, {})
    assert refresher.entry is entry

    hass.bus.async_fire("onTokenExpired")
    await hass.async_block_till_done()


async def test_on_token_expired_event_sends_notification(hass):
    refresher, _entry = _refresher(hass, {})
    refresher.send_expired_notification = MagicMock()

    await refresher.on_token_expired_event(None)

    refresher.send_expired_notification.assert_called_once()


def test_is_token_valid_no_token(hass):
    refresher, _entry = _refresher(hass, {})
    assert refresher.is_token_valid() is False


def test_is_token_valid_expires_at_in_future(hass):
    refresher, _entry = _refresher(hass, {"expires_at": time.time() + 1000})
    assert refresher.is_token_valid() is True


def test_is_token_valid_expires_at_in_past(hass):
    refresher, _entry = _refresher(hass, {"expires_at": time.time() - 1000})
    assert refresher.is_token_valid() is False


def test_is_token_valid_expires_in_created_at_future(hass):
    refresher, _entry = _refresher(
        hass, {"created_at": time.time(), "expires_in": 1000}
    )
    assert refresher.is_token_valid() is True


def test_is_token_valid_expires_in_created_at_past(hass):
    refresher, _entry = _refresher(
        hass, {"created_at": time.time() - 5000, "expires_in": 100}
    )
    assert refresher.is_token_valid() is False


def test_is_token_valid_no_recognizable_fields(hass):
    refresher, _entry = _refresher(hass, {"some_other_field": True})
    assert refresher.is_token_valid() is False


async def test_start_token_check_invalid_token_sends_notification(hass):
    refresher, _entry = _refresher(hass, {})
    refresher.send_expired_notification = MagicMock()
    refresher.async_check_token_expiry = AsyncMock()

    refresher.start_token_check()
    await hass.async_block_till_done()

    refresher.send_expired_notification.assert_called_once()
    refresher.async_check_token_expiry.assert_awaited_once()


async def test_start_token_check_valid_token_schedules_interval(hass):
    refresher, _entry = _refresher(hass, {"expires_at": time.time() + 1000})
    refresher.send_expired_notification = MagicMock()
    refresher.async_check_token_expiry = AsyncMock()

    with patch("custom_components.bluetti.oauth.async_track_time_interval") as mock_track:
        refresher.start_token_check()
        await hass.async_block_till_done()

    mock_track.assert_called_once()
    refresher.send_expired_notification.assert_not_called()
    refresher.async_check_token_expiry.assert_awaited_once()


def test_send_expired_notification_creates_notification(hass):
    refresher, _entry = _refresher(hass, {})

    with patch("custom_components.bluetti.oauth.persistent_notification.async_create") as mock_create:
        refresher.send_expired_notification()

    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["notification_id"] == "notifyTokenExpire"

    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID_OAUTH_EXPIRED)
    assert issue is not None
    assert issue.translation_key == "oauth_expired"
    assert issue.is_fixable is False


async def test_start_token_check_clears_issue_when_token_becomes_valid(hass):
    refresher, _entry = _refresher(hass, {"expires_at": time.time() + 1000})
    refresher.async_check_token_expiry = AsyncMock()
    ir.async_create_issue(
        hass, DOMAIN, ISSUE_ID_OAUTH_EXPIRED, is_fixable=False,
        severity=ir.IssueSeverity.ERROR, translation_key="oauth_expired",
    )

    with patch("custom_components.bluetti.oauth.async_track_time_interval"):
        refresher.start_token_check()
        await hass.async_block_till_done()

    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID_OAUTH_EXPIRED) is None


async def test_async_check_token_expiry_accepts_the_timer_callback_signature(hass):
    """
    async_track_time_interval always invokes its callback with a datetime.

    Regression test: this method is registered directly as that callback in
    start_token_check - if it didn't accept a positional `now`, every timer
    fire would raise TypeError and silently break the daily proactive check.
    """
    refresher, _entry = _refresher(hass, {})
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry(datetime.now())

    refresher.send_expired_notification.assert_not_called()


async def test_async_check_token_expiry_no_expires_at_logs_and_returns(hass):
    refresher, _entry = _refresher(hass, {})
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    refresher.send_expired_notification.assert_not_called()


async def test_async_check_token_expiry_already_expired(hass):
    refresher, _entry = _refresher(hass, {"expires_at": time.time() - 10})
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    refresher.send_expired_notification.assert_called_once()


async def test_async_check_token_expiry_not_due_soon_does_nothing(hass):
    refresher, _entry = _refresher(hass, {"expires_at": time.time() + 3600 * 24 * 30})
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    refresher.send_expired_notification.assert_not_called()


async def test_async_check_token_expiry_recent_refresh_is_skipped(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": time.time() - 60})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 100}
    refresher = AuthTokenRefresh(hass, entry, session)

    await refresher.async_check_token_expiry()

    session.implementation.async_refresh_token.assert_not_called()


async def test_async_check_token_expiry_notifies_when_rate_limited_and_expired(hass):
    """A recently-refreshed but already-expired token still notifies."""
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": time.time() - 60})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() - 100}
    refresher = AuthTokenRefresh(hass, entry, session)
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    session.implementation.async_refresh_token.assert_not_called()
    refresher.send_expired_notification.assert_called_once()


async def test_async_check_token_expiry_refreshes_and_reloads(hass):
    """
    Refreshing the token must reload the entry exactly once.

    Regression test: async_check_token_expiry() used to call
    hass.config_entries.async_reload() explicitly right after
    async_update_entry() - on a loaded entry (mock_reload here, matching a
    real one via the update listener registered below), that update
    already fires the entry's registered update listener, which reloads
    it - the explicit call fired a second, redundant reload.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entry.add_update_listener(_async_update_listener)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 100}
    session.implementation.async_refresh_token = AsyncMock(return_value={"access_token": "new"})
    refresher = AuthTokenRefresh(hass, entry, session)

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await refresher.async_check_token_expiry()
        await hass.async_block_till_done()

    session.implementation.async_refresh_token.assert_awaited_once()
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.data["token"] == {"access_token": "new"}
    mock_reload.assert_awaited_once_with(entry.entry_id)


async def test_async_force_refresh_stores_the_new_token_and_reloads(hass):
    # The cloud rejected a token far inside its announced lifetime: refresh
    # regardless of expires_at, store it, let the update listener reload.
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entry.add_update_listener(_async_update_listener)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 28 * 86400}
    session.implementation.async_refresh_token = AsyncMock(return_value={"access_token": "new"})
    refresher = AuthTokenRefresh(hass, entry, session)

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        assert await refresher.async_force_refresh() is True
        await hass.async_block_till_done()

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.data["token"] == {"access_token": "new"}
    assert updated.data["last_token_refresh"] > 0
    mock_reload.assert_awaited_once_with(entry.entry_id)


async def test_async_force_refresh_defers_just_after_a_refresh(hass):
    # A fresh token rejected again moments later: refreshing once more would
    # only hammer the SSO. Nothing was learnt about the credentials, so this
    # is not a failed refresh - the caller retries rather than asking for a
    # sign-in (#65).
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": time.time() - 60})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.implementation.async_refresh_token = AsyncMock()
    refresher = AuthTokenRefresh(hass, entry, session)

    with pytest.raises(RefreshDeferredError):
        await refresher.async_force_refresh()
    session.implementation.async_refresh_token.assert_not_awaited()


async def test_async_force_refresh_retries_once_the_floor_has_passed(hass):
    # The same rejection five minutes later does get a grant: the floor only
    # stops a loop, it does not leave the entry stuck for an hour.
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": time.time() - 301})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 28 * 86400}
    session.implementation.async_refresh_token = AsyncMock(return_value={"access_token": "new"})
    refresher = AuthTokenRefresh(hass, entry, session)

    assert await refresher.async_force_refresh() is True
    session.implementation.async_refresh_token.assert_awaited_once()


async def test_async_force_refresh_reports_a_failed_grant(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.implementation.async_refresh_token = AsyncMock(side_effect=RuntimeError("boom"))
    refresher = AuthTokenRefresh(hass, entry, session)

    assert await refresher.async_force_refresh() is False


async def test_async_force_refresh_raises_when_the_cloud_is_unreachable(hass):
    # A grant that never reached the SSO judges nothing. Reporting it as a
    # failed refresh sent owners to a sign-in page that fixed nothing while
    # their DNS was failing (#65), so it is raised instead.
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.implementation.async_refresh_token = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("DNS server returned answer with no data")
    )
    refresher = AuthTokenRefresh(hass, entry, session)

    with pytest.raises(CloudUnreachableError):
        await refresher.async_force_refresh()


async def test_async_force_refresh_reports_a_refused_grant_as_a_plain_failure(hass):
    # The SSO answering 400 is the one case that means the refresh token
    # itself is done: the caller does send the user through reauth.
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.implementation.async_refresh_token = AsyncMock(
        side_effect=aiohttp.ClientResponseError(MagicMock(), (), status=400)
    )
    refresher = AuthTokenRefresh(hass, entry, session)

    assert await refresher.async_force_refresh() is False


async def test_async_check_token_expiry_unreachable_cloud_does_not_ask_for_a_sign_in(hass):
    # Same rule on the daily check: an expired token whose refresh could not
    # be attempted waits for the next one rather than raising the notice.
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() - 100}
    session.implementation.async_refresh_token = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("dns")
    )
    refresher = AuthTokenRefresh(hass, entry, session)
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    refresher.send_expired_notification.assert_not_called()


async def test_async_check_token_expiry_refused_grant_asks_for_a_sign_in(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() - 100}
    session.implementation.async_refresh_token = AsyncMock(
        side_effect=aiohttp.ClientResponseError(MagicMock(), (), status=400)
    )
    refresher = AuthTokenRefresh(hass, entry, session)
    refresher.send_expired_notification = MagicMock()

    await refresher.async_check_token_expiry()

    refresher.send_expired_notification.assert_called_once()


async def test_async_check_token_expiry_refresh_failure_is_logged(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"last_token_refresh": 0.0})
    entry.add_to_hass(hass)
    session = MagicMock()
    session.token = {"expires_at": time.time() + 100}
    session.implementation.async_refresh_token = AsyncMock(side_effect=RuntimeError("boom"))
    refresher = AuthTokenRefresh(hass, entry, session)

    # Must not raise even though the refresh call failed.
    await refresher.async_check_token_expiry()


async def test_async_get_access_token_ensures_validity_first():
    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = {"access_token": "fresh-token"}
    auth = AsyncConfigEntryAuth(MagicMock(), session)

    token = await auth.async_get_access_token()

    session.async_ensure_token_valid.assert_awaited_once()
    assert token == "fresh-token"  # noqa: S105 - fake test fixture value, not a secret


async def test_select_devices_shows_form_with_available_devices(hass):
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {}
    flow._oauth_data = {
        "auth_implementation": "bluetti",
        "token": {"access_token": "tok", "expires_at": 9999999999},
    }
    product = UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")

    with patch("custom_components.bluetti.oauth.async_get_clientsession"), \
         patch("custom_components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=MagicMock(data=[product])
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "select_devices"


# --- a fresh token rejected: ask the other data centers (#65) ---------------


def _deferring_refresher(hass, gateway: str = "global"):
    """A refresher whose floor will hold: a refresh was made a minute ago."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"last_token_refresh": time.time() - 60, "gateway": gateway}
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entry.add_update_listener(_async_update_listener)
    session = MagicMock()
    session.token = {"access_token": "fresh"}
    session.implementation.async_refresh_token = AsyncMock()
    return AuthTokenRefresh(hass, entry, session), entry, session


def _answer(msg_code: int) -> MagicMock:
    response = MagicMock()
    response.msgCode = msg_code
    return response


async def test_a_fresh_token_rejected_moves_the_account_to_the_data_center_that_takes_it(hass):
    # A token refused moments after the SSO issued it is not expired: the
    # recorded gateway stopped honouring the account. Ask the others, move the
    # entry to the one that answers, and let the data update reload it.
    refresher, entry, session = _deferring_refresher(hass)
    seen: list[str] = []

    async def _probe(fetch, preferred):
        seen.append(preferred)
        await fetch("https://gwde.bluettipower.com")  # the real fetch, client patched
        return "eu", _answer(0)

    with (
        patch("custom_components.bluetti.oauth.async_probe_gateway", side_effect=_probe),
        patch("custom_components.bluetti.oauth.ProductClient") as client_cls,
        patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload,
    ):
        client_cls.return_value.get_user_products = AsyncMock(return_value=_answer(0))
        with pytest.raises(RefreshDeferredError, match="moved to the eu data center"):
            await refresher.async_force_refresh()
        await hass.async_block_till_done()

    assert seen == ["global"]
    client_cls.assert_called_once_with(
        client_cls.call_args.args[0], "https://gwde.bluettipower.com", "fresh", on_auth_expired=None
    )
    assert hass.config_entries.async_get_entry(entry.entry_id).data["gateway"] == "eu"
    mock_reload.assert_awaited_once_with(entry.entry_id)
    session.implementation.async_refresh_token.assert_not_awaited()


async def test_every_data_center_rejecting_is_an_outage_said_once(hass, caplog):
    # Every gateway refusing the same fresh token is BLUETTI's outage, not a
    # sign-in problem. Said once per episode, even across the reloads every
    # refresh causes - not once per five minutes for ten hours.
    refresher, entry, session = _deferring_refresher(hass)
    probe = AsyncMock(return_value=("global", _answer(805)))

    with patch("custom_components.bluetti.oauth.async_probe_gateway", probe):
        with caplog.at_level(logging.DEBUG), pytest.raises(RefreshDeferredError, match="moments ago"):
            await refresher.async_force_refresh()
        warned = [r for r in caplog.records if "Every BLUETTI data center" in r.message]
        assert [r.levelno for r in warned] == [logging.WARNING]

        caplog.clear()
        reloaded = AuthTokenRefresh(hass, entry, session)  # what the next reload builds
        with caplog.at_level(logging.DEBUG), pytest.raises(RefreshDeferredError):
            await reloaded.async_force_refresh()
        warned = [r for r in caplog.records if "Every BLUETTI data center" in r.message]
        assert [r.levelno for r in warned] == [logging.DEBUG]

    assert hass.config_entries.async_get_entry(entry.entry_id).data["gateway"] == "global"


async def test_the_recorded_data_center_taking_the_token_again_changes_nothing(hass, caplog):
    refresher, entry, _session = _deferring_refresher(hass)
    probe = AsyncMock(return_value=("global", _answer(0)))

    with (
        patch("custom_components.bluetti.oauth.async_probe_gateway", probe),
        caplog.at_level(logging.WARNING),
        pytest.raises(RefreshDeferredError, match="moments ago"),
    ):
        await refresher.async_force_refresh()

    assert "data center" not in caplog.text
    assert hass.config_entries.async_get_entry(entry.entry_id).data["gateway"] == "global"


async def test_the_other_data_centers_are_asked_once_per_setup(hass):
    # Once per setup is once per refresh window: polls keep landing inside
    # the floor, and each must not cost a round of the data centers.
    refresher, _entry, _session = _deferring_refresher(hass)
    probe = AsyncMock(return_value=("global", _answer(805)))

    with patch("custom_components.bluetti.oauth.async_probe_gateway", probe):
        for _ in range(3):
            with pytest.raises(RefreshDeferredError):
                await refresher.async_force_refresh()

    probe.assert_awaited_once()


async def test_a_data_center_probe_that_fails_changes_nothing(hass):
    refresher, entry, _session = _deferring_refresher(hass)
    probe = AsyncMock(side_effect=aiohttp.ClientConnectionError("unreachable"))

    with (
        patch("custom_components.bluetti.oauth.async_probe_gateway", probe),
        pytest.raises(RefreshDeferredError, match="moments ago"),
    ):
        await refresher.async_force_refresh()

    assert hass.config_entries.async_get_entry(entry.entry_id).data["gateway"] == "global"
