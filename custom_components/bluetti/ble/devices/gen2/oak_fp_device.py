from typing import Any, List

from ....models import BluettiDevice
from ..base_device.oak_device_gen2 import OakDeviceGen2

class OakFPDevice(OakDeviceGen2):
    # FP "FP"
    SUPPORTED_MODELS = {"FP"}
    SUPPORTED_MODELS_CACHE = None

    def __init__(self, address: str,bluetti_device:BluettiDevice):
        super().__init__(address,bluetti_device)
        # gen2 iot board addr 0
        self.slave_addr = 0
    