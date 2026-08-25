from typing import Any, List

from ....models import BluettiDevice
from ..base_device.oak_device_gen2 import OakDeviceGen2
from ..base_device.fn_const import PROTO_FN_CODE

class OakCarProductDevice(OakDeviceGen2):
    SUPPORTED_MODELS = {"RV5"}
    SUPPORTED_MODELS_CACHE = None

    def __init__(self, address: str,bluetti_device:BluettiDevice):
        super().__init__(address,bluetti_device)
        self.slave_addr = 0

    def parse_oak_state_data(self,coordinator_data: dict) -> dict:
        bluetti_state_supper = super().parse_oak_state_data(coordinator_data)
        bluetti_state = {}
        for k,v in bluetti_state_supper.items():
            bluetti_value = v
            if k == PROTO_FN_CODE.PVAllTotalPower:
                bluetti_value = self.safe_int(bluetti_state_supper[PROTO_FN_CODE.DrivingChargingPower]) + self.safe_int(v)
            
            bluetti_state[k] = bluetti_value
        return bluetti_state
    
    def safe_int(self,s):
        try:
            return int(float(str(s).strip()))
        except (ValueError, TypeError):
            return 0