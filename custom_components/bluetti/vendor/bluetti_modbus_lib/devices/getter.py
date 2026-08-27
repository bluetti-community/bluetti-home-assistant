from typing import cast

from modbus_connection import ModbusUnit

from .balco260 import Balco260
from .ep2000 import EP2000
from .smeter import SMeter


def get_device(
    d: str, unit: ModbusUnit | None = None
) -> Balco260 | EP2000 | SMeter | None:
    # unit=None is a real, supported call (e.g. sensor.py inspects a
    # device's fields without a live connection) - Component.__init__ only
    # stores the reference, it doesn't dereference it, so this is safe even
    # though ModbusUnit itself isn't declared Optional there.
    unit = cast(ModbusUnit, unit)
    if d == "balco260":
        return Balco260(unit)
    if d == "ep2000":
        return EP2000(unit)
    if d == "smeter":
        return SMeter(unit)
    else:
        return None
