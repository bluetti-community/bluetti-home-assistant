from typing import Any, List

from ....models import BluettiDevice
from ..base_device.oak_device_gen1 import OakDeviceGen1

class OakPortableDeviceG1(OakDeviceGen1):

    SUPPORTED_MODELS = {"AC200L","AC200PL"}
    SUPPORTED_MODELS_CACHE = None

    def __init__(self, address: str,bluetti_device:BluettiDevice):
        super().__init__(address,bluetti_device)

    