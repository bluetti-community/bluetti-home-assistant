from typing import Any, List

from ....models import BluettiDevice
from ..base_device.oak_device_gen2 import OakDeviceGen2

class OakPortableDevice(OakDeviceGen2):
    
    SUPPORTED_MODELS = {"PR30V2,EL30V2,AORA30V2","PR100V2,EL100V2,AORA100V2"}
    SUPPORTED_MODELS_CACHE = None

    def __init__(self, address: str,bluetti_device:BluettiDevice):
        super().__init__(address,bluetti_device)