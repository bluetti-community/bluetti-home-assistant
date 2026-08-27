from enum import Enum, unique


@unique
class FieldCategory(Enum):
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


@unique
class FieldStateClass(Enum):
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"


@unique
class DeviceClass(Enum):
    BATTERY = "battery"
    CURRENT = "current"
    DURATION = "duration"
    ENERGY = "energy"
    FREQUENCY = "frequency"
    POWER = "power"
    TEMPERATURE = "temperature"
    VOLTAGE = "voltage"
