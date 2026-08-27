"""Tests for the cloud-model-to-Modbus-device-type mapping."""

import pytest

from custom_components.bluetti.modbus_support import modbus_dev_type_for_model


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("Balco260", "balco260"),
        ("EP2000", "ep2000"),
        ("balco260", "balco260"),
        ("SMeter", None),
        ("AC200L", None),
        ("Unknown", None),
        ("", None),
        (None, None),
    ],
)
def test_modbus_dev_type_for_model(model, expected):
    assert modbus_dev_type_for_model(model) == expected
