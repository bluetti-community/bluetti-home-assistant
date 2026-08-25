from typing import Any, List

from ....models import BluettiDevice
from .oak_versatile_v1_device import OakVersatileV1Device

class OakVersatileV2Device(OakVersatileV1Device):
    
    SUPPORTED_MODELS = {"EL300,AORA300","AP300,AP300V2","AP200"}
    SUPPORTED_MODELS_CACHE = None

    def __init__(self, address: str,bluetti_device:BluettiDevice):
        super().__init__(address,bluetti_device)
        self.slave_addr = 0
    