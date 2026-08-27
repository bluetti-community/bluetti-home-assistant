from typing import Any

from modbus_connection.model import RegisterField

from .field_extras import DeviceClass, FieldCategory, FieldStateClass


def set_category(reg: RegisterField[Any], category: FieldCategory | None) -> None:
    # category/state_class/device_class are metadata we attach, not
    # attributes RegisterField declares - setattr keeps that explicit
    # instead of asserting a type it doesn't have.
    setattr(reg, "category", category)  # noqa: B010


def set_state_class(
    reg: RegisterField[Any], state_class: FieldStateClass | None
) -> None:
    setattr(reg, "state_class", state_class)  # noqa: B010


def set_device_class(reg: RegisterField[Any], device_class: DeviceClass | None) -> None:
    setattr(reg, "device_class", device_class)  # noqa: B010
