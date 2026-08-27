from enum import Enum, unique


@unique
class InverterStatus(Enum):
    Stop = 0
    OffGrid = 1
    GridConnectedLoad = 2
    GridConnectedOperation = 3
    GridConnectedCharging = 4
    GridConnectedDischarging = 5
    InverterFault = 6
    AbnormalOffGrid = 7
