from enum import Enum, unique
from typing import Any

from modbus_connection.model import RegisterField, WriteValidator, enum, float32, uint32
from modbus_connection.model.fields import NumberField, StringField


class BluettiStringField(StringField):
    def decode(self, words: list[int], scale_exponent: int | None = None) -> str:
        raw = b"".join((w & 0xFFFF).to_bytes(2, "little") for w in words)
        return raw.decode("ascii", errors="ignore").rstrip("\x00")

    def encode(self, value: Any, scale_exponent: int | None = None) -> list[int]:
        length = self.count
        raw = str(value).encode("ascii", errors="ignore")[: length * 2]
        raw = raw.ljust(length * 2, b"\x00")
        return [int.from_bytes(raw[i : i + 2], "little") for i in range(0, len(raw), 2)]


def uint16(
    address: int,
    *,
    scale: float = 1.0,
    writable: bool | WriteValidator = False,
    unit: str | None = None,
) -> NumberField[Any]:
    return NumberField(
        address,
        scale=scale,
        word_order="little",
        signed=False,
        writable=writable,
        unit=unit,
    )


def int16(
    address: int,
    *,
    scale: float = 1.0,
    writable: bool | WriteValidator = False,
    unit: str | None = None,
) -> NumberField[Any]:
    return NumberField(
        address,
        scale=scale,
        word_order="little",
        signed=True,
        writable=writable,
        unit=unit,
    )


def bluetti_string(
    address: int,
    length: int,
) -> BluettiStringField:
    return BluettiStringField(
        address,
        count=length,
        stride=0,
        writable=False,
        force_fc16=False,
    )


@unique
class FieldType(Enum):
    INT16 = "int16"
    UINT16 = "uint16"
    UINT32 = "uint32"
    FLOAT32 = "float32"
    STRING = "str"
    ENUM = "enum"


def field(
    t: FieldType,
    address: int,
    *,
    scale: float = 1.0,
    writable: bool | WriteValidator = False,
    unit: str | None = None,
    length: int = 1,
    count: int = 1,
    enum_type: type[Enum] | None = None,
) -> RegisterField[Any]:
    match t:
        case FieldType.INT16:
            return int16(address, scale=scale, writable=writable, unit=unit)
        case FieldType.UINT16:
            return uint16(address, scale=scale, writable=writable, unit=unit)
        case FieldType.UINT32:
            return uint32(
                address, scale=scale, writable=writable, unit=unit, word_order="little"
            )
        case FieldType.FLOAT32:
            return float32(
                address, scale=scale, writable=writable, unit=unit, word_order="little"
            )
        case FieldType.STRING:
            return bluetti_string(address, length)
        case FieldType.ENUM:
            # Every real caller (balco260.py, ep2000.py) passes enum_type
            # for FieldType.ENUM - the None default only exists because the
            # other FieldTypes don't use this parameter at all.
            assert enum_type is not None, "FieldType.ENUM requires enum_type"
            return enum(address, enum_type, count=count, word_order="little")
